import pytest

from offerproof.catalog import Severity
from offerproof.extract import Extraction, ModelUnavailable
from offerproof.findings import Finding
from offerproof.verdict import MAX_MESSAGE_CHARS, check


class FixedExtractor:
    def __init__(self, findings: list[Finding], company: str = "") -> None:
        self._extraction = Extraction(findings=findings, claimed_company=company)

    def extract(self, message: str) -> Extraction:
        return self._extraction


class BrokenExtractor:
    def extract(self, message: str) -> Extraction:
        raise ModelUnavailable("connection refused")


def model_finding(signal_id: str, severity: Severity = "severe") -> Finding:
    return Finding(signal_id=signal_id, severity=severity, label="x", why="x", ask_back="x",
                   quote="x", source="model")


def test_severe_rule_finding_means_likely_scam() -> None:
    result = check("Pay the registration fee of Rs 500 to proceed.", extractor=None)
    assert result.verdict == "LIKELY_SCAM"
    assert result.model_status == "off"


def test_clean_message_is_unverified_never_genuine() -> None:
    result = check("Thanks for applying. Can you do a video interview on Tuesday?", extractor=None)
    assert result.verdict == "UNVERIFIED"
    assert result.findings == []
    assert "does not make it genuine" in result.summary


def test_model_evidence_alone_can_flag_a_scam() -> None:
    message = "Hello, small advance needed before the training starts."
    result = check(message, extractor=FixedExtractor([model_finding("asks_fee")]))
    assert result.verdict == "LIKELY_SCAM"
    assert result.model_status == "used"


def test_rule_finding_wins_over_model_for_the_same_signal() -> None:
    message = "Pay the registration fee of Rs 500 to proceed."
    result = check(message, extractor=FixedExtractor([model_finding("asks_fee")]))
    assert [f.source for f in result.findings if f.signal_id == "asks_fee"] == ["rules"]


def test_unreachable_model_falls_back_to_rules() -> None:
    result = check("Pay the registration fee of Rs 500.", extractor=BrokenExtractor())
    assert result.model_status == "unavailable"
    assert result.verdict == "LIKELY_SCAM"


def test_severe_findings_are_listed_first() -> None:
    message = "Reply within 2 hours. Pay Rs 999 joining fee."
    severities = [f.severity for f in check(message, extractor=None).findings]
    assert severities == sorted(severities, key=lambda s: s != "severe")


def test_claimed_company_gets_official_domain_to_verify() -> None:
    result = check("Offer from TCS, write to tcs.offers@gmail.com", extractor=None)
    assert [(v.company, v.domains) for v in result.verify] == [("Tata Consultancy Services", ("tcs.com",))]


def test_overlong_message_is_rejected() -> None:
    with pytest.raises(ValueError):
        check("a" * (MAX_MESSAGE_CHARS + 1), extractor=None)
