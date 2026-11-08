"""The title rule: is a posting in my role?

My role is an analyst job in finance or fintech: financial, data, credit, risk, investment,
strategy, pricing and similar analysts, plus FP&A and business intelligence jobs.

A title is IN ROLE when it (compared in lower case)
  1. contains the word "analyst" together with at least one of the finance/data words in
     QUALIFIERS (for example "Financial Analyst", "Senior Data Analyst", "Summer Analyst,
     Investment Banking"), or contains "FP&A" or "business intelligence"; and
  2. contains none of the words in EXCLUDED (so "Security Analyst" and "Data Security Analyst" are out).
Every other title is out: "Software Engineer", "Account Executive", "Systems Analyst", "Analyst, Facilities".
"""

import re

QUALIFIERS = (
    "financ", "data", "business", "credit", "risk", "investment", "quantitative", "quant", "strategy",
    "strategic", "pricing", "treasury", "planning", "portfolio", "research", "market", "reporting",
    "analytics", "fraud", "underwriting", "accounting", "economic", "valuation", "equity", "capital",
    "revenue", "forecast",
)
EXCLUDED = (
    "cyber", "security", "threat", "siem", "soc analyst", "help desk", "helpdesk", "systems analyst",
    "it analyst", "network", "devops", "infrastructure",
)

ANALYST = re.compile(r"\banalysts?\b")
FPA = re.compile(r"\bfp\s*&\s*a\b|\bfp&a\b|\bfpa\b")
BUSINESS_INTELLIGENCE = re.compile(r"\bbusiness intelligence\b")


def in_role(title):
    """True when the title matches the title rule above."""
    text = (title or "").lower()
    if any(word in text for word in EXCLUDED):
        return False
    if FPA.search(text) or BUSINESS_INTELLIGENCE.search(text):
        return True
    return bool(ANALYST.search(text)) and any(word in text for word in QUALIFIERS)
