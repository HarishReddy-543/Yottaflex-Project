"""Tests for Pipeline Idempotency and Safe Reruns."""

import sqlite3
import pandas as pd
import pytest
from src.audit import AuditStore


def test_idempotent_publishing(tmp_path):
    """Verify that rerunning the same records multiple times does not inflate analytical counts."""
    db_file = tmp_path / "test_idempotency.sqlite"
    audit = AuditStore(db_path=db_file)

    test_data = pd.DataFrame([
        {
            "encounter_id": "ENC-1001",
            "patient_token": "TOK_PAT_AAAA",
            "masked_name": "R*** K****",
            "masked_email": "ra***@gmail.com",
            "gender": "Male",
            "age_group": "30-49",
            "provider_id": "PRV-101",
            "diagnosis_code": "E11.9",
            "diagnosis_desc": "Type 2 diabetes",
            "treatment_cost": 300.0,
            "encounter_timestamp": "2026-05-10T12:00:00Z",
            "run_id": "RUN_1",
            "published_at": "2026-11-05T12:00:00Z"
        },
        {
            "encounter_id": "ENC-1002",
            "patient_token": "TOK_PAT_BBBB",
            "masked_name": "P*** R****",
            "masked_email": "pr***@gmail.com",
            "gender": "Female",
            "age_group": "18-29",
            "provider_id": "PRV-102",
            "diagnosis_code": "I10",
            "diagnosis_desc": "Hypertension",
            "treatment_cost": 250.0,
            "encounter_timestamp": "2026-05-11T12:00:00Z",
            "run_id": "RUN_1",
            "published_at": "2026-11-05T12:00:00Z"
        }
    ])

    # First run
    inserted_1 = audit.publish_analytical_encounters_idempotent(test_data)
    assert inserted_1 == 2
    assert audit.get_total_analytical_count() == 2

    # Second run with exact same encounter_ids, simulating rerun or retry with updated run_id
    rerun_data = test_data.copy()
    rerun_data["run_id"] = "RUN_2_RETRY"

    inserted_2 = audit.publish_analytical_encounters_idempotent(rerun_data)
    assert inserted_2 == 2

    # Crucial assertion: Total count in analytical store remains 2, not 4!
    assert audit.get_total_analytical_count() == 2

    # Verify that the record was updated with the latest run_id
    with audit.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT run_id FROM analytical_encounters WHERE encounter_id = 'ENC-1001'")
        latest_run = cursor.fetchone()[0]
        assert latest_run == "RUN_2_RETRY"
