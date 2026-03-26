from fastapi.testclient import TestClient

import main as main_mod


def test_demo_full_flow_endpoint() -> None:
    client = TestClient(main_mod.app)
    r = client.get("/demo/full-flow")
    assert r.status_code == 200
    data = r.json()
    assert data["demo_mode"] is True
    assert data["fake_access_token"] == "access-demo-fake"
    assert len(data["steps"]) >= 5
    ids = [s["id"] for s in data["steps"]]
    assert "1_init" in ids
    assert "5_rfp" in ids
