from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from attestation.schemas import InitAttestationRequest
from attestation.step1 import initiate_attestation
from attestation.step2 import get_or_create_challenge
from attestation.sessions import SessionStore
import main as main_mod


def _mock_plaid() -> httpx.MockTransport:
    return httpx.MockTransport(
        lambda r: httpx.Response(
            200,
            json={
                "accounts": [],
                "item": {"item_id": "i1", "institution_id": "ins_1"},
            },
        )
    )


@pytest.mark.asyncio
async def test_challenge_idempotent() -> None:
    store = SessionStore()
    body = InitAttestationRequest(
        access_token="access-sandbox-x",
        wallet_address="0xAbCdEf0123456789AbCdEf0123456789AbCdEf01",
    )
    resp = await initiate_attestation(
        body,
        session_store=store,
        transport=_mock_plaid(),
    )
    fixed_now = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)
    c1 = get_or_create_challenge(
        resp.session_id,
        session_store=store,
        now=fixed_now,
    )
    c2 = get_or_create_challenge(resp.session_id, session_store=store)
    assert c1.message == c2.message
    assert c1.nonce == c2.nonce
    assert c1.wallet_address.lower() == body.wallet_address.lower()


def test_challenge_unknown_session() -> None:
    with pytest.raises(LookupError):
        get_or_create_challenge("00000000-0000-0000-0000-000000000000", session_store=SessionStore())


def test_http_challenge_after_init(monkeypatch: pytest.MonkeyPatch) -> None:
    from attestation import step1 as step1_mod

    store = SessionStore()

    async def patched_init(body):  # noqa: ANN001
        return await step1_mod.initiate_attestation(
            body,
            session_store=store,
            transport=_mock_plaid(),
        )

    monkeypatch.setattr(main_mod, "initiate_attestation", patched_init)
    import attestation.sessions as sessions_mod

    monkeypatch.setattr(sessions_mod, "store", store)

    client = TestClient(main_mod.app)
    r = client.post(
        "/attestation/init",
        json={
            "access_token": "access-sandbox-x",
            "wallet_address": "0x0000000000000000000000000000000000000001",
        },
    )
    assert r.status_code == 200
    sid = r.json()["session_id"]

    r2 = client.get(f"/attestation/sessions/{sid}/challenge")
    assert r2.status_code == 200
    data = r2.json()
    assert data["session_id"] == sid
    assert "message" in data
    assert data["nonce"]
    assert "signing_note" in data

    r3 = client.get(f"/attestation/sessions/{sid}/challenge")
    assert r3.json()["message"] == data["message"]


def test_http_challenge_404() -> None:
    client = TestClient(main_mod.app)
    r = client.get("/attestation/sessions/00000000-0000-0000-0000-000000000000/challenge")
    assert r.status_code == 404
