"""Tests for Privacy Transformations (Tokenization, Masking, Generalization)."""

import pytest
from src.privacy import date_to_age_bracket, generate_hmac_token, mask_email, mask_name, mask_phone


def test_deterministic_tokenization():
    """Verify HMAC tokenization is strictly deterministic and salt-sensitive."""
    salt_1 = "salt_alpha"
    salt_2 = "salt_beta"
    val = "PAT-10045"

    token_1a = generate_hmac_token(val, salt=salt_1, prefix="TOK_")
    token_1b = generate_hmac_token(val, salt=salt_1, prefix="TOK_")
    token_2 = generate_hmac_token(val, salt=salt_2, prefix="TOK_")

    assert token_1a is not None
    assert token_1a == token_1b, "Same input with same salt must yield identical token"
    assert token_1a != token_2, "Different salts must yield different tokens"
    assert token_1a.startswith("TOK_")


def test_name_masking():
    """Verify name initial masking."""
    assert mask_name("Ravi Kumar") == "R*** K****"
    assert mask_name("Priya") == "P****"
    assert mask_name("A B") == "A B"
    assert mask_name(None) is None


def test_email_masking():
    """Verify email masking preserves domain but masks user prefix."""
    assert mask_email("ravi@gmail.com") == "ra***@gmail.com"
    assert mask_email("a@company.org") == "a***@company.org"
    assert mask_email(None) is None


def test_phone_masking():
    """Verify phone masking preserves last 4 digits."""
    assert mask_phone("+1-202-555-0193") == "***-***-0193"
    assert mask_phone("(555) 123-4567") == "***-***-4567"
    assert mask_phone(None) is None


def test_age_generalization():
    """Verify birth date to age cohort categorization."""
    # Reference date is 2026-01-01
    assert date_to_age_bracket("2010-06-15", reference_date_str="2026-01-01") == "<18"      # ~15 yrs
    assert date_to_age_bracket("2000-01-01", reference_date_str="2026-01-01") == "18-29"    # 26 yrs
    assert date_to_age_bracket("1985-05-20", reference_date_str="2026-01-01") == "30-49"    # 40 yrs
    assert date_to_age_bracket("1970-11-04", reference_date_str="2026-01-01") == "50-64"    # 55 yrs
    assert date_to_age_bracket("1950-03-12", reference_date_str="2026-01-01") == "65+"      # 75 yrs
    assert date_to_age_bracket("invalid-date") == "UNKNOWN"
    assert date_to_age_bracket(None) == "UNKNOWN"
