import uuid

from fastapi.testclient import TestClient


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _signup_and_auth(client: TestClient) -> dict[str, str]:
    slug = _unique("acme")
    resp = client.post(
        "/auth/signup",
        json={
            "company_name": slug,
            "tenant_slug": slug,
            "email": "owner@acme.example",
            "password": "correct-horse-battery-staple",
        },
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _set_company(client: TestClient, headers: dict[str, str], state_code: str) -> None:
    resp = client.put(
        "/company",
        headers=headers,
        json={
            "legal_name": "Acme Pvt Ltd",
            "gstin": "27AAAAA0000A1Z5",
            "state_code": state_code,
            "address": "Mumbai, Maharashtra",
        },
    )
    assert resp.status_code == 200, resp.text


def _create_customer(client: TestClient, headers: dict[str, str], state_code: str) -> str:
    resp = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "Globex Corp",
            "gstin": None,
            "state_code": state_code,
            "billing_address": "Somewhere",
        },
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def _create_item(client: TestClient, headers: dict[str, str], rate_bps: int = 1800) -> str:
    resp = client.post(
        "/items",
        headers=headers,
        json={
            "name": "Consulting hours",
            "hsn_sac": "9983",
            "unit": "hour",
            "unit_price_paise": 100_000,  # Rs 1000.00
            "gst_rate_bps": rate_bps,
        },
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def test_intra_state_invoice_issue_cancel_and_pdf(client: TestClient) -> None:
    headers = _signup_and_auth(client)
    _set_company(client, headers, state_code="27")
    customer_id = _create_customer(client, headers, state_code="27")
    item_id = _create_item(client, headers, rate_bps=1800)

    create_resp = client.post(
        "/invoices",
        headers=headers,
        json={"customer_id": customer_id, "lines": [{"item_id": item_id, "quantity": 1}]},
    )
    assert create_resp.status_code == 201, create_resp.text
    invoice = create_resp.json()
    assert invoice["status"] == "draft"
    assert invoice["cgst_paise"] == 9_000
    assert invoice["sgst_paise"] == 9_000
    assert invoice["igst_paise"] == 0
    assert invoice["grand_total_paise"] == 118_000

    issue_resp = client.post(f"/invoices/{invoice['id']}/issue", headers=headers)
    assert issue_resp.status_code == 200, issue_resp.text
    issued = issue_resp.json()
    assert issued["status"] == "issued"
    assert issued["number"] == 1

    # a draft-only transition: issuing an already-issued invoice is rejected
    assert client.post(f"/invoices/{invoice['id']}/issue", headers=headers).status_code == 409

    pdf_resp = client.get(f"/invoices/{invoice['id']}/pdf", headers=headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content.startswith(b"%PDF")

    cancel_resp = client.post(f"/invoices/{invoice['id']}/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    # an issued-only transition: cancelling an already-cancelled invoice is rejected
    assert client.post(f"/invoices/{invoice['id']}/cancel", headers=headers).status_code == 409


def test_inter_state_invoice_charges_igst_only(client: TestClient) -> None:
    headers = _signup_and_auth(client)
    _set_company(client, headers, state_code="27")
    customer_id = _create_customer(client, headers, state_code="29")
    item_id = _create_item(client, headers, rate_bps=1800)

    resp = client.post(
        "/invoices",
        headers=headers,
        json={"customer_id": customer_id, "lines": [{"item_id": item_id, "quantity": 2}]},
    )
    assert resp.status_code == 201, resp.text
    invoice = resp.json()
    assert invoice["cgst_paise"] == 0
    assert invoice["sgst_paise"] == 0
    assert invoice["igst_paise"] == 36_000  # 18% of Rs 2,000.00
    assert invoice["grand_total_paise"] == 236_000


def test_invoice_numbering_is_gapless_per_tenant(client: TestClient) -> None:
    headers = _signup_and_auth(client)
    _set_company(client, headers, state_code="27")
    customer_id = _create_customer(client, headers, state_code="27")
    item_id = _create_item(client, headers)

    numbers = []
    for _ in range(3):
        create_resp = client.post(
            "/invoices",
            headers=headers,
            json={"customer_id": customer_id, "lines": [{"item_id": item_id, "quantity": 1}]},
        )
        invoice_id = create_resp.json()["id"]
        issue_resp = client.post(f"/invoices/{invoice_id}/issue", headers=headers)
        numbers.append(issue_resp.json()["number"])

    assert numbers == [1, 2, 3]


def test_preview_matches_create_and_writes_nothing(client: TestClient) -> None:
    headers = _signup_and_auth(client)
    _set_company(client, headers, state_code="27")
    customer_id = _create_customer(client, headers, state_code="29")  # inter-state
    item_id = _create_item(client, headers, rate_bps=1800)

    body = {"customer_id": customer_id, "lines": [{"item_id": item_id, "quantity": 2}]}

    preview_resp = client.post("/invoices/preview", headers=headers, json=body)
    assert preview_resp.status_code == 200, preview_resp.text
    preview = preview_resp.json()
    assert "id" not in preview  # nothing persisted, no invoice id exists
    assert preview["igst_paise"] == 36_000
    assert preview["grand_total_paise"] == 236_000

    create_resp = client.post("/invoices", headers=headers, json=body)
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    for field in ("subtotal_paise", "cgst_paise", "sgst_paise", "igst_paise", "grand_total_paise"):
        assert preview[field] == created[field]

    # a second preview of the same body must still produce no new invoice
    list_resp = client.get("/invoices", headers=headers)
    assert len(list_resp.json()) == 1  # only the one from create_invoice above


def test_invoice_requires_company_profile_first(client: TestClient) -> None:
    headers = _signup_and_auth(client)
    customer_id = _create_customer(client, headers, state_code="27")
    item_id = _create_item(client, headers)

    resp = client.post(
        "/invoices",
        headers=headers,
        json={"customer_id": customer_id, "lines": [{"item_id": item_id, "quantity": 1}]},
    )
    assert resp.status_code == 400
