import threading
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

from app.db import engine


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _signup_and_auth(client: TestClient) -> dict[str, str]:
    slug = _unique("ledger")
    resp = client.post(
        "/auth/signup",
        json={
            "company_name": slug,
            "tenant_slug": slug,
            "email": "owner@ledger.example",
            "password": "correct-horse-battery-staple",
        },
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _set_company(client: TestClient, headers: dict[str, str], state_code: str = "27") -> None:
    resp = client.put(
        "/company",
        headers=headers,
        json={
            "legal_name": "Ledger Pvt Ltd",
            "gstin": "27AAAAA0000A1Z5",
            "state_code": state_code,
            "address": "Mumbai, Maharashtra",
        },
    )
    assert resp.status_code == 200, resp.text


def _create_customer(client: TestClient, headers: dict[str, str], state_code: str = "27") -> str:
    resp = client.post(
        "/customers",
        headers=headers,
        json={"name": "Buyer", "gstin": None, "state_code": state_code, "billing_address": "x"},
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def _create_item(client: TestClient, headers: dict[str, str], rate_bps: int = 1800) -> str:
    resp = client.post(
        "/items",
        headers=headers,
        json={
            "name": "Widget",
            "hsn_sac": "8471",
            "unit": "unit",
            "unit_price_paise": 100_000,
            "gst_rate_bps": rate_bps,
        },
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def _create_and_issue_invoice(
    client: TestClient, headers: dict[str, str], customer_id: str, item_id: str
) -> dict:
    create_resp = client.post(
        "/invoices",
        headers=headers,
        json={"customer_id": customer_id, "lines": [{"item_id": item_id, "quantity": 1}]},
    )
    assert create_resp.status_code == 201, create_resp.text
    invoice_id = create_resp.json()["id"]
    issue_resp = client.post(f"/invoices/{invoice_id}/issue", headers=headers)
    assert issue_resp.status_code == 200, issue_resp.text
    return issue_resp.json()


def _trial_balance_nets_to_zero(client: TestClient, headers: dict[str, str]) -> None:
    resp = client.get("/reports/trial-balance", headers=headers)
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    total_debit = sum(r["debit_paise"] for r in rows)
    total_credit = sum(r["credit_paise"] for r in rows)
    assert total_debit == total_credit


def test_issuing_invoice_posts_a_balanced_journal(client: TestClient) -> None:
    headers = _signup_and_auth(client)
    _set_company(client, headers)
    customer_id = _create_customer(client, headers)
    item_id = _create_item(client, headers)

    invoice = _create_and_issue_invoice(client, headers, customer_id, item_id)
    assert invoice["grand_total_paise"] == 118_000  # Rs 1000 + 18% GST

    resp = client.get("/reports/trial-balance", headers=headers)
    rows = {r["account_code"]: r for r in resp.json()}
    assert rows["1100"]["debit_paise"] == 118_000  # Accounts Receivable
    assert rows["4000"]["credit_paise"] == 100_000  # Sales Revenue
    assert rows["2100"]["credit_paise"] == 9_000  # Output CGST
    assert rows["2200"]["credit_paise"] == 9_000  # Output SGST
    _trial_balance_nets_to_zero(client, headers)


def test_cancel_reverses_the_issue_journal_exactly(client: TestClient) -> None:
    headers = _signup_and_auth(client)
    _set_company(client, headers)
    customer_id = _create_customer(client, headers)
    item_id = _create_item(client, headers)

    invoice = _create_and_issue_invoice(client, headers, customer_id, item_id)
    cancel_resp = client.post(f"/invoices/{invoice['id']}/cancel", headers=headers)
    assert cancel_resp.status_code == 200, cancel_resp.text

    resp = client.get("/reports/trial-balance", headers=headers)
    rows = {r["account_code"]: r for r in resp.json()}
    # Every account that moved on issue is now fully reversed back to zero net.
    for code in ("1100", "4000", "2100", "2200", "2300"):
        assert rows[code]["debit_paise"] == rows[code]["credit_paise"]
    _trial_balance_nets_to_zero(client, headers)


def test_partial_then_full_payment_against_an_invoice(client: TestClient) -> None:
    headers = _signup_and_auth(client)
    _set_company(client, headers)
    customer_id = _create_customer(client, headers)
    item_id = _create_item(client, headers)

    invoice = _create_and_issue_invoice(client, headers, customer_id, item_id)
    grand_total = invoice["grand_total_paise"]

    partial = client.post(
        "/payments",
        headers=headers,
        json={"invoice_id": invoice["id"], "amount_paise": grand_total // 2, "method": "upi"},
    )
    assert partial.status_code == 201, partial.text

    # overpaying the remaining balance is rejected
    overpay = client.post(
        "/payments",
        headers=headers,
        json={"invoice_id": invoice["id"], "amount_paise": grand_total, "method": "upi"},
    )
    assert overpay.status_code == 400

    remaining = grand_total - grand_total // 2
    final = client.post(
        "/payments",
        headers=headers,
        json={"invoice_id": invoice["id"], "amount_paise": remaining, "method": "bank_transfer"},
    )
    assert final.status_code == 201, final.text

    # fully paid now, so it drops off the ageing report
    ageing = client.get("/reports/receivables-ageing", headers=headers)
    assert ageing.status_code == 200
    assert invoice["id"] not in {row["invoice_id"] for row in ageing.json()}

    _trial_balance_nets_to_zero(client, headers)


def test_unpaid_invoice_shows_up_in_receivables_ageing(client: TestClient) -> None:
    headers = _signup_and_auth(client)
    _set_company(client, headers)
    customer_id = _create_customer(client, headers)
    item_id = _create_item(client, headers)

    invoice = _create_and_issue_invoice(client, headers, customer_id, item_id)

    ageing = client.get("/reports/receivables-ageing", headers=headers)
    assert ageing.status_code == 200
    rows = {row["invoice_id"]: row for row in ageing.json()}
    assert invoice["id"] in rows
    assert rows[invoice["id"]]["outstanding_paise"] == invoice["grand_total_paise"]
    assert rows[invoice["id"]]["bucket"] == "0-30"


def test_concurrent_issuance_never_duplicates_a_number(client: TestClient) -> None:
    headers = _signup_and_auth(client)
    _set_company(client, headers)
    customer_id = _create_customer(client, headers)
    item_id = _create_item(client, headers)

    draft_ids = []
    for _ in range(8):
        create_resp = client.post(
            "/invoices",
            headers=headers,
            json={"customer_id": customer_id, "lines": [{"item_id": item_id, "quantity": 1}]},
        )
        draft_ids.append(create_resp.json()["id"])

    results: list[int] = []
    lock = threading.Lock()

    def issue(invoice_id: str) -> None:
        resp = client.post(f"/invoices/{invoice_id}/issue", headers=headers)
        assert resp.status_code == 200, resp.text
        with lock:
            results.append(resp.json()["number"])

    threads = [threading.Thread(target=issue, args=(iid,)) for iid in draft_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == list(range(1, 9))  # gapless, no duplicates


def test_ledger_entry_rows_are_append_only(client: TestClient) -> None:
    slug = _unique("appendonly")
    signup_resp = client.post(
        "/auth/signup",
        json={
            "company_name": slug,
            "tenant_slug": slug,
            "email": "owner@appendonly.example",
            "password": "correct-horse-battery-staple",
        },
    )
    assert signup_resp.status_code == 201, signup_resp.text
    headers = {"Authorization": f"Bearer {signup_resp.json()['access_token']}"}

    _set_company(client, headers)
    customer_id = _create_customer(client, headers)
    item_id = _create_item(client, headers)
    _create_and_issue_invoice(client, headers, customer_id, item_id)

    def set_tenant(conn: Connection, tid: object) -> None:
        conn.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tid)})

    with engine.connect() as conn:
        tenant_id = conn.execute(
            text("SELECT id FROM tenant WHERE slug = :s"), {"s": slug}
        ).scalar_one()
        set_tenant(conn, tenant_id)
        entry_id = conn.execute(text("SELECT id FROM ledger_entry LIMIT 1")).scalar_one()

        with pytest.raises(DBAPIError):
            conn.execute(
                text("UPDATE ledger_entry SET debit_paise = 0 WHERE id = :id"),
                {"id": str(entry_id)},
            )
        conn.rollback()

        set_tenant(conn, tenant_id)
        with pytest.raises(DBAPIError):
            conn.execute(text("DELETE FROM ledger_entry WHERE id = :id"), {"id": str(entry_id)})
        conn.rollback()
