"""Canonical attestation binding message for wallet signatures (Step 2)."""

from __future__ import annotations

from datetime import datetime, timezone


def format_challenge_timestamp(when: datetime) -> str:
    """UTC instant as `YYYY-MM-DDTHH:MM:SSZ` (no subseconds)."""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    when = when.astimezone(timezone.utc)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_challenge_message(
    *,
    wallet_address: str,
    nonce: str,
    timestamp_utc: datetime,
) -> str:
    """
    Exact string the user must sign (after any wallet-specific wrapping).

    Wallets like MetaMask use `personal_sign`, which applies the EIP-191
    "Ethereum signed message" prefix to these UTF-8 bytes. Step 4 verification
    must recover the signer with the same convention.
    """
    ts = format_challenge_timestamp(timestamp_utc)
    return (
        "I authorize Plaid to issue an attestation binding this wallet to my verified identity. "
        f"Wallet: {wallet_address}. Nonce: {nonce}. Timestamp: {ts}"
    )
