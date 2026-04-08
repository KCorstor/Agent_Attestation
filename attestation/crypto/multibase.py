"""Multibase `z` + base58btc helpers for DID keys and proofValue."""

from __future__ import annotations

import base58


def mb58_encode(raw: bytes) -> str:
    return "z" + base58.b58encode(raw).decode("ascii")


def mb58_decode(s: str) -> bytes:
    if not s.startswith("z"):
        raise ValueError("expected multibase z-prefix")
    return base58.b58decode(s[1:])

