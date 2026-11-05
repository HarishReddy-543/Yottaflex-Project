"""Tests for Duplicate Detection and Handling."""

import pandas as pd
import pytest
from src.validator import DatasetValidator


def test_duplicate_primary_key_quarantine():
    """Verify that duplicate encounter_ids within a batch are routed to quarantine."""
    records = [
        {
            "encounter_id": "ENC-001",
            "patient_id": "PAT-1",
            "full_name": "Ravi Kumar",
            "email": "ravi@gmail.com",
            "phone_number": "+1-202-555-0101",
            "national_id": "111-22-3333",
            "birth_date": "1990-01-01",
            "gender": "Male",
            "provider_id": "PRV-101",
            "diagnosis_code": "I10",
            "diagnosis_desc": "Hypertension",
            "treatment_cost": 200.0,
            "encounter_timestamp": "2026-05-01T10:00:00Z"
        },
        {
            "encounter_id": "ENC-001",  # Duplicate encounter_id
            "patient_id": "PAT-1",
            "full_name": "Ravi Kumar",
            "email": "ravi@gmail.com",
            "phone_number": "+1-202-555-0101",
            "national_id": "111-22-3333",
            "birth_date": "1990-01-01",
            "gender": "Male",
            "provider_id": "PRV-101",
            "diagnosis_code": "I10",
            "diagnosis_desc": "Hypertension",
            "treatment_cost": 200.0,
            "encounter_timestamp": "2026-05-01T10:00:00Z"
        },
        {
            "encounter_id": "ENC-002",  # Distinct valid record
            "patient_id": "PAT-2",
            "full_name": "Priya Reddy",
            "email": "priya@gmail.com",
            "phone_number": "+1-202-555-0102",
            "national_id": "222-33-4444",
            "birth_date": "1995-02-02",
            "gender": "Female",
            "provider_id": "PRV-101",
            "diagnosis_code": "E11.9",
            "diagnosis_desc": "Diabetes",
            "treatment_cost": 450.0,
            "encounter_timestamp": "2026-05-02T10:00:00Z"
        }
    ]

    df = pd.DataFrame(records)
    validator = DatasetValidator(valid_providers=["PRV-101"])
    result = validator.validate(df, run_id="RUN_DUP_TEST")

    # 1st ENC-001 and ENC-002 valid, 2nd ENC-001 quarantined
    assert len(result.valid_df) == 2
    assert len(result.quarantined_df) == 1
    assert result.quarantined_df.iloc[0]["encounter_id"] == "ENC-001"
    assert result.quarantined_df.iloc[0]["rejection_code"] == "DUPLICATE_PRIMARY_KEY"
