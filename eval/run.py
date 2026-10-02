"""Measure OfferProof on labelled messages.

    python eval/run.py                 # rules, model and combined
    python eval/run.py --no-model      # rules only
    python eval/run.py eval/samples.yaml eval/private/*.yaml
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

import yaml

from offerproof.app import default_extractor
from offerproof.domains import check_domains
from offerproof.extract import ModelUnavailable
from offerproof.rules import scan
from offerproof.verdict import decide

DEFAULT_FILES = [Path(__file__).parent / "samples.yaml"]


@dataclass
class Score:
    caught: int = 0
    scams: int = 0
    false_alarms: int = 0
    reals: int = 0

    def add(self, label: str, flagged: bool) -> None:
        if label == "scam":
            self.scams += 1
            self.caught += flagged
        else:
            self.reals += 1
            self.false_alarms += flagged


def load(paths: list[Path]) -> list[dict[str, str]]:
    samples: list[dict[str, str]] = []
    for path in paths:
        samples += yaml.safe_load(path.read_text(encoding="utf-8"))["samples"]
    return samples


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--no-model", action="store_true")
    args = parser.parse_args()

    samples = load(args.files or DEFAULT_FILES)
    extractor = None if args.no_model else default_extractor()
    scores = {"Rules only": Score(), "Model only": Score(), "Combined": Score()}
    misses: list[str] = []

    for sample in samples:
        text, label = sample["text"], sample["label"]
        rule_findings = scan(text) + check_domains(text).findings
        model_findings = []
        if extractor is not None:
            try:
                model_findings = extractor.extract(text).findings
            except ModelUnavailable as exc:
                print(f"model unavailable: {exc}", file=sys.stderr)
                extractor = None

        rules_flag = decide(rule_findings) == "LIKELY_SCAM"
        model_flag = decide(model_findings) == "LIKELY_SCAM"
        combined_flag = rules_flag or model_flag
        scores["Rules only"].add(label, rules_flag)
        scores["Model only"].add(label, model_flag)
        scores["Combined"].add(label, combined_flag)
        if combined_flag != (label == "scam"):
            misses.append(f"{sample['id']} ({label})")

    if extractor is None:
        del scores["Model only"]

    print("| Checks | Scams caught | False alarms on real messages |")
    print("|---|---|---|")
    for name, s in scores.items():
        print(f"| {name} | {s.caught}/{s.scams} | {s.false_alarms}/{s.reals} |")
    if misses:
        print("\nWrong verdicts (combined): " + ", ".join(misses))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
