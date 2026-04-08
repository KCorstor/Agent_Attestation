from __future__ import annotations

import os

import httpx
import pytest
from fastapi.testclient import TestClient

from attestation.schemas import InitAttestationRequest
from attestation.steps.session_store import SessionStore
from attestation.steps.step1_init import initiate_attestation
import main as main_mod


def _mock_plaid_success() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/accounts/get")
        return httpx.Response(
            200,
            json={
                "accounts": [{"account_id": "acc_1"}, {"account_id": "acc_2"}],
                "item": {
                    "item_id": "item_123",
                    "institution_id": "ins_456",
                },
            },
        )

    return httpx.MockTransport(handler)


@pytest.fixture
def plaid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLAID_CLIENT_ID", "test_client")
    monkeypatch.setenv("PLAID_SECRET", "test_secret")
    monkeypatch.setenv("PLAID_ENV", "sandbox")


@pytest.mark.asyncio
async def test_initiate_creates_session(plaid_env: None) -> None:
    store = SessionStore()
    body = InitAttestationRequest(
        access_token="access-sandbox-abc",
        wallet_address="0x0000000000000000000000000000000000000001",
    )
    resp = await initiate_attestation(
        body,
        session_store=store,
        transport=_mock_plaid_success(),
    )
    assert resp.session_id
    assert resp.status == "awaiting_wallet_signature"
    assert resp.account_count == 2
    assert resp.plaid_item_id == "item_123"
    assert resp.plaid_institution_id == "ins_456"

    sess = store.get(resp.session_id)
    assert sess is not None
    assert sess.access_token == "access-sandbox-abc"


@pytest.mark.asyncio
async def test_plaid_error_propagates(plaid_env: None) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error_code": "INVALID_ACCESS_TOKEN", "error_message": "bad token"},
        )

    transport = httpx.MockTransport(handler)
    body = InitAttestationRequest(
        access_token="bad",
        wallet_address="0x0000000000000000000000000000000000000001",
    )
    with pytest.raises(ValueError, match="Plaid rejected"):
        await initiate_attestation(body, session_store=SessionStore(), transport=transport)


def test_http_init_endpoint(plaid_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    transport = httpx.MockTransport(
        lambda r: httpx.Response(
            200,
            json={
                "accounts": [],
                "item": {"item_id": "i1", "institution_id": "ins_1"},
            },
        )
    )

    async def patched_init(body):  # noqa: ANN001
        return await initiate_attestation(
            body,
            session_store=SessionStore(),
            transport=transport,
        )

    monkeypatch.setattr(main_mod, "initiate_attestation", patched_init)
    client = TestClient(main_mod.app)
    r = client.post(
        "/attestation/init",
        json={
            "access_token": "access-sandbox-xyz",
            "wallet_address": "0xAbCdEf0123456789AbCdEf0123456789AbCdEf01",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["plaid_verified"] is True
    assert data["status"] == "awaiting_wallet_signature"


def test_invalid_wallet_rejected(plaid_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    async def never_called(body):  # noqa: ANN001
        raise AssertionError("should not reach Plaid")

    monkeypatch.setattr(main_mod, "initiate_attestation", never_called)
    client = TestClient(main_mod.app)
    r = client.post(
        "/attestation/init",
        json={
            "access_token": "access-sandbox-xyz",
            "wallet_address": "not-a-wallet",
        },
    )
    assert r.status_code == 422
