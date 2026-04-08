"""Tests for auction borrower packet sketch."""

from __future__ import annotations

import json

from attestation.demo.auction_borrower_packet import (
    AuctionBorrowerPacketV1,
    TierClaimsSnapshot,
    build_minimal_packet,
)
from attestation.issuer.claims_provider import MockClaimsProvider, TierClaims
from attestation.schemas import BidRfpRequest, TransactionIntent


def test_build_minimal_packet_aligns_tier_claims() -> None:
    claims = MockClaimsProvider().derive_claims(plaid_accounts_summary={})
    tx = TransactionIntent(amount_cents=49_99, currency="USD", mcc="5411")
    p = build_minimal_packet(
        wallet_address="0x" + "a" * 40,
        transaction=tx,
        claims=claims,
        credit_score_band="680-719",
        credential_ref="sha256:abc",
    )
    assert p.attestation_claims.kycStatus == "cleared"
    assert p.credit.score_band == "680-719"
    assert p.income_liquidity.income_range == claims.incomeRange
    assert p.subject.credential_ref == "sha256:abc"


def test_into_bid_rfp_request_fields_round_trip() -> None:
    claims = TierClaims(
        identityVerified=True,
        kycStatus="cleared",
        incomeRange="50k-75k",
        liquidBalanceRange="10k-25k",
        authorizedSpendingLimit="2500",
        authorizedSpendingWindow="monthly",
    )
    packet = build_minimal_packet(
        wallet_address="0x" + "b" * 40,
        transaction=TransactionIntent(amount_cents=1000),
        claims=claims,
    )
    fields = packet.into_bid_rfp_request_fields()
    req = BidRfpRequest(transaction=TransactionIntent(**fields["transaction"]), **{k: v for k, v in fields.items() if k != "transaction"})
    assert req.wallet_address == packet.subject.wallet_address
    assert req.attestation_claims == packet.attestation_claims.model_dump()


def test_sorted_json_stable_for_same_payload() -> None:
    claims = MockClaimsProvider().derive_claims(plaid_accounts_summary={})
    packet = build_minimal_packet(
        wallet_address="0x" + "c" * 40,
        transaction=TransactionIntent(amount_cents=1),
        claims=claims,
    )
    # Freeze time field so two dumps match
    fixed = packet.model_copy(update={"generated_at": packet.generated_at})
    s1 = fixed.model_dump_json_sorted()
    s2 = fixed.model_dump_json_sorted()
    assert s1 == s2
    roundtrip = AuctionBorrowerPacketV1.model_validate(json.loads(s1))
    assert roundtrip.schema_version == "auction.borrower_packet.v1"


def test_tier_snapshot_from_credential_claims_dict() -> None:
    claims = MockClaimsProvider().derive_claims(plaid_accounts_summary={})
    snap = TierClaimsSnapshot.from_credential_claims(claims.to_dict())
    assert snap.identityVerified is True
