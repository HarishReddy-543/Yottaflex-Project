"""End-to-End Pipeline Integration Tests."""

import pandas as pd
import pytest
from src.generator import generate_encounters_dataset
from src.pipeline import PrivacyPipeline


@pytest.fixture
def temp_pipeline(tmp_path):
    """Create isolated test pipeline instance with temporary paths."""
    config = {
        "pipeline": {
            "name": "test-pipeline",
            "hmac_secret_salt": "test_secure_salt_999",
            "environment": "test"
        },
        "storage": {
            "db_path": str(tmp_path / "test_audit.sqlite"),
            "output_dir": str(tmp_path / "output"),
            "quarantine_dir": str(tmp_path / "quarantine"),
            "reports_dir": str(tmp_path / "reports"),
            "target_format": "both"
        }
    }
    return PrivacyPipeline(custom_config=config)


def test_pipeline_end_to_end_happy_path(temp_pipeline):
    """Test full pipeline execution on valid synthetic data."""
    df, _ = generate_encounters_dataset(num_records=50, invalid_ratio=0.0, duplicate_ratio=0.0, seed=10)
    result = temp_pipeline.run(df, run_id="TEST_RUN_HAPPY")

    assert result["status"] == "SUCCESS"
    assert result["input_count"] == 50
    assert result["valid_count"] == 50
    assert result["quarantined_count"] == 0
    assert result["published_count"] == 50
    assert result["reconciliation"]["reconciliation_status"] == "BALANCED"


def test_pipeline_privacy_leak_assertion(temp_pipeline, tmp_path):
    """Verify strictly that raw sensitive identifiers are NOT present in analytical output."""
    df, _ = generate_encounters_dataset(num_records=20, seed=12)
    result = temp_pipeline.run(df, run_id="TEST_RUN_PRIVACY")

    output_csv = tmp_path / "output/analytical_encounters.csv"
    published_df = pd.read_csv(output_csv)

    forbidden_fields = [
        "patient_id",
        "full_name",
        "email",
        "phone_number",
        "national_id",
        "birth_date",
    ]

    for field in forbidden_fields:
        assert field not in published_df.columns, f"Privacy violation: raw field '{field}' leaked into analytical dataset!"

    # Allowed safe minimized fields must be present
    assert "patient_token" in published_df.columns
    assert "masked_name" in published_df.columns
    assert "masked_email" in published_df.columns
    assert "age_group" in published_df.columns


def test_pipeline_reconciliation_math(temp_pipeline):
    """Verify that input == valid + quarantined and cost aggregates balance with zero discrepancy."""
    df, meta = generate_encounters_dataset(num_records=100, invalid_ratio=0.10, duplicate_ratio=0.05, seed=42)
    result = temp_pipeline.run(df, run_id="TEST_RUN_RECON")

    assert result["status"] == "SUCCESS"
    reconciliation = result["reconciliation"]
    counts = reconciliation["counts"]

    assert counts["is_count_balanced"] is True
    assert counts["input_records"] == counts["valid_records"] + counts["quarantined_records"]
    assert reconciliation["financial_aggregate_reconciliation"]["is_cost_balanced"] is True
    assert reconciliation["financial_aggregate_reconciliation"]["difference"] == 0.0


def test_pipeline_missing_schema_column_raises(temp_pipeline):
    """Verify that unexpected schema change (missing required column) raises error."""
    bad_df = pd.DataFrame({
        "encounter_id": ["ENC-1"],
        "unexpected_col": ["XYZ"]
    })

    with pytest.raises(ValueError, match="Schema Conformance Error: Missing required columns"):
        temp_pipeline.run(bad_df, run_id="TEST_SCHEMA_ERR")


def test_pipeline_empty_batch_handling(temp_pipeline):
    """Verify empty input dataset is handled gracefully without crash."""
    empty_df = pd.DataFrame(columns=[
        "encounter_id", "patient_id", "full_name", "email", "phone_number",
        "national_id", "birth_date", "gender", "provider_id", "diagnosis_code",
        "diagnosis_desc", "treatment_cost", "encounter_timestamp"
    ])

    result = temp_pipeline.run(empty_df, run_id="TEST_EMPTY")
    assert result["status"] == "SUCCESS"
    assert result["input_count"] == 0
    assert result["valid_count"] == 0
    assert result["quarantined_count"] == 0
    assert result["published_count"] == 0
