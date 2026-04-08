"""Ed25519 signing key management for issuing credentials."""

from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from attestation.issuer.config import ed25519_seed_hex


def load_or_generate_private_key() -> Ed25519PrivateKey:
    seed = ed25519_seed_hex()
    if seed:
        raw = bytes.fromhex(seed)
        if len(raw) != 32:
            raise ValueError("ATTESTATION_ED25519_SEED_HEX must decode to 32 bytes (64 hex chars)")
        return Ed25519PrivateKey.from_private_bytes(raw)
    return Ed25519PrivateKey.generate()


def public_key_raw_32(sk: Ed25519PrivateKey) -> bytes:
    return sk.public_key().public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)

