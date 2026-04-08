"""Demo: build an RFP package and simulate issuer bids (not production banking)."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


def _iso(dt: datetime | None = None) -> str:
    d = dt or datetime.now(timezone.utc)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class DemoBid:
    issuer_id: str
    issuer_label: str
    fee_bps: int
    estimated_settlement_ms: int
    score: float
    note: str


def mock_bids_for_rfp(rfp_id: str, amount_cents: int) -> list[DemoBid]:
    """Deterministic-ish fake bids for the demo UI."""
    seed = int(hashlib.sha256(rfp_id.encode()).hexdigest()[:8], 16)
    base = 15 + (seed % 25)  # 15–39 bps
    return [
        DemoBid(
            issuer_id="issuer_demo_northwind",
            issuer_label="Northwind Issuing (demo)",
            fee_bps=base,
            estimated_settlement_ms=800 + (seed % 400),
            score=0.72 + (seed % 20) / 100,
            note="Prefers retail MCC; instant settle mock",
        ),
        DemoBid(
            issuer_id="issuer_demo_contoso",
            issuer_label="Contoso Card Program (demo)",
            fee_bps=base + 8,
            estimated_settlement_ms=1200 + (seed % 600),
            score=0.68 + (seed % 15) / 100,
            note="Higher fee, broader MCC tolerance (mock)",
        ),
        DemoBid(
            issuer_id="issuer_demo_fabrikam",
            issuer_label="Fabrikam RTP Bridge (demo)",
            fee_bps=max(10, base - 5),
            estimated_settlement_ms=400 + (seed % 200),
            score=0.75 + (seed % 10) / 100,
            note="Optimized for low-latency (mock)",
        ),
    ]


@dataclass
class RfpRecord:
    rfp_id: str
    created_at: str
    package: dict[str, Any]
    bids: list[DemoBid] = field(default_factory=list)


class BidDemoStore:
    def __init__(self) -> None:
        self._rfps: dict[str, RfpRecord] = {}

    def create_rfp(self, body: dict[str, Any]) -> RfpRecord:
        rfp_id = str(uuid.uuid4())
        now_dt = datetime.now(timezone.utc)
        now = _iso(now_dt)
        tx = body.get("transaction") or {}
        amount = int(tx.get("amount_cents") or 0)

        credential = body.get("credential")
        cred_ref: str | None = None
        if credential is not None:
            payload = json.dumps(credential, sort_keys=True, separators=(",", ":")).encode()
            cred_ref = "sha256:" + hashlib.sha256(payload).hexdigest()

        exp_raw = body.get("expires_at")
        if not exp_raw:
            exp_raw = _iso(now_dt + timedelta(minutes=15))

        package: dict[str, Any] = {
            "rfp_version": "0.1-demo",
            "rfp_id": rfp_id,
            "created_at": now,
            "expires_at": exp_raw,
            "payment_context": {
                "trigger": "http_402",
                "resource_url": body.get("resource_url"),
                "protocol_hints": body.get("protocol_hints") or ["before_mpp_facilitator"],
            },
            "transaction": tx,
            "agent": {
                "wallet_address": body.get("wallet_address"),
                "agent_id": body.get("agent_id"),
                "credential_ref": cred_ref,
                "credential_embedded": credential if body.get("include_full_credential") else None,
            },
            "underwriting": {
                "credit_score_band": body.get("credit_score_band"),
                "attestation_claims": body.get("attestation_claims"),
                "notes": body.get("underwriting_notes"),
            },
            "policy": {
                "max_fee_bps": body.get("max_fee_bps"),
                "preferred_rails": body.get("preferred_rails") or [],
            },
        }

        bids = mock_bids_for_rfp(rfp_id, amount)
        rec = RfpRecord(rfp_id=rfp_id, created_at=now, package=package, bids=bids)
        self._rfps[rfp_id] = rec
        return rec

    def get(self, rfp_id: str) -> RfpRecord | None:
        return self._rfps.get(rfp_id)


store = BidDemoStore()
