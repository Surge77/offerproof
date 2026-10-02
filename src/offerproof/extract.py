"""Asks a local open-weight model to read the message and quote evidence.

The model never decides the verdict. It answers narrow questions ("does it ask for money?") and must
quote the words it relied on. Quotes that don't appear in the message are thrown away, so the model
cannot invent a reason.
"""

from dataclasses import dataclass
import json
import re
from typing import Any

import httpx

from offerproof.catalog import load_signals
from offerproof.findings import Finding

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma3:4b"
# Local inference on a laptop GPU can take tens of seconds for a long message.
REQUEST_TIMEOUT_SECONDS = 120.0
MIN_QUOTE_CHARS = 4

# Model field -> signal it provides evidence for.
FLAG_FIELDS = {
    "asks_money": "asks_fee",
    "asks_secrets": "asks_secrets",
    "task_based_work": "task_scam",
    "pressure": "pressure",
    "asks_identity_docs": "identity_docs",
}
INTERVIEW_SIGNALS = {"chat_only": "chat_only_interview", "no_interview": "no_interview"}

_EVIDENCE = {
    "type": "object",
    "properties": {"present": {"type": "boolean"}, "quote": {"type": "string"}},
    "required": ["present", "quote"],
}
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "claimed_company": {"type": "string"},
        **{field: _EVIDENCE for field in FLAG_FIELDS},
        "interview": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "enum": [
                    "video_or_phone", "in_person", "chat_only", "no_interview", "not_mentioned"]},
                "quote": {"type": "string"},
            },
            "required": ["channel", "quote"],
        },
    },
    "required": ["claimed_company", *FLAG_FIELDS, "interview"],
}

SYSTEM_PROMPT = """You read job-related messages sent to fresh graduates in India and report facts.
Answer only with JSON matching the schema. For every field, "quote" must be copied word for word from
the message (a short phrase is enough). If something is not in the message, set present=false and quote="".

- asks_money: the candidate is asked to pay anything (fee, deposit, charges, top-up), even if "refundable".
  A sentence saying they will NOT be charged is not asking for money.
- asks_secrets: asks for an OTP, PIN, CVV, card number or banking password.
- asks_identity_docs: asks for Aadhaar, PAN, passport or bank account details.
- task_based_work: the job is paid online tasks such as liking videos, rating hotels or reviewing products.
  Coding tests, assessments and assignments are NOT task-based work.
- pressure: demands a decision or payment within hours, "today only", limited seats.
- interview.channel: how the interview happens. Phone or video calls are "video_or_phone".
  "chat_only" only when the message says the interview is held over Telegram/WhatsApp/text chat.
  "no_interview" only when the message says there is no interview. If the message does not describe
  how an interview will be held (for example a rejection or a general enquiry), use "not_mentioned".
- claimed_company: the employer the message claims to represent, or "" if none."""

EXAMPLE_MESSAGE = (
    "Dear candidate, you are shortlisted for Data Entry at Infosys. Salary 32,000. Interview will be on "
    "Telegram with HR. Pay Rs 1,500 refundable registration fee today to confirm your seat."
)
EXAMPLE_ANSWER = {
    "claimed_company": "Infosys",
    "asks_money": {"present": True, "quote": "Pay Rs 1,500 refundable registration fee"},
    "asks_secrets": {"present": False, "quote": ""},
    "asks_identity_docs": {"present": False, "quote": ""},
    "task_based_work": {"present": False, "quote": ""},
    "pressure": {"present": True, "quote": "today to confirm your seat"},
    "interview": {"channel": "chat_only", "quote": "Interview will be on Telegram"},
}


class ModelUnavailable(Exception):
    """The local model could not be reached or returned something unusable."""


@dataclass(frozen=True)
class Extraction:
    findings: list[Finding]
    claimed_company: str


def _normalise(text: str) -> str:
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    return " ".join(text.lower().split())


def quote_is_genuine(quote: str, message: str) -> bool:
    cleaned = _normalise(quote).strip(" .,\"'")
    return len(cleaned) >= MIN_QUOTE_CHARS and cleaned in _normalise(message)


def quote_supports(signal_id: str, quote: str) -> bool:
    """The quote must be about the claim, not just appear somewhere in the message."""
    evidence = load_signals()[signal_id].evidence
    return evidence is None or evidence.search(quote) is not None


def _accepted(signal_id: str, quote: str, message: str) -> bool:
    return quote_is_genuine(quote, message) and quote_supports(signal_id, quote)


def _finding(signal_id: str, quote: str) -> Finding:
    signal = load_signals()[signal_id]
    return Finding(
        signal_id=signal.id, severity=signal.severity, label=signal.label, why=signal.why,
        ask_back=signal.ask_back, quote=" ".join(quote.split()), source="model",
    )


def findings_from_answer(answer: dict[str, Any], message: str) -> Extraction:
    findings: list[Finding] = []
    for field, signal_id in FLAG_FIELDS.items():
        evidence = answer.get(field) or {}
        quote = str(evidence.get("quote", ""))
        if evidence.get("present") is True and _accepted(signal_id, quote, message):
            findings.append(_finding(signal_id, quote))
    interview = answer.get("interview") or {}
    signal_id = INTERVIEW_SIGNALS.get(str(interview.get("channel", "")))
    quote = str(interview.get("quote", ""))
    if signal_id and _accepted(signal_id, quote, message):
        findings.append(_finding(signal_id, quote))
    company = str(answer.get("claimed_company", "")).strip()
    return Extraction(findings=findings, claimed_company=company if company and re.search(
        re.escape(company), message, re.IGNORECASE) else "")


class OllamaExtractor:
    def __init__(self, base_url: str = DEFAULT_OLLAMA_URL, model: str = DEFAULT_MODEL,
                 transport: httpx.BaseTransport | None = None) -> None:
        self.model = model
        self._client = httpx.Client(base_url=base_url, timeout=REQUEST_TIMEOUT_SECONDS, transport=transport)

    def extract(self, message: str) -> Extraction:
        payload = {
            "model": self.model,
            "stream": False,
            "format": SCHEMA,
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": EXAMPLE_MESSAGE},
                {"role": "assistant", "content": json.dumps(EXAMPLE_ANSWER)},
                {"role": "user", "content": message},
            ],
        }
        try:
            response = self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            answer = json.loads(response.json()["message"]["content"])
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise ModelUnavailable(str(exc)) from exc
        if not isinstance(answer, dict):
            raise ModelUnavailable("model did not return a JSON object")
        return findings_from_answer(answer, message)
