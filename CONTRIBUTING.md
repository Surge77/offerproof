# Contributing

The most useful contribution is a scam OfferProof misses, or a genuine message it wrongly flags.

## Report a message

Open an issue with the message text. **Remove names, phone numbers, email usernames, UPI IDs and
links first.** Keep the wording otherwise unchanged; the wording is what matters.

## Add or improve a pattern

Signals live in [`src/offerproof/data/signals.yaml`](src/offerproof/data/signals.yaml). Each one has:

- `severity`: `severe` if the sign alone means a scam, `caution` if it only needs checking
- `negatable`: `true` if a nearby "never" / "no" / "do not" should cancel the match
- `patterns`: Python regular expressions, matched case-insensitively
- `label`, `why`, `ask_back`: the text shown to the user

Prefer a narrow pattern over a broad one. A false alarm on a genuine offer costs the user an opportunity.

Add the message to [`eval/samples.yaml`](eval/samples.yaml) with `source: reported`, and a test in
[`tests/test_rules.py`](tests/test_rules.py) that shows the new pattern firing and, where it applies,
not firing on similar genuine wording.

## Add a company

Add it to [`src/offerproof/data/companies.yaml`](src/offerproof/data/companies.yaml) with the domains
its recruiters actually send from. Only include domains you can confirm on the company's own website.

## Before opening a pull request

```
pip install -e ".[dev]"
pytest
pyright
python eval/run.py --no-model
```

Mention any change in the eval numbers in the pull request.
