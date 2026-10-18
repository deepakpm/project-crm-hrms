import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import Connection, text

from app.db import engine


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _set_tenant(conn: Connection, tenant_id: object) -> None:
    conn.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)}
    )


def _signup(client: TestClient) -> tuple[dict[str, str], str]:
    slug = _unique("people")
    resp = client.post(
        "/auth/signup",
        json={
            "company_name": slug,
            "tenant_slug": slug,
            "email": "owner@people.example",
            "password": "correct-horse-battery-staple",
        },
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, slug


def _add_teammate(
    client: TestClient, owner_headers: dict[str, str], email: str, role: str, slug: str
) -> tuple[dict[str, str], uuid.UUID]:
    resp = client.post(
        "/users",
        headers=owner_headers,
        json={"email": email, "password": "correct-horse-battery-staple", "role": role},
    )
    assert resp.status_code == 201, resp.text
    user_id = uuid.UUID(resp.json()["id"])
    login = client.post(
        "/auth/login",
        json={"tenant_slug": slug, "email": email, "password": "correct-horse-battery-staple"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, user_id


def _create_employee(
    client: TestClient,
    owner_headers: dict[str, str],
    code: str,
    name: str,
    email: str,
    user_id: uuid.UUID | None = None,
    manager_id: uuid.UUID | None = None,
) -> uuid.UUID:
    resp = client.post(
        "/people/employees",
        headers=owner_headers,
        json={
            "code": code,
            "name": name,
            "work_email": email,
            "join_date": "2024-01-01",
            "user_id": str(user_id) if user_id else None,
            "manager_id": str(manager_id) if manager_id else None,
        },
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["id"])


def _setup(client: TestClient) -> dict[str, object]:
    owner_headers, slug = _signup(client)
    # Seeds the chart of accounts -- expense-claim approval posts a journal
    # against it, same precondition invoices already have.
    company_resp = client.put(
        "/company",
        headers=owner_headers,
        json={
            "legal_name": "People Co",
            "gstin": "27AAAAA0000A1Z5",
            "state_code": "27",
            "address": "Mumbai, Maharashtra",
        },
    )
    assert company_resp.status_code == 200, company_resp.text

    boss_headers, boss_user_id = _add_teammate(
        client, owner_headers, "boss@people.example", "member", slug
    )
    report_headers, report_user_id = _add_teammate(
        client, owner_headers, "report@people.example", "member", slug
    )
    outsider_headers, _outsider_user_id = _add_teammate(
        client, owner_headers, "outsider@people.example", "member", slug
    )

    employee_boss_id = _create_employee(
        client, owner_headers, "EMP-BOSS", "Boss", "boss@co.example", boss_user_id
    )
    employee_report_id = _create_employee(
        client,
        owner_headers,
        "EMP-REPORT",
        "Report",
        "report@co.example",
        report_user_id,
        employee_boss_id,
    )

    leave_type_resp = client.post(
        "/people/leave/types",
        headers=owner_headers,
        json={"name": "Casual Leave", "exclude_weekends": True, "exclude_holidays": True},
    )
    assert leave_type_resp.status_code == 201, leave_type_resp.text
    leave_type_id = leave_type_resp.json()["id"]

    policy_resp = client.post(
        "/people/leave/policies",
        headers=owner_headers,
        json={"name": "Standard", "types": [{"leave_type_id": leave_type_id, "annual_days": 10}]},
    )
    assert policy_resp.status_code == 201, policy_resp.text
    policy_id = policy_resp.json()["id"]

    apply_resp = client.post(
        f"/people/leave/policies/{policy_id}/apply",
        headers=owner_headers,
        json={"employee_id": str(employee_report_id), "financial_year": "2026-27"},
    )
    assert apply_resp.status_code == 200, apply_resp.text

    return {
        "owner_headers": owner_headers,
        "boss_headers": boss_headers,
        "report_headers": report_headers,
        "outsider_headers": outsider_headers,
        "employee_boss_id": str(employee_boss_id),
        "employee_report_id": str(employee_report_id),
        "leave_type_id": leave_type_id,
        "slug": slug,
    }


def test_leave_balance_equals_sum_of_ledger_rows(client: TestClient) -> None:
    s = _setup(client)

    balances = client.get(
        f"/people/leave/balances/{s['employee_report_id']}", headers=s["report_headers"]
    )
    assert balances.status_code == 200, balances.text
    initial = next(b for b in balances.json() if b["leave_type_id"] == s["leave_type_id"])
    assert Decimal(initial["balance_days"]) == 10

    # Monday to Tuesday: 2 weekdays, no weekend in range.
    create_resp = client.post(
        "/people/leave/applications",
        headers=s["report_headers"],
        json={
            "employee_id": s["employee_report_id"],
            "leave_type_id": s["leave_type_id"],
            "start_date": "2026-11-02",
            "end_date": "2026-11-03",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    application_id = create_resp.json()["id"]

    submit_resp = client.post(
        f"/people/leave/applications/{application_id}/submit", headers=s["report_headers"]
    )
    assert submit_resp.status_code == 200, submit_resp.text
    assert Decimal(submit_resp.json()["days"]) == 2

    approve_resp = client.post(
        f"/people/leave/applications/{application_id}/approve", headers=s["boss_headers"]
    )
    assert approve_resp.status_code == 200, approve_resp.text

    balances = client.get(
        f"/people/leave/balances/{s['employee_report_id']}", headers=s["report_headers"]
    )
    api_balance = next(
        b for b in balances.json() if b["leave_type_id"] == s["leave_type_id"]
    )["balance_days"]
    assert Decimal(api_balance) == 8

    with engine.connect() as conn:
        tenant_id = conn.execute(
            text("SELECT id FROM tenant WHERE slug = :s"), {"s": s["slug"]}
        ).scalar_one()
        _set_tenant(conn, tenant_id)
        ledger_sum = conn.execute(
            text(
                "SELECT COALESCE(SUM(days_delta), 0) FROM leave_ledger_entry "
                "WHERE employee_id = :eid AND leave_type_id = :ltid"
            ),
            {"eid": s["employee_report_id"], "ltid": s["leave_type_id"]},
        ).scalar_one()
        conn.rollback()
    assert ledger_sum == 8 == Decimal(api_balance)


def test_overlapping_leave_is_rejected(client: TestClient) -> None:
    s = _setup(client)

    first = client.post(
        "/people/leave/applications",
        headers=s["report_headers"],
        json={
            "employee_id": s["employee_report_id"],
            "leave_type_id": s["leave_type_id"],
            "start_date": "2026-11-02",
            "end_date": "2026-11-04",
        },
    ).json()
    submit = client.post(
        f"/people/leave/applications/{first['id']}/submit", headers=s["report_headers"]
    )
    assert submit.status_code == 200, submit.text

    second = client.post(
        "/people/leave/applications",
        headers=s["report_headers"],
        json={
            "employee_id": s["employee_report_id"],
            "leave_type_id": s["leave_type_id"],
            "start_date": "2026-11-04",
            "end_date": "2026-11-05",
        },
    ).json()
    overlap_submit = client.post(
        f"/people/leave/applications/{second['id']}/submit", headers=s["report_headers"]
    )
    assert overlap_submit.status_code == 400


def test_approval_by_non_manager_is_denied(client: TestClient) -> None:
    s = _setup(client)

    application = client.post(
        "/people/leave/applications",
        headers=s["report_headers"],
        json={
            "employee_id": s["employee_report_id"],
            "leave_type_id": s["leave_type_id"],
            "start_date": "2026-11-02",
            "end_date": "2026-11-02",
        },
    ).json()
    submit = client.post(
        f"/people/leave/applications/{application['id']}/submit", headers=s["report_headers"]
    )
    assert submit.status_code == 200, submit.text

    denied = client.post(
        f"/people/leave/applications/{application['id']}/approve", headers=s["outsider_headers"]
    )
    assert denied.status_code == 403

    approved = client.post(
        f"/people/leave/applications/{application['id']}/approve", headers=s["boss_headers"]
    )
    assert approved.status_code == 200, approved.text


def test_cross_employee_access_denied_via_api(client: TestClient) -> None:
    s = _setup(client)

    # outsider is not the employee, not their manager, not owner/hr
    detail = client.get(
        f"/people/employees/{s['employee_report_id']}", headers=s["outsider_headers"]
    )
    assert detail.status_code == 403

    listing = client.get("/people/employees", headers=s["outsider_headers"])
    assert listing.status_code == 200
    assert s["employee_report_id"] not in {row["id"] for row in listing.json()}

    # the manager CAN see their report
    manager_view = client.get(
        f"/people/employees/{s['employee_report_id']}", headers=s["boss_headers"]
    )
    assert manager_view.status_code == 200


def test_cross_tenant_access_denied_via_api_and_raw_sql(client: TestClient) -> None:
    s = _setup(client)
    other_owner_headers, _other_slug = _signup(client)

    cross_tenant = client.get(
        f"/people/employees/{s['employee_report_id']}", headers=other_owner_headers
    )
    assert cross_tenant.status_code == 404  # RLS hides it entirely -- not even a 403

    with engine.connect() as conn:
        tenant_id = conn.execute(
            text("SELECT id FROM tenant WHERE slug = :s"), {"s": s["slug"]}
        ).scalar_one()
        conn.rollback()

    with engine.connect() as conn:
        # Deliberately NOT setting this tenant's context -- simulating a
        # session scoped to some other tenant trying to read across the line.
        conn.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": "00000000-0000-0000-0000-000000000000"},
        )
        rows = conn.execute(
            text("SELECT id FROM employee WHERE id = :eid"), {"eid": s["employee_report_id"]}
        ).fetchall()
        assert rows == []
        conn.rollback()

    # sanity: the row really is visible under its own tenant's context
    with engine.connect() as conn:
        _set_tenant(conn, tenant_id)
        rows = conn.execute(
            text("SELECT id FROM employee WHERE id = :eid"), {"eid": s["employee_report_id"]}
        ).fetchall()
        assert len(rows) == 1
        conn.rollback()


def test_employee_update_audits_changed_fields(client: TestClient) -> None:
    s = _setup(client)
    resp = client.put(
        f"/people/employees/{s['employee_report_id']}",
        headers=s["owner_headers"],
        json={
            "code": "EMP-REPORT",
            "name": "Report Renamed",
            "work_email": "report@co.example",
            "join_date": "2024-01-01",
            "manager_id": s["employee_boss_id"],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Report Renamed"

    with engine.connect() as conn:
        tenant_id = conn.execute(
            text("SELECT id FROM tenant WHERE slug = :s"), {"s": s["slug"]}
        ).scalar_one()
        _set_tenant(conn, tenant_id)
        rows = conn.execute(
            text(
                "SELECT field_names FROM audit_log WHERE table_name = 'employee' "
                "AND action = 'update' AND record_id = :eid"
            ),
            {"eid": s["employee_report_id"]},
        ).fetchall()
        conn.rollback()
    assert len(rows) == 1
    assert "name" in rows[0][0]


def test_expense_claim_lifecycle_posts_balanced_journal(client: TestClient) -> None:
    s = _setup(client)

    create = client.post(
        "/people/expenses",
        headers=s["report_headers"],
        json={
            "employee_id": s["employee_report_id"],
            "lines": [
                {"description": "Taxi", "amount_paise": 50_000, "category": "travel"},
                {"description": "Lunch", "amount_paise": 30_000, "category": "meals"},
            ],
        },
    )
    assert create.status_code == 201, create.text
    claim_id = create.json()["id"]

    submit = client.post(f"/people/expenses/{claim_id}/submit", headers=s["report_headers"])
    assert submit.status_code == 200, submit.text
    assert submit.json()["total_paise"] == 80_000

    approve = client.post(f"/people/expenses/{claim_id}/approve", headers=s["boss_headers"])
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"

    reimburse = client.post(
        f"/people/expenses/{claim_id}/reimburse",
        headers=s["owner_headers"],
        json={"amount_paise": 80_000, "method": "bank_transfer"},
    )
    assert reimburse.status_code == 200, reimburse.text

    trial_balance = client.get("/reports/trial-balance", headers=s["owner_headers"])
    assert trial_balance.status_code == 200, trial_balance.text
    rows = {r["account_code"]: r for r in trial_balance.json()}
    assert rows["5100"]["debit_paise"] == 80_000  # Operating Expenses
    assert rows["2400"]["debit_paise"] == 80_000  # Employee Reimbursements Payable cleared
    assert rows["2400"]["credit_paise"] == 80_000
    assert rows["1000"]["credit_paise"] == 80_000  # Cash and Bank paid out

    total_debit = sum(r["debit_paise"] for r in rows.values())
    total_credit = sum(r["credit_paise"] for r in rows.values())
    assert total_debit == total_credit


def test_leave_entirely_on_holiday_is_rejected(client: TestClient) -> None:
    s = _setup(client)

    holiday_list_resp = client.post(
        "/people/leave/holiday-lists",
        headers=s["owner_headers"],
        json={"name": "Default"},
    )
    assert holiday_list_resp.status_code == 201, holiday_list_resp.text
    holiday_list_id = holiday_list_resp.json()["id"]
    # 2026-11-02 is a Monday -- a genuine working day unless declared a holiday.
    add_holiday = client.post(
        f"/people/leave/holiday-lists/{holiday_list_id}/holidays",
        headers=s["owner_headers"],
        json={"date": "2026-11-02", "description": "Company holiday"},
    )
    assert add_holiday.status_code == 201, add_holiday.text

    create_resp = client.post(
        "/people/leave/applications",
        headers=s["report_headers"],
        json={
            "employee_id": s["employee_report_id"],
            "leave_type_id": s["leave_type_id"],
            "start_date": "2026-11-02",
            "end_date": "2026-11-02",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    application_id = create_resp.json()["id"]

    submit_resp = client.post(
        f"/people/leave/applications/{application_id}/submit", headers=s["report_headers"]
    )
    assert submit_resp.status_code == 400, submit_resp.text


def test_half_day_leave_deducts_half_day_balance(client: TestClient) -> None:
    s = _setup(client)

    create_resp = client.post(
        "/people/leave/applications",
        headers=s["report_headers"],
        json={
            "employee_id": s["employee_report_id"],
            "leave_type_id": s["leave_type_id"],
            "start_date": "2026-11-02",
            "end_date": "2026-11-02",
            "half_day": True,
            "reason_code": "medical",
            "comment": "doctor appointment",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    application_id = create_resp.json()["id"]

    submit_resp = client.post(
        f"/people/leave/applications/{application_id}/submit", headers=s["report_headers"]
    )
    assert submit_resp.status_code == 200, submit_resp.text
    assert Decimal(submit_resp.json()["days"]) == Decimal("0.5")
    assert submit_resp.json()["reason_code"] == "medical"
    assert submit_resp.json()["comment"] == "doctor appointment"


def test_approve_marks_attendance_and_cancel_clears_it(client: TestClient) -> None:
    s = _setup(client)

    create_resp = client.post(
        "/people/leave/applications",
        headers=s["report_headers"],
        json={
            "employee_id": s["employee_report_id"],
            "leave_type_id": s["leave_type_id"],
            "start_date": "2026-11-02",
            "end_date": "2026-11-03",
        },
    )
    application_id = create_resp.json()["id"]
    client.post(f"/people/leave/applications/{application_id}/submit", headers=s["report_headers"])
    approve_resp = client.post(
        f"/people/leave/applications/{application_id}/approve", headers=s["boss_headers"]
    )
    assert approve_resp.status_code == 200, approve_resp.text

    calendar = client.get(
        f"/people/attendance/{s['employee_report_id']}",
        params={"year": 2026, "month": 11},
        headers=s["report_headers"],
    )
    assert calendar.status_code == 200, calendar.text
    by_date = {row["date"]: row for row in calendar.json()}
    assert by_date["2026-11-02"]["status"] == "on_leave"
    assert by_date["2026-11-02"]["leave_application_id"] == application_id
    assert by_date["2026-11-03"]["status"] == "on_leave"

    # Manual override of a leave-derived day is blocked.
    blocked = client.post(
        "/people/attendance",
        headers=s["report_headers"],
        json={"employee_id": s["employee_report_id"], "date": "2026-11-02", "status": "present"},
    )
    assert blocked.status_code == 409, blocked.text

    cancel_resp = client.post(
        f"/people/leave/applications/{application_id}/cancel", headers=s["report_headers"]
    )
    assert cancel_resp.status_code == 200, cancel_resp.text

    calendar_after = client.get(
        f"/people/attendance/{s['employee_report_id']}",
        params={"year": 2026, "month": 11},
        headers=s["report_headers"],
    )
    dates_after = {row["date"] for row in calendar_after.json()}
    assert "2026-11-02" not in dates_after
    assert "2026-11-03" not in dates_after


def test_accrual_credits_incrementally_and_is_idempotent_per_period(client: TestClient) -> None:
    s = _setup(client)

    leave_type_resp = client.post(
        "/people/leave/types",
        headers=s["owner_headers"],
        json={"name": "Earned Leave", "accrual_frequency": "monthly"},
    )
    assert leave_type_resp.status_code == 201, leave_type_resp.text
    accrual_leave_type_id = leave_type_resp.json()["id"]

    policy_resp = client.post(
        "/people/leave/policies",
        headers=s["owner_headers"],
        json={
            "name": "Earned",
            "types": [{"leave_type_id": accrual_leave_type_id, "annual_days": 12}],
        },
    )
    policy_id = policy_resp.json()["id"]
    apply_resp = client.post(
        f"/people/leave/policies/{policy_id}/apply",
        headers=s["owner_headers"],
        json={"employee_id": s["employee_report_id"], "financial_year": "2026-27"},
    )
    assert apply_resp.status_code == 200, apply_resp.text
    allocation_id = next(
        a for a in apply_resp.json() if a["leave_type_id"] == accrual_leave_type_id
    )["id"]

    # Accruing type -- allocation exists but the ledger starts at zero, not the full cap.
    balances = client.get(
        f"/people/leave/balances/{s['employee_report_id']}", headers=s["owner_headers"]
    ).json()
    before = next(b for b in balances if b["leave_type_id"] == accrual_leave_type_id)
    assert Decimal(before["balance_days"]) == 0

    accrue_resp = client.post(
        f"/people/leave/allocations/{allocation_id}/accrue", headers=s["owner_headers"]
    )
    assert accrue_resp.status_code == 200, accrue_resp.text

    balances = client.get(
        f"/people/leave/balances/{s['employee_report_id']}", headers=s["owner_headers"]
    ).json()
    after = next(b for b in balances if b["leave_type_id"] == accrual_leave_type_id)
    assert Decimal(after["balance_days"]) == 1  # 12 annual / 12 months

    # Same period again -- idempotent, no double credit.
    again = client.post(
        f"/people/leave/allocations/{allocation_id}/accrue", headers=s["owner_headers"]
    )
    assert again.status_code == 409, again.text
