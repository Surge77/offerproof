import pytest

from offerproof.rules import scan


def fired(text: str) -> set[str]:
    return {f.signal_id for f in scan(text)}


@pytest.mark.parametrize("text", [
    "Please pay a refundable registration fee of Rs 1,999 to confirm.",
    "Kindly transfer ₹2500 for your laptop deposit before joining.",
    "A security deposit is required for onboarding.",
])
def test_flags_requests_for_money(text: str) -> None:
    assert "asks_fee" in fired(text)


@pytest.mark.parametrize("text", [
    "Infosys does not charge any registration fee at any stage.",
    "We never ask candidates for a security deposit.",
    "We never ask candidates for a registration fee or security deposit.",
])
def test_ignores_fee_disclaimers(text: str) -> None:
    assert "asks_fee" not in fired(text)


def test_negation_in_an_earlier_sentence_does_not_hide_a_fee() -> None:
    assert "asks_fee" in fired("Don't miss this chance. Pay the registration fee of Rs 500 today.")


def test_flags_task_scam() -> None:
    text = "Earn by liking YouTube videos. Complete prepaid tasks to unlock higher commission per task."
    assert "task_scam" in fired(text)


def test_would_like_to_schedule_a_video_call_is_not_a_task_scam() -> None:
    assert "task_scam" not in fired("We'd like to schedule a 45-minute video interview next week.")


def test_flags_chat_only_interview() -> None:
    assert "chat_only_interview" in fired("Your interview will be conducted on Telegram by our HR.")


def test_flags_hiring_without_interview() -> None:
    assert "no_interview" in fired("No interview required, direct joining from Monday.")


def test_flags_otp_request() -> None:
    assert "asks_secrets" in fired("Share the OTP you receive to complete verification.")


def test_identity_documents_are_only_a_caution() -> None:
    findings = {f.signal_id: f for f in scan("Send your Aadhaar and PAN card on this number.")}
    assert findings["identity_docs"].severity == "caution"


def test_quote_is_the_triggering_sentence() -> None:
    text = "Congratulations on your selection. Pay the training fee of Rs 999 today. Regards, HR"
    finding = next(f for f in scan(text) if f.signal_id == "asks_fee")
    assert finding.quote == "Pay the training fee of Rs 999 today"


def test_ordinary_recruiter_email_fires_nothing_severe() -> None:
    text = (
        "Hi Tejas, thanks for applying for the Software Engineer role. We'd like to schedule a 45-minute "
        "video interview next week. Please share three time slots that work for you."
    )
    assert all(f.severity != "severe" for f in scan(text))
