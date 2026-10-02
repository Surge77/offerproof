"""Combines rule, domain and model findings into a verdict. Plain code, no model involved."""

from dataclasses import dataclass, field
from typing import Literal, Protocol

from offerproof.catalog import load_companies
from offerproof.domains import check_domains
from offerproof.extract import Extraction, ModelUnavailable
from offerproof.findings import Finding
from offerproof.rules import scan

Verdict = Literal["LIKELY_SCAM", "UNVERIFIED"]
ModelStatus = Literal["used", "unavailable", "off"]

MAX_MESSAGE_CHARS = 20_000
REPORT_STEPS = (
    "Do not pay anything and do not share OTPs, PINs or documents.",
    "Report it at cybercrime.gov.in or call 1930 (India's cyber fraud helpline).",
)
SUMMARIES = {
    ("LIKELY_SCAM", True): "This message has clear signs of a job scam.",
    ("UNVERIFIED", True): "Some things here need checking before you reply.",
    ("UNVERIFIED", False): "No scam signs found. That does not make it genuine, so verify it yourself.",
}


class Extractor(Protocol):
    def extract(self, message: str) -> Extraction: ...


@dataclass(frozen=True)
class Verification:
    company: str
    domains: tuple[str, ...]


@dataclass(frozen=True)
class Result:
    verdict: Verdict
    summary: str
    findings: list[Finding]
    verify: list[Verification]
    model_status: ModelStatus
    report_steps: tuple[str, ...] = field(default=REPORT_STEPS)


def _merge(*groups: list[Finding]) -> list[Finding]:
    """One finding per signal. Earlier groups win, so a rule match is shown before the model's."""
    merged: dict[str, Finding] = {}
    for group in groups:
        for finding in group:
            merged.setdefault(finding.signal_id, finding)
    return sorted(merged.values(), key=lambda f: f.severity != "severe")


def decide(findings: list[Finding]) -> Verdict:
    return "LIKELY_SCAM" if any(f.severity == "severe" for f in findings) else "UNVERIFIED"


def check(message: str, extractor: Extractor | None) -> Result:
    if len(message) > MAX_MESSAGE_CHARS:
        raise ValueError(f"message is longer than {MAX_MESSAGE_CHARS} characters")

    rule_findings = scan(message)
    domain_report = check_domains(message)

    model_findings: list[Finding] = []
    model_status: ModelStatus = "off"
    claimed_by_model = ""
    if extractor is not None:
        try:
            extraction = extractor.extract(message)
            model_findings, claimed_by_model = extraction.findings, extraction.claimed_company
            model_status = "used"
        except ModelUnavailable:
            model_status = "unavailable"

    findings = _merge(domain_report.findings, rule_findings, model_findings)
    verdict = decide(findings)

    claimed = list(domain_report.claimed)
    if claimed_by_model:
        claimed += [c for c in load_companies().companies
                    if c not in claimed and claimed_by_model.lower() in (c.name.lower(), *c.aliases)]
    verify = [Verification(company=c.name, domains=c.domains) for c in claimed]

    return Result(
        verdict=verdict,
        summary=SUMMARIES[(verdict, bool(findings))],
        findings=findings,
        verify=verify,
        model_status=model_status,
    )
