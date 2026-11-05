"""Tests for Data Profiler Module."""

import pandas as pd
import pytest
from src.profiler import DatasetProfiler


def test_profiler_detects_sensitive_fields():
    """Verify profiler accurately classifies PII/PHI columns."""
    sample_df = pd.DataFrame({
        "encounter_id": ["ENC-1", "ENC-2"],
        "patient_id": ["PAT-100", "PAT-101"],
        "full_name": ["John Doe", "Jane Smith"],
        "email": ["john@example.com", "jane@example.com"],
        "phone_number": ["+1-202-555-0100", "+1-202-555-0101"],
        "national_id": ["123-45-6789", "987-65-4321"],
        "birth_date": ["1990-05-12", "1985-08-20"],
        "treatment_cost": [150.0, 300.0]
    })

    profiler = DatasetProfiler()
    profile = profiler.profile(sample_df)

    dataset_metrics = profile["dataset_metrics"]
    assert dataset_metrics["total_rows"] == 2
    assert "email" in dataset_metrics["sensitive_columns"]
    assert "full_name" in dataset_metrics["sensitive_columns"]
    assert "patient_id" in dataset_metrics["sensitive_columns"]
    assert "phone_number" in dataset_metrics["sensitive_columns"]


def test_profiler_null_and_duplicate_metrics():
    """Verify null and duplicate percentage calculations."""
    df = pd.DataFrame({
        "id": [1, 2, 2, None],
        "val": ["A", "B", "B", "D"]
    })
    profiler = DatasetProfiler()
    profile = profiler.profile(df)

    col_profiles = {c["column_name"]: c for c in profile["columns"]}
    assert col_profiles["id"]["null_count"] == 1
    assert col_profiles["id"]["null_percentage"] == 25.0
    assert profile["dataset_metrics"]["exact_duplicate_rows"] == 1
