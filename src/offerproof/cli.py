"""Command line: `offerproof check message.txt` or `offerproof serve`."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from offerproof.verdict import Result, check

DEFAULT_PORT = 8766
VERDICT_TEXT = {"LIKELY_SCAM": "LIKELY SCAM", "UNVERIFIED": "UNVERIFIED"}
MODEL_NOTE = {
    "used": "Checked with pattern rules and the local model.",
    "unavailable": "Local model not reachable (is Ollama running?). Checked with pattern rules only.",
    "off": "Checked with pattern rules only.",
}


def _read_message(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    return Path(source).read_text(encoding="utf-8")


def format_result(result: Result) -> str:
    lines = [f"{VERDICT_TEXT[result.verdict]}: {result.summary}", ""]
    for f in result.findings:
        lines += [f"[{f.severity}] {f.label}", f'  "{f.quote}"', f"  {f.why}", f"  Ask them: {f.ask_back}", ""]
    for v in result.verify:
        lines.append(f"Verify: genuine {v.company} recruiters write from {', '.join('@' + d for d in v.domains)}")
    if result.findings:
        lines += ["", *result.report_steps]
    lines += ["", MODEL_NOTE[result.model_status]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="offerproof", description="Check a job offer for scam signs, locally.")
    commands = parser.add_subparsers(dest="command", required=True)

    check_cmd = commands.add_parser("check", help="check a message from a file, or '-' for stdin")
    check_cmd.add_argument("source")
    check_cmd.add_argument("--no-model", action="store_true", help="use pattern rules only")
    check_cmd.add_argument("--json", action="store_true", help="print the full result as JSON")

    serve_cmd = commands.add_parser("serve", help="run the web app on this computer")
    serve_cmd.add_argument("--port", type=int, default=DEFAULT_PORT)

    args = parser.parse_args(argv)

    if args.command == "serve":
        import uvicorn

        from offerproof.app import create_app
        uvicorn.run(create_app(), host="127.0.0.1", port=args.port)
        return 0

    from offerproof.app import default_extractor
    message = _read_message(args.source)
    result = check(message, None if args.no_model else default_extractor())
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False) if args.json else format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
