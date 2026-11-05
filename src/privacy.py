"""Privacy Transformation Engine.

Implements:
1. Deterministic Tokenization using HMAC-SHA256 with secret salt.
2. Configurable Masking (Names, Emails, Phone numbers).
3. Quasi-Identifier Generalization (Date of birth to age cohorts).
"""

from datetime import datetime
import hashlib
import hmac
import re
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd


def generate_hmac_token(value: Any, salt: str, prefix: str = "TOK_", length: int = 16) -> str:
    """Generate a deterministic HMAC-SHA256 token for a given value.

    Args:
        value: Input string or identifier to tokenize.
        salt: Secret cryptographic salt key.
        prefix: Namespace prefix for the generated token.
        length: Number of hex characters to retain.

    Returns:
        Deterministic token string, or None if value is missing.
    """
    if pd.isna(value) or str(value).strip() == "":
        return None

    raw_str = str(value).strip().encode("utf-8")
    salt_bytes = salt.encode("utf-8")
    token_hash = hmac.new(salt_bytes, raw_str, hashlib.sha256).hexdigest()
    return f"{prefix}{token_hash[:length]}"


def mask_name(name: Any) -> Optional[str]:
    """Mask a person's name, retaining initial letter of each component.

    Example:
        'Ravi Kumar' -> 'R*** K****'
        'Priya' -> 'P****'
    """
    if pd.isna(name) or str(name).strip() == "":
        return None

    parts = str(name).strip().split()
    masked_parts = []
    for part in parts:
        if len(part) <= 1:
            masked_parts.append(part)
        elif len(part) == 2:
            masked_parts.append(f"{part[0]}*")
        else:
            masked_parts.append(f"{part[0]}{'*' * (len(part) - 1)}")
    return " ".join(masked_parts)


def mask_email(email: Any) -> Optional[str]:
    """Mask an email address while preserving domain for categorical analytics.

    Example:
        'ravi@gmail.com' -> 'ra***@gmail.com'
        'a@company.org' -> 'a***@company.org'
    """
    if pd.isna(email) or str(email).strip() == "":
        return None

    val = str(email).strip()
    if "@" not in val:
        return "****"

    user, domain = val.split("@", 1)
    if len(user) <= 2:
        masked_user = f"{user[0]}***"
    else:
        masked_user = f"{user[:2]}***"

    return f"{masked_user}@{domain}"


def mask_phone(phone: Any) -> Optional[str]:
    """Mask a phone number preserving only the last 4 digits.

    Example:
        '+1-202-555-0193' -> '***-***-0193'
    """
    if pd.isna(phone) or str(phone).strip() == "":
        return None

    digits = re.sub(r"\D", "", str(phone))
    if len(digits) >= 4:
        return f"***-***-{digits[-4:]}"
    return "****"


def date_to_age_bracket(
    birth_date: Any,
    reference_date_str: str = "2026-01-01"
) -> Optional[str]:
    """Generalize an exact birth date into an analytical age cohort.

    Age cohorts:
        - '<18'
        - '18-29'
        - '30-49'
        - '50-64'
        - '65+'
    """
    if pd.isna(birth_date) or str(birth_date).strip() == "":
        return "UNKNOWN"

    try:
        bdate = datetime.strptime(str(birth_date).strip()[:10], "%Y-%m-%d")
        ref = datetime.strptime(reference_date_str, "%Y-%m-%d")
        age = ref.year - bdate.year - ((ref.month, ref.day) < (bdate.month, bdate.day))

        if age < 0:
            return "UNKNOWN"
        elif age < 18:
            return "<18"
        elif 18 <= age <= 29:
            return "18-29"
        elif 30 <= age <= 49:
            return "30-49"
        elif 50 <= age <= 64:
            return "50-64"
        else:
            return "65+"
    except Exception:
        return "UNKNOWN"


class PrivacyTransformer:
    """Orchestrates privacy transformations based on configuration rules."""

    def __init__(self, privacy_rules: dict, secret_salt: str = "default_secure_salt"):
        self.rules = privacy_rules
        self.secret_salt = secret_salt

    def apply_transformations(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply configured tokenization, masking, and generalization to DataFrame.

        Args:
            df: Validated DataFrame.

        Returns:
            Transformed DataFrame with tokenized and masked columns added.
        """
        if df.empty:
            return df.copy()

        transformed = df.copy()

        transformations = self.rules.get("transformations", {})

        # 1. Tokenization
        for tok_rule in transformations.get("tokenization", []):
            src_col = tok_rule.get("field")
            tgt_col = tok_rule.get("target_field")
            prefix = tok_rule.get("prefix", "TOK_")

            if src_col in transformed.columns:
                transformed[tgt_col] = transformed[src_col].apply(
                    lambda v: generate_hmac_token(v, salt=self.secret_salt, prefix=prefix)
                )

        # 2. Masking
        for mask_rule in transformations.get("masking", []):
            src_col = mask_rule.get("field")
            tgt_col = mask_rule.get("target_field")
            strategy = mask_rule.get("strategy")

            if src_col in transformed.columns:
                if strategy == "name_initial_mask":
                    transformed[tgt_col] = transformed[src_col].apply(mask_name)
                elif strategy == "email_mask":
                    transformed[tgt_col] = transformed[src_col].apply(mask_email)
                elif strategy == "phone_last4":
                    transformed[tgt_col] = transformed[src_col].apply(mask_phone)

        # 3. Generalization
        for gen_rule in transformations.get("generalization", []):
            src_col = gen_rule.get("field")
            tgt_col = gen_rule.get("target_field")
            strategy = gen_rule.get("strategy")
            ref_date = gen_rule.get("reference_date", "2026-01-01")

            if src_col in transformed.columns and strategy == "date_to_age_bracket":
                transformed[tgt_col] = transformed[src_col].apply(
                    lambda v: date_to_age_bracket(v, reference_date_str=ref_date)
                )

        return transformed
