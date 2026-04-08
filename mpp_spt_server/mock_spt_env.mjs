/**
 * Shared mock SPT credentials for local demos.
 *
 * The Stripe test helper binds an SPT to a seller via seller_details.network_id +
 * seller_details.external_id. The MPP challenge from mppx must use the same
 * networkId, and the grant request must use the same external_id — so server
 * and agent read the same env vars.
 *
 * @see https://docs.stripe.com/agentic-commerce/concepts/shared-payment-tokens
 */

export function mockSptConfigFromEnv() {
  const sellerNetworkId = (
    process.env.MPP_MOCK_SELLER_NETWORK_ID ||
    process.env.STRIPE_MPP_NETWORK_ID ||
    "internal"
  ).trim();

  const sellerExternalId = (process.env.MPP_MOCK_SELLER_EXTERNAL_ID || "mock-seller-attestation-lab").trim();

  const grantorExternalId = (
    process.env.MPP_MOCK_GRANTOR_EXTERNAL_ID || "mock-issuing-bank-auction-winner"
  ).trim();

  const grantorLabel = (
    process.env.MPP_MOCK_GRANTOR_LABEL || "Mock Issuing Bank (auction winner)"
  ).trim();

  const paymentMethodId = (process.env.MPP_MOCK_PAYMENT_METHOD_ID || "").trim();

  /** Default: Stripe test token (no raw-card API). @see https://stripe.com/docs/testing */
  const stripeCardToken = (process.env.MPP_MOCK_STRIPE_CARD_TOKEN || "tok_visa").trim();

  const useRawCardData =
    process.env.MPP_MOCK_USE_RAW_CARD_DATA === "1" ||
    process.env.MPP_MOCK_USE_RAW_CARD_DATA === "true";

  const card = {
    number: (process.env.MPP_MOCK_CARD_NUMBER || "4242424242424242").replace(/\s/g, ""),
    exp_month: Number(process.env.MPP_MOCK_CARD_EXP_MONTH || "12"),
    exp_year: Number(process.env.MPP_MOCK_CARD_EXP_YEAR || "2034"),
    cvc: (process.env.MPP_MOCK_CARD_CVC || "123").trim(),
  };

  return {
    sellerNetworkId,
    sellerExternalId,
    grantorExternalId,
    grantorLabel,
    paymentMethodId,
    stripeCardToken,
    useRawCardData,
    card,
  };
}

export function describeMockSptConfig(mock) {
  let pmSource = "MPP_MOCK_PAYMENT_METHOD_ID";
  if (!mock.paymentMethodId) {
    pmSource = mock.useRawCardData
      ? "MPP_MOCK_CARD_* raw (requires Stripe raw card data API)"
      : `Stripe test token ${mock.stripeCardToken} (MPP_MOCK_STRIPE_CARD_TOKEN)`;
  }
  return {
    seller_network_id: mock.sellerNetworkId,
    seller_external_id: mock.sellerExternalId,
    grantor_external_id: mock.grantorExternalId,
    grantor_label: mock.grantorLabel,
    payment_method_source: pmSource,
  };
}
