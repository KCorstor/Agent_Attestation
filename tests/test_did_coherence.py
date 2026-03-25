"""DID document public key matches issuer key used for signing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.testclient import TestClient

from agent_attestation.api import app
from agent_attestation.multibase import multibase_encode_ed25519_public_key


def test_did_multibase_matches_issuer() -> None:
    client = TestClient(app)
    did = client.get("/.well-known/did.json").json()
    multibase = did["verificationMethod"][0]["publicKeyMultibase"]

    exp = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    client.post(
        "/agent_attestation/create",
        json={
            "access_tokens": ["t"],
            "wallet_address": "0x0000000000000000000000000000000000000001",
            "scopes": ["identity"],
            "expires_at": exp,
        },
    )
    # Same seed as conftest: derive expected public multibase from that seed.
    sk = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("00" * 32))
    pub = sk.public_key().public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
    assert multibase == multibase_encode_ed25519_public_key(pub)
