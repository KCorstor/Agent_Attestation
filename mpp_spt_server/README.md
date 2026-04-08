# MPP test server (Stripe SPT)

Minimal [Machine Payments Protocol](https://mpp.dev) server using the **Stripe Shared Payment Token** path, following [Stripe — MPP payments](https://docs.stripe.com/payments/machine/mpp).

## Prerequisites

1. **Node.js 22+** (`mppx` / dependencies expect it; Node 20 may warn or fail.)
2. **Stripe Test mode** API secret from [Dashboard → API keys](https://dashboard.stripe.com/test/apikeys).
3. **Machine payments** enabled for your Stripe account — request access via the [Machine payments signup](https://docs.stripe.com/payments/machine#sign-up) flow described in Stripe’s docs.
4. A stable `**MPP_SECRET_KEY`** (HMAC binding for challenges). Generate once:
  ```bash
   openssl rand -base64 32
  ```

## Setup

```bash
cd mpp_spt_server
cp .env.example .env
# Edit .env: STRIPE_SECRET_KEY, MPP_SECRET_KEY, and optionally MPP_MOCK_* (see below)
npm install
npm start
```

Default URL: `http://127.0.0.1:4242`

## Quick test (402 only)

```bash
curl -i http://127.0.0.1:4242/paid
```

You should get **HTTP 402** and a JSON problem body (see Stripe’s “Test your endpoint” section).

Check which **mock seller binding** the server expects (must match the agent):

```bash
curl -s http://127.0.0.1:4242/mock-spt/seller | jq
```

## Mock SPT credentials (`mock_spt_env.mjs`)

Server and agent share `**mock_spt_env.mjs**` so the **MPP challenge `networkId`** matches `**seller_details.network_id**`, and `**seller_details.external_id**` matches when minting the SPT via Stripe’s [test helper](https://docs.stripe.com/agentic-commerce/concepts/shared-payment-tokens).


| Variable                       | Role                                                                                                       |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| `MPP_MOCK_SELLER_NETWORK_ID`   | Same as MPP `stripe.charge` `networkId` (default `internal`). You can set `STRIPE_MPP_NETWORK_ID` instead. |
| `MPP_MOCK_SELLER_EXTERNAL_ID`  | **Seller** id sent to Stripe when creating the SPT (`seller_details.external_id`).                         |
| `MPP_MOCK_GRANTOR_EXTERNAL_ID` | Mock **issuing bank / auction winner** id on the MPP credential + PI metadata.                             |
| `MPP_MOCK_GRANTOR_LABEL`       | Human-readable label for logs.                                                                             |
| `MPP_MOCK_PAYMENT_METHOD_ID`   | Optional `pm_…` to reuse instead of creating a test card each run.                                         |
| `MPP_MOCK_CARD_*`              | Optional overrides for the 4242 test card when not using `MPP_MOCK_PAYMENT_METHOD_ID`.                     |


## MPP “agent” client (mint SPT + pay 402)

The agent simulates a **grantor** (such as an issuing bank) by using mock bank credentials: it creates or reuses a `PaymentMethod`, calls the **SPT test helper** with the same mock seller fields as the server, then uses `mppx.fetch` to pay the challenge.

Terminal 1:

```bash
npm start
```

Terminal 2 (same directory and `.env`):

```bash
npm run agent
```

If Stripe returns an error on the test helper, your account may need **agentic commerce / machine payments** access; see [Machine payments](https://docs.stripe.com/payments/machine#sign-up).

## PostalForm (real printed mail)

The same MPP + Stripe SPT client can pay **[PostalForm](https://postalform.com)**’s machine API so an agent can **print and mail a physical letter** ([agents guide](https://postalform.com/agents)).

1. Set **`POSTALFORM_BUYER_EMAIL`** in `.env` (required by PostalForm for receipts).
2. Optionally set **`POSTALFORM_*`** address and PDF variables (see `.env.example`); default PDF is `fixtures/sample-letter.pdf` (small W3C sample PDF).
3. Run:

   ```bash
   npm run agent:postalform
   ```

The script calls **`POST /api/machine/mpp/orders/validate`**, then **`POST /api/machine/mpp/orders`** with the same JSON body; **`mppx`** handles **402 → SPT → retry**. If PostalForm returns only a **Tempo** challenge, add a Tempo method to the client or use their **legacy x402** / **`purl`** flow instead.

Set **`POSTALFORM_STRIPE_SELLER_EXTERNAL_ID`** / **`POSTALFORM_STRIPE_NETWORK_ID`** if your Stripe SPT grant must match PostalForm’s Business Network profile (see validate response and Stripe docs).

## Configuration (core)


| Variable             | Purpose                                                    |
| -------------------- | ---------------------------------------------------------- |
| `STRIPE_SECRET_KEY`  | Required. `sk_test_...`                                    |
| `MPP_SECRET_KEY`     | Required. Stable base64 secret for challenge binding       |
| `STRIPE_API_VERSION` | Default `2026-03-04.preview`                               |
| `PORT`               | Default `4242`                                             |
| `MPP_PAID_URL`       | URL the agent calls (default `http://127.0.0.1:4242/paid`) |


## Troubleshooting

- `**Invalid character in header content ["WWW-Authenticate"]`** (Node): The MPP challenge embeds `description` in the `WWW-Authenticate` value. Use **ASCII-only** text there (no smart quotes or em dashes).
- **Node version**: `mppx` dependencies may warn below **Node 22**; upgrade if anything fails at runtime.
- **SPT rejected / seller mismatch**: Ensure **`MPP_MOCK_SELLER_NETWORK_ID`** and **`MPP_MOCK_SELLER_EXTERNAL_ID`** are identical in the **same** `.env` for both `npm start` and `npm run agent`.
- **404 on `POST .../test_helpers/shared_payment/granted_tokens`**: The SPT test helper is not available on every test account (often gated with [machine payments](https://docs.stripe.com/payments/machine#sign-up) / agentic commerce). Until Stripe enables it, you can still run the server and confirm **`curl /paid` → 402**; the agent will fail at the SPT mint step.

## Security

- Never commit `.env` or real keys.
- This repo folder is for **test** integration only.

