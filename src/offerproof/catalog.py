"""Loads the signal and company catalogs shipped in `offerproof/data`."""

from dataclasses import dataclass
from functools import cache
from importlib import resources
import re
from typing import Any, Literal

import yaml

Severity = Literal["severe", "caution"]


@dataclass(frozen=True)
class Signal:
    id: str
    severity: Severity
    negatable: bool
    label: str
    why: str
    ask_back: str
    patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class Company:
    name: str
    aliases: tuple[str, ...]
    domains: tuple[str, ...]


@dataclass(frozen=True)
class CompanyCatalog:
    companies: tuple[Company, ...]
    free_mail: frozenset[str]


def _read_yaml(filename: str) -> dict[str, Any]:
    text = resources.files("offerproof").joinpath("data", filename).read_text(encoding="utf-8")
    return yaml.safe_load(text)


@cache
def load_signals() -> dict[str, Signal]:
    raw = _read_yaml("signals.yaml")["signals"]
    signals: dict[str, Signal] = {}
    for item in raw:
        severity = item["severity"]
        if severity not in ("severe", "caution"):
            raise ValueError(f"signal {item['id']}: unknown severity {severity!r}")
        signals[item["id"]] = Signal(
            id=item["id"],
            severity=severity,
            negatable=bool(item["negatable"]),
            label=item["label"],
            why=item["why"],
            ask_back=item["ask_back"],
            patterns=tuple(re.compile(p, re.IGNORECASE) for p in item["patterns"]),
        )
    return signals


@cache
def load_companies() -> CompanyCatalog:
    raw = _read_yaml("companies.yaml")
    companies = tuple(
        Company(
            name=c["name"],
            aliases=tuple(a.lower() for a in c["aliases"]),
            domains=tuple(d.lower() for d in c["domains"]),
        )
        for c in raw["companies"]
    )
    return CompanyCatalog(companies=companies, free_mail=frozenset(d.lower() for d in raw["free_mail"]))
