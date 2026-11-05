"""Data Profiler Module.

Profiles datasets for:
- Data types, missingness (null counts and percentages)
- Cardinality, unique value ratios, duplicate rows
- Automated sensitive field (PII/PHI) identification
- Sensitivity classification (Direct Identifier, Quasi-Identifier, Clinical Data)
- Recommended privacy actions (Tokenization, Masking, Generalization, Minimization)
"""

import re
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd


# Regex Patterns for Sensitive Data Detection
PII_REGEX_PATTERNS = {
    "email": re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"),
    "phone": re.compile(r"^(\+\d{1,3}[- ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}$"),
    "national_id": re.compile(r"^\d{3}-\d{2}-\d{4}$"),
    "date_of_birth": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
}

# Semantic Keyword Mappings
SEMANTIC_PII_KEYWORDS = {
    "DIRECT_IDENTIFIER": ["name", "full_name", "first_name", "last_name", "email", "phone", "national_id", "ssn"],
    "SURROGATE_IDENTIFIER": ["patient_id", "mrn", "member_id", "user_id"],
    "QUASI_IDENTIFIER": ["birth_date", "dob", "age", "zip", "postal_code", "gender"],
    "SENSITIVE_CLINICAL": ["diagnosis", "treatment", "prescription", "condition", "cost", "biometric"],
}


class DatasetProfiler:
    """Profiles a dataset for data quality, distribution, and sensitive fields."""

    def __init__(self, pii_patterns: Optional[Dict[str, str]] = None):
        self.pii_patterns = PII_REGEX_PATTERNS.copy()
        if pii_patterns:
            for k, pat in pii_patterns.items():
                self.pii_patterns[k] = re.compile(pat)

    def detect_field_sensitivity(self, col_name: str, sample_series: pd.Series) -> Dict[str, Any]:
        """Classify sensitivity of a column using both name semantics and sample data patterns."""
        col_lower = col_name.lower()
        cleaned_series = sample_series.dropna().astype(str).str.strip()

        matched_pattern = None
        sample_match_rate = 0.0

        if not cleaned_series.empty:
            sample_size = min(len(cleaned_series), 200)
            sample_subset = cleaned_series.iloc[:sample_size]

            for pattern_name, regex in self.pii_patterns.items():
                matches = sample_subset.apply(lambda val: bool(regex.match(str(val)))).sum()
                rate = matches / sample_size
                if rate > 0.5:
                    matched_pattern = pattern_name
                    sample_match_rate = round(float(rate), 4)
                    break

        # Semantic heuristic
        sensitivity_category = "NON_SENSITIVE"
        recommended_action = "KEEP"

        for category, keywords in SEMANTIC_PII_KEYWORDS.items():
            if any(kw in col_lower for kw in keywords):
                sensitivity_category = category
                break

        # Override or refine based on pattern matches
        if matched_pattern == "email":
            sensitivity_category = "DIRECT_IDENTIFIER"
            recommended_action = "MASK"
        elif matched_pattern == "phone":
            sensitivity_category = "DIRECT_IDENTIFIER"
            recommended_action = "MASK"
        elif matched_pattern == "national_id":
            sensitivity_category = "DIRECT_IDENTIFIER"
            recommended_action = "TOKENIZE_OR_DROP"
        elif "patient_id" in col_lower:
            sensitivity_category = "SURROGATE_IDENTIFIER"
            recommended_action = "TOKENIZE"
        elif "name" in col_lower:
            sensitivity_category = "DIRECT_IDENTIFIER"
            recommended_action = "MASK"
        elif "birth" in col_lower or "dob" in col_lower:
            sensitivity_category = "QUASI_IDENTIFIER"
            recommended_action = "GENERALIZE"
        elif sensitivity_category == "SENSITIVE_CLINICAL":
            recommended_action = "PRESERVE_ANALYTICAL"

        return {
            "sensitivity_category": sensitivity_category,
            "detected_pattern": matched_pattern,
            "pattern_match_rate": sample_match_rate,
            "recommended_action": recommended_action,
        }

    def profile(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Perform comprehensive profiling of a dataset.

        Args:
            df: Input pandas DataFrame.

        Returns:
            Dictionary containing dataset-level and column-level metrics.
        """
        total_rows = len(df)
        total_columns = len(df.columns)
        exact_duplicate_rows = int(df.duplicated().sum())

        column_profiles = []
        sensitive_fields_detected = []

        for col in df.columns:
            series = df[col]
            null_count = int(series.isna().sum())
            null_pct = round(float(null_count / total_rows * 100), 2) if total_rows > 0 else 0.0
            distinct_count = int(series.nunique(dropna=True))
            cardinality_ratio = round(float(distinct_count / total_rows), 4) if total_rows > 0 else 0.0

            # Sensitivity analysis
            sensitivity_info = self.detect_field_sensitivity(col, series)

            col_profile = {
                "column_name": col,
                "data_type": str(series.dtype),
                "null_count": null_count,
                "null_percentage": null_pct,
                "distinct_count": distinct_count,
                "cardinality_ratio": cardinality_ratio,
                **sensitivity_info,
            }

            column_profiles.append(col_profile)

            if sensitivity_info["sensitivity_category"] in [
                "DIRECT_IDENTIFIER",
                "SURROGATE_IDENTIFIER",
                "QUASI_IDENTIFIER",
            ]:
                sensitive_fields_detected.append(col)

        profile_summary = {
            "dataset_metrics": {
                "total_rows": total_rows,
                "total_columns": total_columns,
                "exact_duplicate_rows": exact_duplicate_rows,
                "duplicate_percentage": round(float(exact_duplicate_rows / total_rows * 100), 2)
                if total_rows > 0
                else 0.0,
                "sensitive_column_count": len(sensitive_fields_detected),
                "sensitive_columns": sensitive_fields_detected,
            },
            "columns": column_profiles,
        }

        return profile_summary
