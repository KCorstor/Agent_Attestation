"""Deterministic JSON bytes for signing (simplified VC canonicalization)."""

from __future__ import annotations

import json
from typing import Any


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    """
    Serialize payload to stable UTF-8 bytes:
    - dict keys sorted recursively
    - compact separators
    - ensure_ascii=False

    This is sufficient for this project’s signing/verifying consistency.
    Full VC-LD signature suites may require RDF Dataset Canonicalization instead.
    """

    def sort_obj(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: sort_obj(obj[k]) for k in sorted(obj.keys())}
        if isinstance(obj, list):
            return [sort_obj(x) for x in obj]
        return obj

    ordered = sort_obj(payload)
    s = json.dumps(ordered, separators=(",", ":"), ensure_ascii=False)
    return s.encode("utf-8")

