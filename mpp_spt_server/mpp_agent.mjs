/**
 * Minimal "agent": MPP-aware fetch against mpp_spt_server using Stripe SPT (test helper).
 *
 * Plays the mock *grantor* (e.g. issuing bank that won your auction): creates a
 * PaymentMethod for the borrower, mints an SPT bound to the same seller as the
 * MPP server (MPP_MOCK_SELLER_*), then pays the 402.
 *
 * Prerequisites:
 *   - mpp_spt_server running (npm start) with the same .env (especially mock SPT vars)
 *   - Machine payments / SPT test helpers enabled on your Stripe test account
 *
 * Plays the mock *grantor* (e.g. issuing bank that won your auction): creates a
 * PaymentMethod for the borrower, mints an SPT bound to the same seller as the
 * MPP server (MPP_MOCK_SELLER_*), then pays the 402.
 *
 * Prerequisites:
 *   - mpp_spt_server running (npm start) with the same .env (especially mock SPT vars)
 *   - Machine payments / SPT test helpers enabled on your Stripe test account
 *
 * Plays the mock *grantor* (e.g. issuing bank that won your auction): creates a
 * PaymentMethod for the borrower, mints an SPT bound to the same seller as the
 * MPP server (MPP_MOCK_SELLER_*), then pays the 402.
 *
 * Prerequisites:
 *   - mpp_spt_server running (npm start) with the same .env (especially mock SPT vars)
 *   - Machine payments / SPT test helpers enabled on your Stripe test account
 *
 * Plays the mock *grantor* (e.g. issuing bank that won your auction): creates a
 * PaymentMethod for the borrower, mints an SPT bound to the same seller as the
 * MPP server (MPP_MOCK_SELLER_*), then pays the 402.
 *
 * Prerequisites:
 *   - mpp_spt_server running (npm start) with the same .env (especially mock SPT vars)
 *   - Machine payments / SPT test helpers enabled on your Stripe test account
 *
 * Plays the mock *grantor* (e.g. issuing bank that won your auction): creates a
 * PaymentMethod for the borrower, mints an SPT bound to the same seller as the
 * MPP server (MPP_MOCK_SELLER_*), then pays the 402.
 *
 * Prerequisites:
 *   - mpp_spt_server running (npm start) with the same .env (especially mock SPT vars)
 *   - Machine payments / SPT test helpers enabled on your Stripe test account
 *
 * Plays the mock *grantor* (e.g. issuing bank that won your auction): creates a
 * PaymentMethod for the borrower, mints an SPT bound to the same seller as the
 * MPP server (MPP_MOCK_SELLER_*), then pays the 402.
 *
 * Prerequisites:
 *   - mpp_spt_server running (npm start) with the same .env (especially mock SPT vars)
 *   - Machine payments / SPT test helpers enabled on your Stripe test account
 *
 * Plays the mock *grantor* (e.g. issuing bank that won your auction): creates a
 * PaymentMethod for the borrower, mints an SPT bound to the same seller as the
 * MPP server (MPP_MOCK_SELLER_*), then pays the 402.
 *
 * Prerequisites:
 *   - mpp_spt_server running (npm start) with the same .env (especially mock SPT vars)
 *   - Machine payments / SPT test helpers enabled on your Stripe test account
 *
 * Plays the mock *grantor* (e.g. issuing bank that won your auction): creates a
 * PaymentMethod for the borrower, mints an SPT bound to the same seller as the
 * MPP server (MPP_MOCK_SELLER_*), then pays the 402.
 *
 * Prerequisites:
 *   - mpp_spt_server running (npm start) with the same .env (especially mock SPT vars)
 *   - Machine payments / SPT test helpers enabled on your Stripe test account
 *
 * Plays the mock *grantor* (e.g. issuing bank that won your auction): creates a
 * PaymentMethod for the borrower, mints an SPT bound to the same seller as the
 * MPP server (MPP_MOCK_SELLER_*), then pays the 402.
 *
 * Prerequisites:
 *   - mpp_spt_server running (npm start) with the same .env (especially mock SPT vars)
 *   - Machine payments / SPT test helpers enabled on your Stripe test account
 *
 * Plays the mock *grantor* (e.g. issuing bank that won your auction): creates a
 * PaymentMethod for the borrower, mints an SPT bound to the same seller as the
 * MPP server (MPP_MOCK_SELLER_*), then pays the 402.
 *
 * Prerequisites:
 *   - mpp_spt_server running (npm start) with the same .env (especially mock SPT vars)
 *   - Machine payments / SPT test helpers enabled on your Stripe test account
 *
 * Run:  npm run agent
 *   or  MPP_PAID_URL=http://127.0.0.1:4242/paid npm run agent
 */
import "dotenv/config";
import Stripe from "stripe";
import { Mppx, stripe as stripeMethod } from "mppx/client";
import { describeMockSptConfig, mockSptConfigFromEnv } from "./mock_spt_env.mjs";

const stripeSecret = process.env.STRIPE_SECRET_KEY?.trim();
const paidUrl = (process.env.MPP_PAID_URL || "http://127.0.0.1:4242/paid").trim();
const stripeApiVersion = process.env.STRIPE_API_VERSION?.trim() || "2026-03-04.preview";
const mock = mockSptConfigFromEnv();

if (!stripeSecret) {
  console.error("Set STRIPE_SECRET_KEY in .env (same test key as mpp_spt_server).");
  process.exit(1);
}

const stripe = new Stripe(stripeSecret, { apiVersion: stripeApiVersion });

/**
 * Mint SPT via Stripe test helper (simulates grantor delegating pay to seller).
 * @see https://docs.stripe.com/agentic-commerce/concepts/shared-payment-tokens
 */
async function createSptViaTestHelper({
  paymentMethod,
  amount,
  currency,
  expiresAt,
  networkId,
  sellerExternalId,
}) {
  const params = new URLSearchParams();
  params.set("payment_method", paymentMethod);
  params.set("usage_limits[currency]", currency);
  params.set("usage_limits[max_amount]", amount);
  params.set("usage_limits[expires_at]", String(expiresAt));
  if (networkId) params.set("seller_details[network_id]", networkId);
  params.set("seller_details[external_id]", sellerExternalId);
  // grantorExternalId is carried on the MPP credential (stripe.charge externalId), not all Stripe SPT APIs accept grantor_details.

  const auth = Buffer.from(`${stripeSecret}:`).toString("base64");
  const res = await fetch("https://api.stripe.com/v1/test_helpers/shared_payment/granted_tokens", {
    method: "POST",
    headers: {
      Authorization: `Basic ${auth}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: params,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(`Stripe test_helpers SPT failed (${res.status}): ${JSON.stringify(data)}`);
  }
  return data.id;
}

async function resolvePaymentMethod() {
  if (mock.paymentMethodId) {
    console.log(`Using existing PaymentMethod from MPP_MOCK_PAYMENT_METHOD_ID=${mock.paymentMethodId}`);
    return mock.paymentMethodId;
  }
  console.log(`Creating test PaymentMethod (${mock.card.number.slice(0, 4)}…)`);
  const pm = await stripe.paymentMethods.create({
    type: "card",
    card: mock.card,
  });
  console.log(`PaymentMethod: ${pm.id}`);
  return pm.id;
}

async function main() {
  console.log("[mock SPT] grantor:", mock.grantorLabel);
  console.log("[mock SPT] config:", JSON.stringify(describeMockSptConfig(mock), null, 2));
  console.log("");

  const pmId = await resolvePaymentMethod();

  const mppx = Mppx.create({
    polyfill: false,
    methods: [
      stripeMethod.charge({
        paymentMethod: pmId,
        externalId: mock.grantorExternalId,
        createToken: async (args) =>
          createSptViaTestHelper({
            paymentMethod: args.paymentMethod,
            amount: args.amount,
            currency: args.currency,
            expiresAt: args.expiresAt,
            networkId: args.networkId ?? mock.sellerNetworkId,
            sellerExternalId: mock.sellerExternalId,
          }),
      }),
    ],
  });

  console.log(`GET ${paidUrl} (MPP client will pay 402 + retry)…\n`);
  const res = await mppx.fetch(paidUrl);
  const body = await res.text();

  console.log(`Final status: ${res.status}`);
  console.log(`Payment-Receipt: ${res.headers.get("Payment-Receipt") || "(none)"}`);
  console.log("Body:");
  console.log(body.slice(0, 4000) + (body.length > 4000 ? "…" : ""));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
