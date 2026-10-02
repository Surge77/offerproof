import json
from typing import Any

import httpx
import pytest

from offerproof.extract import ModelUnavailable, OllamaExtractor, findings_from_answer, quote_is_genuine

MESSAGE = "Selected for Infosys data entry. Interview on WhatsApp chat. Pay Rs 2,000 joining fee now."


def answer(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "claimed_company": "Infosys",
        "asks_money": {"present": True, "quote": "Pay Rs 2,000 joining fee"},
        "asks_secrets": {"present": False, "quote": ""},
        "asks_identity_docs": {"present": False, "quote": ""},
        "task_based_work": {"present": False, "quote": ""},
        "pressure": {"present": False, "quote": ""},
        "interview": {"channel": "chat_only", "quote": "Interview on WhatsApp chat"},
    }
    base.update(overrides)
    return base


def stub_transport(body: object, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"message": {"content": json.dumps(body)}})
    return httpx.MockTransport(handler)


def test_quote_matching_ignores_case_and_spacing() -> None:
    assert quote_is_genuine("pay rs 2,000   JOINING fee", MESSAGE)


def test_invented_quote_is_rejected() -> None:
    assert not quote_is_genuine("send your OTP", MESSAGE)


def test_verified_evidence_becomes_findings() -> None:
    extraction = findings_from_answer(answer(), MESSAGE)
    assert {f.signal_id for f in extraction.findings} == {"asks_fee", "chat_only_interview"}
    assert all(f.source == "model" for f in extraction.findings)
    assert extraction.claimed_company == "Infosys"


def test_evidence_with_a_made_up_quote_is_dropped() -> None:
    made_up = answer(asks_secrets={"present": True, "quote": "share the OTP"})
    signals = {f.signal_id for f in findings_from_answer(made_up, MESSAGE).findings}
    assert "asks_secrets" not in signals


@pytest.mark.parametrize(("message", "model_answer"), [
    ("Would you be open to a quick call this week?",
     {"interview": {"channel": "chat_only", "quote": "quick call this week"}}),
    ("Thank you for taking the time to interview with us.",
     {"interview": {"channel": "chat_only", "quote": "interview with us"}}),
    ("Please complete a 60 minute coding assessment on HackerRank.",
     {"task_based_work": {"present": True, "quote": "complete a 60 minute coding assessment on HackerRank"}}),
])
def test_quote_that_does_not_support_the_claim_is_dropped(message: str, model_answer: dict[str, Any]) -> None:
    claim = answer(asks_money={"present": False, "quote": ""}, interview={"channel": "not_mentioned", "quote": ""})
    claim.update(model_answer)
    assert findings_from_answer(claim, message).findings == []


def test_company_not_in_message_is_ignored() -> None:
    assert findings_from_answer(answer(claimed_company="Google"), MESSAGE).claimed_company == ""


def test_extractor_parses_ollama_response() -> None:
    extractor = OllamaExtractor(transport=stub_transport(answer()))
    assert {f.signal_id for f in extractor.extract(MESSAGE).findings} == {"asks_fee", "chat_only_interview"}


def test_server_error_raises_model_unavailable() -> None:
    extractor = OllamaExtractor(transport=stub_transport({}, status=500))
    with pytest.raises(ModelUnavailable):
        extractor.extract(MESSAGE)


def test_non_json_content_raises_model_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "not json"}})
    with pytest.raises(ModelUnavailable):
        OllamaExtractor(transport=httpx.MockTransport(handler)).extract(MESSAGE)
