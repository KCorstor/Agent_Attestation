from fastapi.testclient import TestClient

from attestation.schemas import BidRfpRequest, TransactionIntent
import main as main_mod


def test_demo_rfp_endpoint() -> None:
    client = TestClient(main_mod.app)
    body = BidRfpRequest(
        resource_url="https://x.example/r",
        transaction=TransactionIntent(amount_cents=100, currency="USD", mcc="5411"),
        credit_score_band="720-850",
    )
    r = client.post("/demo/bid-rails/rfp", json=body.model_dump(mode="json"))
    assert r.status_code == 200
    data = r.json()
    assert data["rfp_id"]
    assert data["package"]["rfp_id"] == data["rfp_id"]
    assert len(data["bids"]) == 3
    assert data["bids"][0]["fee_bps"] >= 0
