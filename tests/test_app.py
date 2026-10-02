from fastapi.testclient import TestClient

from offerproof.app import create_app
from offerproof.extract import Extraction


class NoFindings:
    def extract(self, message: str) -> Extraction:
        return Extraction(findings=[], claimed_company="")


client = TestClient(create_app(make_extractor=NoFindings))


def test_serves_the_page() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "OfferProof" in response.text


def test_check_returns_verdict_and_quotes() -> None:
    response = client.post("/api/check", json={"text": "Pay Rs 999 registration fee today."})
    body = response.json()
    assert response.status_code == 200
    assert body["verdict"] == "LIKELY_SCAM"
    assert body["findings"][0]["quote"] == "Pay Rs 999 registration fee today"
    assert body["model_status"] == "used"


def test_model_can_be_switched_off() -> None:
    response = client.post("/api/check", json={"text": "Hello", "use_model": False})
    assert response.json()["model_status"] == "off"


def test_empty_message_is_rejected() -> None:
    assert client.post("/api/check", json={"text": ""}).status_code == 422
