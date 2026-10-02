from offerproof.domains import check_domains


def signal_ids(text: str) -> set[str]:
    return {f.signal_id for f in check_domains(text).findings}


def test_personal_email_claiming_a_company_is_severe() -> None:
    report = check_domains("Greetings from Infosys HR. Reply to infosys.hiring.desk@gmail.com")
    assert [f.signal_id for f in report.findings] == ["free_mail_company"]
    assert report.findings[0].severity == "severe"


def test_personal_email_without_a_claimed_company_is_not_flagged() -> None:
    assert signal_ids("Hi, I run a small studio. Mail me at priya.design@gmail.com") == set()


def test_lookalike_domain_with_short_brand_is_flagged() -> None:
    assert "lookalike_domain" in signal_ids("Offer letter from hr@tcs-careers.in")


def test_lookalike_domain_with_brand_inside_label_is_flagged() -> None:
    assert "lookalike_domain" in signal_ids("Contact recruitment@infosyshr.com")


def test_official_domain_and_subdomain_are_accepted() -> None:
    assert signal_ids("From careers@infosys.com, cc talent@in.infosys.com about Infosys") == set()


def test_claimed_companies_are_reported_for_verification() -> None:
    report = check_domains("This is an offer from Wipro.")
    assert [c.name for c in report.claimed] == ["Wipro"]
