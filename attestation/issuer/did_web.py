"""Serve a minimal did:web document for verifiers to fetch the public key."""

from __future__ import annotations

from typing import Any

from attestation.crypto.multibase import mb58_encode
from attestation.issuer.config import issuer_did, verification_method_id


def build_did_document(public_key_ed25519_32: bytes) -> dict[str, Any]:
    return {
        "@context": "https://www.w3.org/ns/did/v1",
        "id": issuer_did(),
        "verificationMethod": [
            {
                "id": verification_method_id(),
                "type": "Ed25519VerificationKey2020",
                "controller": issuer_did(),
                "publicKeyMultibase": mb58_encode(public_key_ed25519_32),
            }
        ],
        "assertionMethod": [verification_method_id()],
    }

