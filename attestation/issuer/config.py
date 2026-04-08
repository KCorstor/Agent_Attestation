"""Issuer configuration (DID + signing key seed)."""

from __future__ import annotations

import os


def issuer_did() -> str:
    # In production this would be something like did:web:attestation.yourdomain.com
    return os.environ.get("ATTESTATION_ISSUER_DID", "did:web:attestation.local").strip()


def verification_method_id() -> str:
    return f"{issuer_did()}#key-1"


def ed25519_seed_hex() -> str | None:
    """
    Optional 32-byte seed hex for stable signing keys across restarts.

    If unset, the server generates a random key at startup (OK for local dev, not production).
    """
    v = os.environ.get("ATTESTATION_ED25519_SEED_HEX")
    return v.strip() if v else None

