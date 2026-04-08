"""Claims provider: maps Plaid verification data to privacy-preserving tiers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class TierClaims:
    identityVerified: bool
    kycStatus: str
    incomeRange: str
    liquidBalanceRange: str
    authorizedSpendingLimit: str
    authorizedSpendingWindow: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "identityVerified": self.identityVerified,
            "kycStatus": self.kycStatus,
            "incomeRange": self.incomeRange,
            "liquidBalanceRange": self.liquidBalanceRange,
            "authorizedSpendingLimit": self.authorizedSpendingLimit,
            "authorizedSpendingWindow": self.authorizedSpendingWindow,
        }


class ClaimsProvider(Protocol):
    def derive_claims(self, *, plaid_accounts_summary: dict[str, Any]) -> TierClaims: ...


class MockClaimsProvider:
    """
    Placeholder tiers.

    External dependency note: real tiers require additional Plaid products/endpoints
    (Identity/Income/Assets/etc.) and are not derivable from /accounts/get alone.
    """

    def derive_claims(self, *, plaid_accounts_summary: dict[str, Any]) -> TierClaims:  # noqa: ARG002
        return TierClaims(
            identityVerified=True,
            kycStatus="cleared",
            incomeRange="100k-150k",
            liquidBalanceRange="50k-100k",
            authorizedSpendingLimit="5000",
            authorizedSpendingWindow="monthly",
        )

