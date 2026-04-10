# Run the demo

From the repo root, configure **`Agent_Attestation/.env`** (loaded automatically) with at least **`MPP_SECRET_KEY`**, **`TEMPO_PRIVATE_KEY`**, **`TEMPO_RECIPIENT_ADDRESS`**, and **`MPP_AUCTION_TERMS_FILE`** (e.g. `./demo-ui-terms.json`). The payer wallet needs testnet **pathUSD** on Tempo Moderato.

```bash
cd mpp_tempo_example
npm install
npm run demo:ui
```

Open **http://127.0.0.1:3333** and click **Run all steps** (clears artifacts, starts the merchant server on **http://127.0.0.1:4243** by default, runs the agent).

If you do not have keys yet, from **`mpp_tempo_example/`** run **`npm run wallet:setup`** once to create **`../.env`** and fund the testnet wallet.
