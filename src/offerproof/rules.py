"""Pattern-based scam signals. Deterministic, so every result can be tested and explained."""

import re

from offerproof.catalog import Signal, load_signals
from offerproof.findings import Finding, sentence_around

# How far back from a match to look for a negating word, within the same clause. Wide enough for
# lists like "we never ask for a registration fee or security deposit".
NEGATION_WINDOW_CHARS = 80
NEGATION = re.compile(r"\b(no|not|never|don't|do not|doesn't|does not|won't|will not|without|zero)\b", re.IGNORECASE)


def _is_negated(text: str, match_start: int) -> bool:
    window = text[max(0, match_start - NEGATION_WINDOW_CHARS) : match_start]
    clause = re.split(r"[.\n!?;]", window)[-1]
    return NEGATION.search(clause) is not None


def _first_match(signal: Signal, text: str) -> re.Match[str] | None:
    for pattern in signal.patterns:
        for match in pattern.finditer(text):
            if signal.negatable and _is_negated(text, match.start()):
                continue
            return match
    return None


def scan(text: str) -> list[Finding]:
    """Return one finding per signal that fires, quoting the sentence that triggered it."""
    findings: list[Finding] = []
    for signal in load_signals().values():
        match = _first_match(signal, text)
        if match is None:
            continue
        findings.append(
            Finding(
                signal_id=signal.id,
                severity=signal.severity,
                label=signal.label,
                why=signal.why,
                ask_back=signal.ask_back,
                quote=sentence_around(text, match.start(), match.end()),
                source="rules",
            )
        )
    return findings
