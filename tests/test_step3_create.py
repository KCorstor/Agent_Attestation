from __future__ import annotations

import os

import httpx
import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi.testclient import TestClient

import main as main_mod
from attestation.schemas import CreateAttestationRequest
from attestation.steps.step3_verify import create_attestation_request


def _mock_plaid_ok() -> httpx.MockTransport:
    return httpx.MockTransport(
        lambda r: httpx.Response(
            200,
            json={
                "accounts": [{"account_id": "a1"}],
                "item": {"item_id": "item_123", "institution_id": "ins_456"},
            },
        )
    )


@pytest.fixture
def plaid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLAID_CLIENT_ID", "c")
    monkeypatch.setenv("PLAID_SECRET", "s")
    monkeypatch.setenv("PLAID_ENV", "sandbox")


@pytest.mark.asyncio
async def test_create_attestation_request_ok(plaid_env: None) -> None:
    acct = Account.from_key("0x" + "1" * 64)
    msg = "hello world"
    sig = Account.sign_message(encode_defunct(text=msg), private_key="0x" + "1" * 64).signature.hex()
    body = CreateAttestationRequest(
        access_token="access-sandbox-x",
        wallet_address=acct.address,
        message=msg,
        signature=sig,
    )
    resp = await create_attestation_request(body, transport=_mock_plaid_ok())
    assert resp.verified_wallet_signature is True
    assert resp.recovered_address.lower() == acct.address.lower()
    assert resp.plaid_item_id == "item_123"
    assert resp.account_count == 1


@pytest.mark.asyncio
async def test_create_attestation_request_wallet_mismatch(plaid_env: None) -> None:
    acct = Account.from_key("0x" + "1" * 64)
    msg = "hello world"
    sig = Account.sign_message(encode_defunct(text=msg), private_key="0x" + "1" * 64).signature.hex()
    body = CreateAttestationRequest(
        access_token="access-sandbox-x",
        wallet_address="0x0000000000000000000000000000000000000001",
        message=msg,
        signature=sig,
    )
    with pytest.raises(ValueError, match="does not match"):
        await create_attestation_request(body, transport=_mock_plaid_ok())


def test_http_agent_attestation_create(plaid_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    async def patched(body):  # noqa: ANN001
        return await create_attestation_request(body, transport=_mock_plaid_ok())

    monkeypatch.setattr(main_mod, "create_attestation_request", patched)
    client = TestClient(main_mod.app)

    acct = Account.from_key("0x" + "2" * 64)
    msg = "hello world"
    sig = Account.sign_message(encode_defunct(text=msg), private_key="0x" + "2" * 64).signature.hex()
    r = client.post(
        "/agent_attestation/create",
        json={
            "access_token": "access-sandbox-x",
            "wallet_address": acct.address,
            "message": msg,
            "signature": sig,
        },
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["verified_wallet_signature"] is True

