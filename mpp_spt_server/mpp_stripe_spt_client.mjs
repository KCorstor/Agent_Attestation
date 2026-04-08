/**
 * Shared Stripe SPT + mppx/client wiring for MPP 402 flows (local server or PostalForm).
 */
import { Mppx, stripe as stripeMethod } from "mppx/client";

/**
 * Mint SPT via Stripe test helper (test mode).
 * @see https://docs.stripe.com/agentic-commerce/concepts/shared-payment-tokens
 */
export async function mintSptViaStripeTestHelper({
  stripeSecret,
  stripeApiVersion,
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

  const auth = Buffer.from(`${stripeSecret}:`).toString("base64");
  const res = await fetch("https://api.stripe.com/v1/test_helpers/shared_payment/granted_tokens", {
    method: "POST",
    headers: {
      Authorization: `Basic ${auth}`,
      "Content-Type": "application/x-www-form-urlencoded",
      "Stripe-Version": stripeApiVersion,
    },
    body: params,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(`Stripe test_helpers SPT failed (${res.status}): ${JSON.stringify(data)}`);
  }
  return data.id;
}

export async function resolvePaymentMethod(stripe, mock) {
  if (mock.paymentMethodId) {
    console.log(`Using existing PaymentMethod from MPP_MOCK_PAYMENT_METHOD_ID=${mock.paymentMethodId}`);
    return mock.paymentMethodId;
  }
  const cardPayload = mock.useRawCardData ? mock.card : { token: mock.stripeCardToken };
  if (mock.useRawCardData) {
    console.log(`Creating PaymentMethod from raw card (MPP_MOCK_USE_RAW_CARD_DATA)…`);
  } else {
    console.log(`Creating PaymentMethod from Stripe test token ${mock.stripeCardToken}…`);
  }
  const pm = await stripe.paymentMethods.create({
    type: "card",
    card: cardPayload,
  });
  console.log(`PaymentMethod: ${pm.id}`);
  return pm.id;
}

/** resolveNetworkId / resolveSellerExternalId receive the Stripe createToken args from mppx (challenge + payment fields). */
export function createMppxWithStripeSpt({
  stripeSecret,
  stripeApiVersion,
  mock,
  pmId,
  resolveSellerExternalId,
  resolveNetworkId,
}) {
  return Mppx.create({
    polyfill: false,
    methods: [
      stripeMethod.charge({
        paymentMethod: pmId,
        externalId: mock.grantorExternalId,
        createToken: async (args) =>
          mintSptViaStripeTestHelper({
            stripeSecret,
            stripeApiVersion,
            paymentMethod: args.paymentMethod,
            amount: args.amount,
            currency: args.currency,
            expiresAt: args.expiresAt,
            networkId: resolveNetworkId(args),
            sellerExternalId: resolveSellerExternalId(args),
          }),
      }),
    ],
  });
}
