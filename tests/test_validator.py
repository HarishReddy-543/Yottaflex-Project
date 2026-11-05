"""Tests for Schema and Business Rules Validator."""

import pandas as pd
import pytest
from src.validator import DatasetValidator


@pytest.fixture
def base_valid_record():
    return {
        "encounter_id": "ENC-001",
        "patient_id": "PAT-1001",
        "full_name": "Ravi Kumar",
        "email": "ravi@gmail.com",
        "phone_number": "+1-202-555-0199",
        "national_id": "123-45-6789",
        "birth_date": "1992-04-10",
        "gender": "Male",
        "provider_id": "PRV-101",
        "diagnosis_code": "E11.9",
        "diagnosis_desc": "Type 2 diabetes",
        "treatment_cost": 350.0,
        "encounter_timestamp": "2026-05-10T12:00:00Z"
    }


def test_validator_happy_path(base_valid_record):
    """Happy path: valid single row should pass without quarantine."""
    df = pd.DataFrame([base_valid_record])
    validator = DatasetValidator(valid_providers=["PRV-101"])
    result = validator.validate(df, run_id="RUN_TEST")

    assert len(result.valid_df) == 1
    assert len(result.quarantined_df) == 0
    assert result.metrics["valid_records"] == 1


def test_validator_empty_input():
    """Empty input should return empty valid and quarantine without crashing."""
    df = pd.DataFrame()
    validator = DatasetValidator()
    result = validator.validate(df, run_id="RUN_EMPTY")

    assert len(result.valid_df) == 0
    assert len(result.quarantined_df) == 0
    assert result.metrics["total_input_records"] == 0


def test_validator_null_primary_key(base_valid_record):
    """Null encounter_id should be quarantined with NULL_PRIMARY_KEY."""
    record = base_valid_record.copy()
    record["encounter_id"] = None
    df = pd.DataFrame([record])

    validator = DatasetValidator(valid_providers=["PRV-101"])
    result = validator.validate(df, run_id="RUN_TEST")

    assert len(result.valid_df) == 0
    assert len(result.quarantined_df) == 1
    assert result.quarantined_df.iloc[0]["rejection_code"] == "NULL_PRIMARY_KEY"


def test_validator_missing_required_fields(base_valid_record):
    """Missing patient_id or full_name should be quarantined with MISSING_REQUIRED_FIELD."""
    rec1 = base_valid_record.copy()
    rec1["patient_id"] = None
    rec2 = base_valid_record.copy()
    rec2["encounter_id"] = "ENC-002"
    rec2["full_name"] = "  "

    df = pd.DataFrame([rec1, rec2])
    validator = DatasetValidator(valid_providers=["PRV-101"])
    result = validator.validate(df, run_id="RUN_TEST")

    assert len(result.valid_df) == 0
    assert len(result.quarantined_df) == 2
    assert (result.quarantined_df["rejection_code"] == "MISSING_REQUIRED_FIELD").all()


def test_validator_edge_case_negative_cost(base_valid_record):
    """Domain edge case: negative treatment cost must be quarantined."""
    record = base_valid_record.copy()
    record["treatment_cost"] = -50.0
    df = pd.DataFrame([record])

    validator = DatasetValidator(valid_providers=["PRV-101"])
    result = validator.validate(df, run_id="RUN_TEST")

    assert len(result.valid_df) == 0
    assert len(result.quarantined_df) == 1
    assert result.quarantined_df.iloc[0]["rejection_code"] == "INVALID_DOMAIN_VALUE"


def test_validator_edge_case_referential_integrity(base_valid_record):
    """Domain edge case: unrecognized provider_id must be quarantined."""
    record = base_valid_record.copy()
    record["provider_id"] = "PRV-FAKE-999"
    df = pd.DataFrame([record])

    validator = DatasetValidator(valid_providers=["PRV-101"])
    result = validator.validate(df, run_id="RUN_TEST")

    assert len(result.valid_df) == 0
    assert len(result.quarantined_df) == 1
    assert result.quarantined_df.iloc[0]["rejection_code"] == "REFERENTIAL_INTEGRITY_VIOLATION"


def test_validator_edge_case_malformed_email(base_valid_record):
    """Malformed email should trigger MALFORMED_EMAIL."""
    record = base_valid_record.copy()
    record["email"] = "bad-email-without-at"
    df = pd.DataFrame([record])

    validator = DatasetValidator(valid_providers=["PRV-101"])
    result = validator.validate(df, run_id="RUN_TEST")

    assert len(result.valid_df) == 0
    assert len(result.quarantined_df) == 1
    assert result.quarantined_df.iloc[0]["rejection_code"] == "MALFORMED_EMAIL"


def test_validator_edge_case_malformed_timestamp(base_valid_record):
    """Malformed timestamp should trigger MALFORMED_TIMESTAMP."""
    record = base_valid_record.copy()
    record["encounter_timestamp"] = "NOT_A_VALID_DATE"
    df = pd.DataFrame([record])

    validator = DatasetValidator(valid_providers=["PRV-101"])
    result = validator.validate(df, run_id="RUN_TEST")

    assert len(result.valid_df) == 0
    assert len(result.quarantined_df) == 1
    assert result.quarantined_df.iloc[0]["rejection_code"] == "MALFORMED_TIMESTAMP"
