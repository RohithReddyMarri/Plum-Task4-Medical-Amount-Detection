import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_process_text_standard():
    payload = {"text": "Total: INR 1200 | Paid: 1000 | Due: 200 | Discount: 10%"}
    response = client.post("/api/process", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["currency"] == "INR"
    assert len(data["amounts"]) == 3
    assert data["amounts"][0]["type"] == "total_bill"
    assert data["amounts"][0]["value"] == 1200


def test_process_noisy_ocr_sample():
    payload = {"text": "T0tal: Rs l200 | Pald: 1000 | Due: 200"}
    response = client.post("/api/process", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["currency"] == "INR"
    types = [a["type"] for a in data["amounts"]]
    assert "total_bill" in types
    assert "paid" in types
    assert "due" in types


def test_process_guardrail_noisy_text():
    payload = {"text": "~~~ @@@ ### blurred unreadable"}
    response = client.post("/api/process", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_amounts_found"
    assert data["reason"] == "document too noisy"


def test_pipeline_detailed_endpoint():
    payload = {"text": "Total: INR 1200 | Paid: 1000 | Due: 200"}
    response = client.post("/api/pipeline", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "step1_ocr" in data
    assert "step2_normalization" in data
    assert "step3_classification" in data
    assert "step4_final" in data
    assert data["guardrails_passed"] is True


def test_process_image_upload():
    img_path = SAMPLES_DIR / "sample_receipt_standard.png"
    if not img_path.exists():
        pytest.skip("Sample image does not exist yet")

    with open(img_path, "rb") as f:
        response = client.post(
            "/api/process",
            files={"file": ("sample_receipt_standard.png", f, "image/png")}
        )
    assert response.status_code == 200
    data = response.json()
    assert "amounts" in data or "status" in data


def test_individual_step_endpoints():
    # Step 1 endpoint
    resp1 = client.post("/api/step1-ocr", json={"text": "Total: INR 1200 | Paid: 1000 | Due: 200"})
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert "raw_tokens" in data1
    assert data1["currency_hint"] == "INR"

    # Step 2 endpoint
    resp2 = client.post("/api/step2-normalize", json=["l200", "1000", "200", "10%"])
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["normalized_amounts"] == [1200, 1000, 200]

    # Step 3 endpoint
    resp3 = client.post("/api/step3-classify", data={"text": "Total: INR 1200 | Paid: 1000 | Due: 200", "normalized_amounts": [1200, 1000, 200]})
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert len(data3["amounts"]) == 3
