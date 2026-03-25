"""
Production Plaid integration (not implemented).

A real `VerificationProvider` would:

1. Use the official Plaid server SDK (`plaid-python`) with `PLAID_CLIENT_ID`,
   `PLAID_SECRET`, and `PLAID_ENV`.
2. Call product endpoints appropriate to your Plaid contract — for example
   Identity, Income verification, Liabilities, Assets, Balance — using each
   `access_token` from the create request.
3. Map structured Plaid responses into `VerifiedFinancialProfile` tier strings
   (`income_range`, `liquid_balance_range`, etc.) according to your risk policy.

This cannot be completed without **your** Plaid developer account, approved
products, and legal/compliance review of what may be disclosed in an
attestation. The mock provider exercises the rest of the pipeline end-to-end.
"""

from __future__ import annotations
