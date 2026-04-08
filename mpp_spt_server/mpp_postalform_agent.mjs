/**
 * MPP agent -> PostalForm: validate, then POST /api/machine/mpp/orders (402 -> Stripe SPT -> retry).
 * PostalForm prints and mails a real letter from your PDF.
 *
 * Docs: https://postalform.com/agents
 *
 * Required env:
 *   STRIPE_SECRET_KEY, MPP_SECRET_KEY (unused here but keep .env shared)
 *   POSTALFORM_BUYER_EMAIL — receipt email (PostalForm requirement)
 *
 * Run:  npm run agent:postalform
 */
import "dotenv/config";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { randomUUID } from "node:crypto";
import Stripe from "stripe";
import { mockSptConfigFromEnv } from "./mock_spt_env.mjs";
import { createMppxWithStripeSpt, resolvePaymentMethod } from "./mpp_stripe_spt_client.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));

const stripeSecret = process.env.STRIPE_SECRET_KEY?.trim();
const stripeApiVersion = process.env.STRIPE_API_VERSION?.trim() || "2026-03-04.preview";
const base = (process.env.POSTALFORM_BASE_URL || "https://postalform.com").replace(/\/$/, "");
const mock = mockSptConfigFromEnv();

const buyerEmail = process.env.POSTALFORM_BUYER_EMAIL?.trim();
if (!stripeSecret) {
  console.error("Set STRIPE_SECRET_KEY in .env.");
  process.exit(1);
}
if (!buyerEmail) {
  console.error("Set POSTALFORM_BUYER_EMAIL in .env (required for machine orders).");
  process.exit(1);
}

function envOr(name, fallback) {
  const v = process.env[name]?.trim();
  return v || fallback;
}

/** PostalForm rejects null line2; omit key when blank. */
function manualAddress(line1, line2, city, state, zip) {
  const o = {
    line1,
    city,
    state,
    zip,
  };
  const l2 = (line2 || "").trim();
  if (l2) o.line2 = l2;
  return o;
}

function buildOrderPayload() {
  const pdfPath = envOr("POSTALFORM_PDF_PATH", join(__dirname, "fixtures", "minimal-letter.pdf"));
  const pdfBuf = readFileSync(pdfPath);
  const pdf = `data:application/pdf;base64,${pdfBuf.toString("base64")}`;

  return {
    request_id: randomUUID(),
    buyer_name: envOr("POSTALFORM_BUYER_NAME", "Agent Attestation Lab"),
    buyer_email: buyerEmail,
    pdf,
    file_name: envOr("POSTALFORM_FILE_NAME", "letter.pdf"),
    sender_name: envOr("POSTALFORM_SENDER_NAME", "Agent Attestation Lab"),
    sender_address_type: "Manual",
    sender_address_manual: manualAddress(
      envOr("POSTALFORM_SENDER_LINE1", "123 Demo Sender St"),
      envOr("POSTALFORM_SENDER_LINE2", ""),
      envOr("POSTALFORM_SENDER_CITY", "Springfield"),
      envOr("POSTALFORM_SENDER_STATE", "IL"),
      envOr("POSTALFORM_SENDER_ZIP", "62701"),
    ),
    recipient_name: envOr("POSTALFORM_RECIPIENT_NAME", "Demo Recipient"),
    recipient_address_type: "Manual",
    recipient_address_manual: manualAddress(
      envOr("POSTALFORM_RECIPIENT_LINE1", "456 Demo Recipient Ave"),
      envOr("POSTALFORM_RECIPIENT_LINE2", ""),
      envOr("POSTALFORM_RECIPIENT_CITY", "Springfield"),
      envOr("POSTALFORM_RECIPIENT_STATE", "IL"),
      envOr("POSTALFORM_RECIPIENT_ZIP", "62701"),
    ),
    double_sided: envOr("POSTALFORM_DOUBLE_SIDED", "true") !== "false",
    color: envOr("POSTALFORM_COLOR", "false") === "true",
    mail_class: envOr("POSTALFORM_MAIL_CLASS", "standard"),
    certified: envOr("POSTALFORM_CERTIFIED", "false") === "true",
  };
}

async function main() {
  const order = buildOrderPayload();
  const bodyJson = JSON.stringify(order);

  console.log("PostalForm MPP agent");
  console.log("  validate:", `${base}/api/machine/mpp/orders/validate`);
  console.log("  create:  ", `${base}/api/machine/mpp/orders`);
  console.log("  request_id:", order.request_id);
  console.log("");

  const validateRes = await fetch(`${base}/api/machine/mpp/orders/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: bodyJson,
  });
  const validateText = await validateRes.text();
  let validateJson;
  try {
    validateJson = JSON.parse(validateText);
  } catch {
    validateJson = { raw: validateText };
  }
  console.log("Validate status:", validateRes.status);
  console.log(JSON.stringify(validateJson, null, 2).slice(0, 6000));
  if (!validateRes.ok) {
    throw new Error("PostalForm validate failed; fix payload or addresses (see https://postalform.com/agents).");
  }

  const stripe = new Stripe(stripeSecret, { apiVersion: stripeApiVersion });
  const pmId = await resolvePaymentMethod(stripe, mock);

  const sellerExt =
    process.env.POSTALFORM_STRIPE_SELLER_EXTERNAL_ID?.trim() || mock.sellerExternalId;
  const networkFallback = process.env.POSTALFORM_STRIPE_NETWORK_ID?.trim() || mock.sellerNetworkId;

  const mppx = createMppxWithStripeSpt({
    stripeSecret,
    stripeApiVersion,
    mock,
    pmId,
    resolveNetworkId: (args) => args.networkId || networkFallback,
    resolveSellerExternalId: () => sellerExt,
  });

  console.log("\nPOST create (MPP will pay 402 + retry)…\n");

  const res = await mppx.fetch(`${base}/api/machine/mpp/orders`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: bodyJson,
  });

  const out = await res.text();
  console.log("Final status:", res.status);
  console.log("Payment-Receipt:", res.headers.get("Payment-Receipt") || "(none)");
  console.log("Body:", out.slice(0, 8000) + (out.length > 8000 ? "…" : ""));

  if (res.ok || res.status === 202) {
    console.log("\nPoll status:");
    console.log(`  curl -sS "${base}/api/machine/mpp/orders/${order.request_id}" | jq`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
