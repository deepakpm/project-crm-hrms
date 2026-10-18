import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

from app.db import engine


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _set_tenant(conn: Connection, tenant_id: object) -> None:
    conn.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)})


def _signup(client: TestClient, slug: str, email: str) -> dict[str, str]:
    resp = client.post(
        "/auth/signup",
        json={
            "company_name": slug,
            "tenant_slug": slug,
            "email": email,
            "password": "correct-horse-battery-staple",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_api_cannot_see_other_tenants_users(client: TestClient) -> None:
    slug_a, slug_b = _unique("acme"), _unique("globex")
    tokens_a = _signup(client, slug_a, "owner@a.example")
    tokens_b = _signup(client, slug_b, "owner@b.example")

    resp_a = client.get("/users", headers={"Authorization": f"Bearer {tokens_a['access_token']}"})
    resp_b = client.get("/users", headers={"Authorization": f"Bearer {tokens_b['access_token']}"})

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    assert {u["email"] for u in resp_a.json()} == {"owner@a.example"}
    assert {u["email"] for u in resp_b.json()} == {"owner@b.example"}


def test_login_and_refresh_round_trip(client: TestClient) -> None:
    slug = _unique("umbrella")
    _signup(client, slug, "owner@umbrella.example")

    login_resp = client.post(
        "/auth/login",
        json={
            "tenant_slug": slug,
            "email": "owner@umbrella.example",
            "password": "correct-horse-battery-staple",
        },
    )
    assert login_resp.status_code == 200, login_resp.text
    tokens = login_resp.json()

    refresh_resp = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh_resp.status_code == 200, refresh_resp.text

    # the rotated-out refresh token must no longer work
    reuse_resp = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse_resp.status_code == 401


def test_sql_rls_blocks_cross_tenant_read_and_write(client: TestClient) -> None:
    slug_a, slug_b = _unique("initech"), _unique("hooli")
    _signup(client, slug_a, "owner@initech.example")
    _signup(client, slug_b, "owner@hooli.example")

    with engine.connect() as conn:
        tenant_a_id = conn.execute(
            text("SELECT id FROM tenant WHERE slug = :s"), {"s": slug_a}
        ).scalar_one()
        tenant_b_id = conn.execute(
            text("SELECT id FROM tenant WHERE slug = :s"), {"s": slug_b}
        ).scalar_one()
        conn.rollback()

    # reading app_user as tenant A must not surface tenant B's row, even though
    # the connection here is the same restricted role the running app uses.
    with engine.connect() as conn:
        _set_tenant(conn, tenant_a_id)
        rows = conn.execute(text("SELECT email FROM app_user")).fetchall()
        assert {r[0] for r in rows} == {"owner@initech.example"}
        conn.rollback()

    # writing a row stamped with tenant B's id while scoped to tenant A must be
    # rejected by the policy's WITH CHECK, not merely hidden afterwards.
    with engine.connect() as conn:
        _set_tenant(conn, tenant_a_id)
        with pytest.raises(DBAPIError):
            conn.execute(
                text(
                    "INSERT INTO app_user (id, tenant_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tid, 'intruder@evil.test', 'x', 'member')"
                ),
                {"tid": str(tenant_b_id)},
            )
        conn.rollback()
