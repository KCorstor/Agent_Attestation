/**
 * MPP test server — Stripe Shared Payment Token (SPT) method.
 *
 * Uses `mppx/express` (recommended with Node’s HTTP stack for challenge headers).
 *
 * Docs:
 *   https://docs.stripe.com/payments/machine/mpp
 *   https://mpp.dev
 *
 * Run:  cp .env.example .env  # fill STRIPE_SECRET_KEY + MPP_SECRET_KEY
 *       npm install
 *       npm start
 *
 * Probe: curl -i http://127.0.0.1:4242/paid
 */
import "dotenv/config";
import express from "express";
import { Mppx, stripe } from "mppx/express";
import Stripe from "stripe";
import { describeMockSptConfig, mockSptConfigFromEnv } from "./mock_spt_env.mjs";

const stripeSecret = process.env.STRIPE_SECRET_KEY?.trim();
const mppSecret = process.env.MPP_SECRET_KEY?.trim();
const stripeApiVersion = process.env.STRIPE_API_VERSION?.trim() || "2026-03-04.preview";
const mock = mockSptConfigFromEnv();

if (!stripeSecret) {
  console.error("Missing STRIPE_SECRET_KEY (set in .env — Test mode key from Stripe Dashboard).");
  process.exit(1);
}
if (!mppSecret) {
  console.error(
    "Missing MPP_SECRET_KEY. Generate a stable secret (e.g. openssl rand -base64 32) and add to .env.",
  );
  process.exit(1);
}

const stripeClient = new Stripe(stripeSecret, {
  apiVersion: stripeApiVersion,
});

const mppx = Mppx.create({
  secretKey: mppSecret,
  methods: [
    stripe.charge({
      client: stripeClient,
      networkId: mock.sellerNetworkId,
      paymentMethodTypes: ["card", "link"],
      decimals: 2,
      metadata: {
        mock_seller_external_id: mock.sellerExternalId,
        mock_grantor_external_id: mock.grantorExternalId,
      },
    }),
  ],
});

const app = express();

app.get("/", (_req, res) => {
  res.json({
    service: "mpp-spt-test",
    docs: "https://docs.stripe.com/payments/machine/mpp",
    paid: "GET /paid — returns 402 until a valid MPP credential (SPT) is sent",
    mock_spt: describeMockSptConfig(mock),
  });
});

/** Safe reference for the agent: which seller_details must match when minting an SPT. */
app.get("/mock-spt/seller", (_req, res) => {
  res.json(describeMockSptConfig(mock));
});

app.get(
  "/paid",
  mppx.charge({
    amount: "1",
    currency: "usd",
    decimals: 2,
    description: "MPP SPT test - premium API access",
  }),
  (_req, res) => {
    res.json({
      ok: true,
      message: "Payment accepted (MPP + Stripe SPT).",
      data: "This response is only returned after a valid Payment-Receipt path.",
      mock_spt: describeMockSptConfig(mock),
    });
  },
);

const port = Number(process.env.PORT || 4242);
app.listen(port, "127.0.0.1", () => {
  console.log(`MPP SPT server listening on http://127.0.0.1:${port}`);
  console.log(`Try: curl -i http://127.0.0.1:${port}/paid`);
  console.log("[mock SPT] seller binding for grants (must match mpp_agent):");
  console.log(`  MPP_MOCK_SELLER_NETWORK_ID / challenge networkId = ${mock.sellerNetworkId}`);
  console.log(`  MPP_MOCK_SELLER_EXTERNAL_ID (seller_details.external_id) = ${mock.sellerExternalId}`);
  console.log(`  grantor persona (metadata only) = ${mock.grantorLabel} (${mock.grantorExternalId})`);
});
