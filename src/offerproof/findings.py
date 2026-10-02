"""The shape every check reports in."""

from dataclasses import dataclass
from typing import Literal

from offerproof.catalog import Severity

Source = Literal["rules", "domain", "model"]


@dataclass(frozen=True)
class Finding:
    signal_id: str
    severity: Severity
    label: str
    why: str
    ask_back: str
    quote: str
    source: Source


MAX_QUOTE_CHARS = 200


def sentence_around(text: str, start: int, end: int) -> str:
    """Return the sentence or line containing text[start:end], trimmed for display."""
    left = max(text.rfind(sep, 0, start) for sep in (".", "\n", "!", "?"))
    rights = [i for i in (text.find(sep, end) for sep in (".", "\n", "!", "?")) if i != -1]
    right = min(rights) if rights else len(text)
    sentence = " ".join(text[left + 1 : right].split())
    if len(sentence) > MAX_QUOTE_CHARS:
        sentence = " ".join(text[start:end].split())
    return sentence
