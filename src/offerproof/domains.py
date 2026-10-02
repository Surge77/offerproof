"""Checks the sender's email domain against the company the message claims to be from."""

from dataclasses import dataclass
import re

from offerproof.catalog import Company, load_companies
from offerproof.findings import Finding

EMAIL = re.compile(r"\b[\w.+-]+@([\w-]+(?:\.[\w-]+)+)\b")


@dataclass(frozen=True)
class DomainReport:
    findings: list[Finding]
    claimed: list[Company]


def _is_official(domain: str, company: Company) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in company.domains)


def _mentioned_companies(text: str) -> list[Company]:
    lowered = text.lower()
    return [
        c for c in load_companies().companies
        if any(re.search(rf"\b{re.escape(alias)}\b", lowered) for alias in c.aliases)
    ]


# Short brand names (tcs, ibm) only count as a whole label, as in tcs-careers.in. Longer ones also
# count inside a label, as in infosyshr.com, where a 3-letter substring would match by accident.
MIN_SUBSTRING_ALIAS = 5


def _borrows_name(domain: str, company: Company) -> bool:
    labels = re.split(r"[.-]", domain)
    first_label = domain.split(".")[0]
    for alias in company.aliases:
        compact = alias.replace(" ", "")
        if compact in labels:
            return True
        if len(compact) >= MIN_SUBSTRING_ALIAS and compact in first_label:
            return True
    return False


def _lookalike_of(domain: str) -> Company | None:
    """A domain that borrows a company's name without being one of its official domains."""
    companies = load_companies().companies
    if any(_is_official(domain, c) for c in companies):
        return None
    return next((c for c in companies if _borrows_name(domain, c)), None)


def check_domains(text: str) -> DomainReport:
    catalog = load_companies()
    claimed = _mentioned_companies(text)
    findings: list[Finding] = []
    for match in EMAIL.finditer(text):
        domain = match.group(1).lower()
        address = match.group(0)
        lookalike = _lookalike_of(domain)
        if lookalike is not None:
            findings.append(Finding(
                signal_id="lookalike_domain",
                severity="severe",
                label=f"Email domain imitates {lookalike.name}",
                why=f"{lookalike.name} recruits only from {', '.join(lookalike.domains)}. "
                    f"{domain} is a different domain made to look like theirs.",
                ask_back=f"Can you write to me from an @{lookalike.domains[0]} address?",
                quote=address,
                source="domain",
            ))
            continue
        if domain in catalog.free_mail and claimed:
            names = ", ".join(c.name for c in claimed)
            findings.append(Finding(
                signal_id="free_mail_company",
                severity="severe",
                label=f"Personal email claiming to be {names}",
                why="Large employers recruit from their own company domain, never from Gmail, Yahoo or Outlook.",
                ask_back=f"Can you write to me from your official {claimed[0].name} email address?",
                quote=address,
                source="domain",
            ))
    return DomainReport(findings=_dedupe(findings), claimed=claimed)


def _dedupe(findings: list[Finding]) -> list[Finding]:
    seen: set[str] = set()
    unique: list[Finding] = []
    for f in findings:
        if f.signal_id not in seen:
            seen.add(f.signal_id)
            unique.append(f)
    return unique
