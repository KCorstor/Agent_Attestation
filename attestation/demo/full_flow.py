"""Run the full attestation + bid-rails story with fake Plaid (DEMO_MODE) — no real credentials."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from eth_account import Account
from eth_account.messages import encode_defunct

from attestation.demo.bid_rails import store as bid_demo_store
from attestation.steps.step4_issue import CredentialIssuer
from attestation.schemas import (
    CreateAttestationRequest,
    InitAttestationRequest,
    IssueAttestationRequest,
    TransactionIntent,
)
from attestation.steps.step1_init import initiate_attestation
from attestation.steps.step2_challenge import get_or_create_challenge
from attestation.steps.step3_verify import create_attestation_request


@contextmanager
def demo_mode_env() -> Any:
    """Enable fake Plaid responses + dummy API settings for the duration of the block."""
    prev = os.environ.get("DEMO_MODE")
    os.environ["DEMO_MODE"] = "1"
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("DEMO_MODE", None)
        else:
            os.environ["DEMO_MODE"] = prev


# Deterministic demo wallet (fake private key — dev only)
_DEMO_PK = "0x" + "1" * 64


async def run_full_demo(*, issuer: CredentialIssuer) -> dict[str, Any]:
    """
    End-to-end demo:
      Step 1 init → Step 2 challenge → sign (server-side fake wallet) →
      Step 3 verify → Step 4 issue → bid RFP + mock bids.

    Uses DEMO_MODE: no Plaid keys, no MetaMask.
    """
    steps: list[dict[str, Any]] = []

    with demo_mode_env():
        access_token = "access-demo-fake"
        acct = Account.from_key(_DEMO_PK)
        wallet = acct.address

        # Step 1
        init_body = InitAttestationRequest(access_token=access_token, wallet_address=wallet)
        init_out = await initiate_attestation(init_body)
        steps.append(
            {
                "id": "1_init",
                "title": "Step 1 — Init session (fake Plaid token)",
                "description": "Server validates token via DEMO_MODE (no real Plaid call).",
                "request": init_body.model_dump(mode="json"),
                "response": init_out.model_dump(mode="json"),
            }
        )

        # Step 2
        ch = get_or_create_challenge(init_out.session_id)
        steps.append(
            {
                "id": "2_challenge",
                "title": "Step 2 — Challenge message",
                "description": "Exact string a wallet would sign (here we sign with a demo key).",
                "request": {"session_id": init_out.session_id},
                "response": ch.model_dump(mode="json"),
            }
        )

        sig = Account.sign_message(encode_defunct(text=ch.message), private_key=_DEMO_PK).signature.hex()
        if not sig.startswith("0x"):
            sig = "0x" + sig
        steps.append(
            {
                "id": "2b_sign",
                "title": "Step 2b — Signature (simulated wallet)",
                "description": "In production the browser signs; demo signs server-side with a known fake key.",
                "request": {"message": ch.message},
                "response": {"signature": sig},
            }
        )

        # Step 3
        create_body = CreateAttestationRequest(
            access_token=access_token,
            wallet_address=wallet,
            message=ch.message,
            signature=sig,
        )
        create_out = await create_attestation_request(create_body)
        steps.append(
            {
                "id": "3_verify",
                "title": "Step 3 — Verify bundle",
                "description": "Plaid token + wallet signature checks pass.",
                "request": create_body.model_dump(mode="json"),
                "response": create_out.model_dump(mode="json"),
            }
        )

        # Step 4
        exp = datetime.now(timezone.utc) + timedelta(days=30)
        issue_body = IssueAttestationRequest(
            access_token=access_token,
            wallet_address=wallet,
            message=ch.message,
            signature=sig,
            expires_at=exp,
        )
        issue_out = await issuer.issue(issue_body)
        cred = issue_out.credential
        steps.append(
            {
                "id": "4_issue",
                "title": "Step 4 — Issue signed credential",
                "description": "Issuer signs claims with Ed25519 (attestation service key).",
                "request": issue_body.model_dump(mode="json"),
                "response": {"credential": cred},
            }
        )

        # Step 5 — bid rails
        rfp_body = {
            "resource_url": "https://pay.example.com/api/resource/402-demo",
            "transaction": TransactionIntent(
                amount_cents=5000,
                currency="USD",
                mcc="5411",
                description="Demo checkout — groceries",
                idempotency_key="demo-rfp-001",
            ).model_dump(mode="json"),
            "wallet_address": wallet,
            "agent_id": "agent-demo-001",
            "credential": cred,
            "include_full_credential": True,
            "credit_score_band": "720-850",
            "attestation_claims": cred.get("claims"),
            "protocol_hints": ["before_mpp_facilitator", "x402"],
        }
        rec = bid_demo_store.create_rfp(rfp_body)
        steps.append(
            {
                "id": "5_rfp",
                "title": "Step 5 — Broadcast RFP + mock issuer bids",
                "description": "Package includes transaction + trust signals; mock banks return bids.",
                "request": rfp_body,
                "response": {
                    "rfp_id": rec.rfp_id,
                    "package": rec.package,
                    "bids": [
                        {
                            "issuer_id": b.issuer_id,
                            "issuer_label": b.issuer_label,
                            "fee_bps": b.fee_bps,
                            "estimated_settlement_ms": b.estimated_settlement_ms,
                            "score": b.score,
                            "note": b.note,
                        }
                        for b in rec.bids
                    ],
                },
            }
        )

    return {
        "demo_mode": True,
        "fake_access_token": access_token,
        "fake_wallet_address": wallet,
        "steps": steps,
    }
