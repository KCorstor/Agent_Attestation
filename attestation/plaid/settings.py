"""Load Plaid credentials from the environment (never hardcode secrets)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PlaidSettings:
    client_id: str
    secret: str
    base_url: str


def is_demo_mode() -> bool:
    return os.environ.get("DEMO_MODE", "").strip().lower() in ("1", "true", "yes")


def load_plaid_settings() -> PlaidSettings:
    if is_demo_mode():
        return PlaidSettings(
            client_id="demo",
            secret="demo",
            base_url="https://sandbox.plaid.com",
        )

    client_id = os.environ.get("PLAID_CLIENT_ID", "").strip()
    secret = os.environ.get("PLAID_SECRET", "").strip()
    env = os.environ.get("PLAID_ENV", "sandbox").strip().lower()

    if not client_id or not secret:
        raise RuntimeError(
            "Set PLAID_CLIENT_ID and PLAID_SECRET (e.g. from .env). "
            "Do not commit API secrets to git."
        )

    hosts = {
        "sandbox": "https://sandbox.plaid.com",
        "development": "https://development.plaid.com",
        "production": "https://production.plaid.com",
    }
    base_url = hosts.get(env, hosts["sandbox"])
    return PlaidSettings(client_id=client_id, secret=secret, base_url=base_url)
