/**
 * Minimal MPP server — Tempo (pathUSD) on Tempo Moderato testnet only.
 *
 * Run:  cp .env.example .env && fill MPP_SECRET_KEY + TEMPO_RECIPIENT_ADDRESS
 *       npm install && npm start
 *
 * Probe: curl -i http://127.0.0.1:4243/paid   → 402 until paid with mppx client
 *
 * Docs: https://mpp.dev  |  Tempo: https://tempo.xyz
 */
import "./load-env.mjs";
import express from "express";
import { Mppx, tempo } from "mppx/express";

const mppSecret = process.env.MPP_SECRET_KEY?.trim();
const recipient = process.env.TEMPO_RECIPIENT_ADDRESS?.trim();

if (!mppSecret) {
  console.error("Set MPP_SECRET_KEY in .env (e.g. openssl rand -base64 32).");
  process.exit(1);
}
if (!recipient || !/^0x[a-fA-F0-9]{40}$/.test(recipient)) {
  console.error("Set TEMPO_RECIPIENT_ADDRESS to a valid 0x…40 address in .env.");
  process.exit(1);
}

const mppx = Mppx.create({
  secretKey: mppSecret,
  // This server uses `tempo.charge` only, not `tempo()`. The full `tempo()` helper
  // also registers `session`, which needs a server signing account
  // (`privateKeyToAccount`) — omitted here to keep the demo small.
  methods: [
    tempo.charge({
      recipient,
      testnet: true,
    }),
  ],
});

const app = express();

app.get("/", (_req, res) => {
  res.json({
    service: "mpp-tempo-example",
    paid: "GET /paid - 402 until valid Tempo MPP credential",
    recipient,
    chain: "Tempo Moderato (testnet)",
  });
});

app.get(
  "/paid",
  mppx.charge({
    amount: "0.1",
    decimals: 6,
    description: "MPP Tempo demo - 0.1 pathUSD (testnet)",
  }),
  (_req, res) => {
    res.json({
      ok: true,
      message: "Paid with Tempo (MPP).",
    });
  },
);

const port = Number(process.env.PORT || 4243);
app.listen(port, "127.0.0.1", () => {
  console.log(`MPP Tempo server → http://127.0.0.1:${port}`);
  console.log(`Recipient (receives pathUSD): ${recipient}`);
  console.log(`Try: curl -i http://127.0.0.1:${port}/paid`);
});
