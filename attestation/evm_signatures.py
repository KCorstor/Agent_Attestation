"""EVM personal_sign verification helpers (EIP-191)."""

from __future__ import annotations

from eth_account import Account
from eth_account.messages import encode_defunct


def recover_personal_sign_address(*, message: str, signature: str) -> str:
    """
    Recover the signing address for an EVM `personal_sign` message.

    Most EVM wallets (MetaMask, Rainbow, etc.) sign `EIP-191` wrapped bytes when using
    `personal_sign` / `eth_sign`. We model that with `encode_defunct(text=message)`.
    """
    return Account.recover_message(encode_defunct(text=message), signature=signature)


def addresses_match(a: str, b: str) -> bool:
    return a.strip().lower() == b.strip().lower()

