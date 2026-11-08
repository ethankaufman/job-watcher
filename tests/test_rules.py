import pytest

from watcher.rules import in_role


@pytest.mark.parametrize("title", [
    "Financial Analyst",
    "Senior Financial Analyst, Revenue Accounting",
    "Data Analyst",
    "Senior Data Analyst, Payments",
    "Credit Risk Analyst II",
    "Summer Analyst, Investment Banking",
    "Investment Banking – Financial Institutions Group – Analyst",
    "Quantitative Analyst - CIO Office",
    "Finance (FP&A) Analyst - 12 month fixed-term contract",
    "FP&A Manager",
    "Director, FPA",
    "Business Intelligence Developer",
    "Senior Business Intelligence Engineer",
    "Pricing Analysts, Treasury",
    "Research Analyst",
    "FINANCIAL ANALYST",  # case does not matter
])
def test_these_titles_are_in_role(title):
    assert in_role(title) is True


@pytest.mark.parametrize("title", [
    "Software Engineer",
    "Account Executive, Enterprise",
    "Analyst, Facilities",          # an analyst, but not finance or data
    "Systems Analyst, Finance",      # excluded: an IT role
    "Security Analyst",
    "Data Security Analyst",         # has "data" but is a security role
    "Cyber Threat Analyst, Financial Crimes",
    "Senior Compensation Analyst",
    "HRIS Analyst (Workday)",
    "Financial Planning Advisor",    # "financ" and "planning", but no "analyst"
    "Data Engineer",
    "Analytics Engineer",
    "Product Designer",
    "",
    None,
])
def test_these_titles_are_not_in_role(title):
    assert in_role(title) is False


def test_the_word_analyst_must_stand_alone():
    assert in_role("Analystic Data Lead") is False  # 'analystic' is not the word 'analyst'
