from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi.testclient import TestClient

import main as main_mod
from attestation.issue_credential import CredentialIssuer
from attestation.schemas import IssueAttestationRequest


def _mock_plaid_ok() -> httpx.MockTransport:
    return httpx.MockTransport(
        lambda r: httpx.Response(
            200,
            json={
                "accounts": [{"account_id": "a1"}, {"account_id": "a2"}],
                "item": {"item_id": "item_123", "institution_id": "ins_456"},
            },
        )
    )


@pytest.mark.asyncio
async def test_issue_returns_signed_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    # Patch Plaid verification so no network is used.
    import attestation.step3_create as step3_mod

    async def fake_verify_access_token(*, base_url, client_id, secret, access_token, transport=None):  # noqa: ANN001, ARG001
        return {
            "accounts": [{"account_id": "a1"}, {"account_id": "a2"}],
            "item": {"item_id": "item_123", "institution_id": "ins_456"},
        }

    monkeypatch.setattr(step3_mod, "verify_access_token", fake_verify_access_token)

    issuer = CredentialIssuer()

    acct = Account.from_key("0x" + "3" * 64)
    msg = "hello world"
    sig = Account.sign_message(encode_defunct(text=msg), private_key="0x" + "3" * 64).signature.hex()

    exp = datetime.now(timezone.utc) + timedelta(days=30)
    body = IssueAttestationRequest(
        access_token="access-sandbox-x",
        wallet_address=acct.address,
        message=msg,
        signature=sig,
        expires_at=exp,
    )
    out = await issuer.issue(body)
    cred = out.credential
    assert cred["walletAddress"].lower() == acct.address.lower()
    assert cred["proof"]["type"] == "Ed25519Signature2020"
    assert cred["proof"]["proofValue"].startswith("z")
    assert "claims" in cred


def test_http_issue_and_did(monkeypatch: pytest.MonkeyPatch) -> None:
    import attestation.step3_create as step3_mod

    async def fake_verify_access_token(*, base_url, client_id, secret, access_token, transport=None):  # noqa: ANN001, ARG001
        return {
            "accounts": [{"account_id": "a1"}],
            "item": {"item_id": "item_123", "institution_id": "ins_456"},
        }

    monkeypatch.setattr(step3_mod, "verify_access_token", fake_verify_access_token)

    client = TestClient(main_mod.app)
    did = client.get("/.well-known/did.json")
    assert did.status_code == 200
    doc = did.json()
    assert doc["id"] == "did:web:attestation.local"

    acct = Account.from_key("0x" + "4" * 64)
    msg = "hello world"
    sig = Account.sign_message(encode_defunct(text=msg), private_key="0x" + "4" * 64).signature.hex()
    exp = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = client.post(
        "/agent_attestation/issue",
        json={
            "access_token": "access-sandbox-x",
            "wallet_address": acct.address,
            "message": msg,
            "signature": sig,
            "expires_at": exp,
        },
    )
    assert r.status_code == 200, r.text
    cred = r.json()["credential"]
    assert cred["issuedBy"] == "did:web:attestation.local"

