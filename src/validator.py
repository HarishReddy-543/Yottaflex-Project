"""Schema and Business Rule Validator.

Validates datasets against:
- Schema presence and expected columns
- Primary key constraints (nullability and uniqueness)
- Mandatory business fields
- Referential integrity (foreign key validation against reference sets)
- Format validity (email, ISO timestamps)
- Domain boundaries (treatment_cost >= 0)
- Explicit quarantine routing with traceable error codes and source snapshots
"""

from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

EXPECTED_SCHEMA_COLUMNS = [
    "encounter_id",
    "patient_id",
    "full_name",
    "email",
    "phone_number",
    "national_id",
    "birth_date",
    "gender",
    "provider_id",
    "diagnosis_code",
    "diagnosis_desc",
    "treatment_cost",
    "encounter_timestamp",
]


class ValidationResult:
    """Encapsulates validation outcome."""

    def __init__(self, valid_df: pd.DataFrame, quarantined_df: pd.DataFrame, metrics: Dict[str, Any]):
        self.valid_df = valid_df
        self.quarantined_df = quarantined_df
        self.metrics = metrics


class DatasetValidator:
    """Validates raw datasets, separating clean records from quarantined anomalies."""

    def __init__(
        self,
        valid_providers: Optional[Set[str] | List[str]] = None,
        required_columns: Optional[List[str]] = None,
    ):
        self.valid_providers = set(valid_providers) if valid_providers else set()
        self.required_columns = required_columns or EXPECTED_SCHEMA_COLUMNS

    def validate(
        self,
        df: pd.DataFrame,
        run_id: str = "RUN-UNKNOWN"
    ) -> ValidationResult:
        """Validate DataFrame against structural and business constraints.

        Args:
            df: Raw input DataFrame.
            run_id: Active pipeline execution identifier for tracking.

        Returns:
            ValidationResult containing valid_df, quarantined_df, and audit metrics.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        if df.empty:
            empty_quarantine = pd.DataFrame(columns=[
                "run_id", "source_row_index", "encounter_id",
                "rejection_code", "rejection_reason", "raw_record_json", "quarantined_at"
            ])
            return ValidationResult(
                valid_df=df.copy(),
                quarantined_df=empty_quarantine,
                metrics={
                    "total_input_records": 0,
                    "valid_records": 0,
                    "quarantined_records": 0,
                    "rejections_by_code": {},
                }
            )

        # Check Schema Conformance
        missing_columns = set(self.required_columns) - set(df.columns)
        if missing_columns:
            raise ValueError(f"Schema Conformance Error: Missing required columns: {sorted(list(missing_columns))}")

        quarantine_records: List[Dict[str, Any]] = []
        valid_mask = np.ones(len(df), dtype=bool)

        # Track seen primary keys for deduplication
        seen_primary_keys: Set[str] = set()

        for idx, row in df.iterrows():
            row_dict = row.to_dict()
            encounter_id = row_dict.get("encounter_id")
            patient_id = row_dict.get("patient_id")
            full_name = row_dict.get("full_name")
            email = row_dict.get("email")
            provider_id = row_dict.get("provider_id")
            treatment_cost = row_dict.get("treatment_cost")
            encounter_timestamp = row_dict.get("encounter_timestamp")

            rejection_code = None
            rejection_reason = None

            # 1. Primary Key Nullness
            if pd.isna(encounter_id) or str(encounter_id).strip() == "":
                rejection_code = "NULL_PRIMARY_KEY"
                rejection_reason = "Encounter ID is missing or empty."

            # 2. Duplicate Primary Key
            elif encounter_id in seen_primary_keys:
                rejection_code = "DUPLICATE_PRIMARY_KEY"
                rejection_reason = f"Duplicate encounter_id '{encounter_id}' detected in batch."

            # 3. Required Fields Check
            elif pd.isna(patient_id) or str(patient_id).strip() == "":
                rejection_code = "MISSING_REQUIRED_FIELD"
                rejection_reason = "Mandatory field 'patient_id' is null or blank."

            elif pd.isna(full_name) or str(full_name).strip() == "":
                rejection_code = "MISSING_REQUIRED_FIELD"
                rejection_reason = "Mandatory field 'full_name' is null or blank."

            # 4. Email Format Check
            elif pd.notna(email) and not EMAIL_REGEX.match(str(email).strip()):
                rejection_code = "MALFORMED_EMAIL"
                rejection_reason = f"Email '{email}' does not adhere to standard RFC email format."

            # 5. Referential Integrity Check
            elif self.valid_providers and (pd.isna(provider_id) or str(provider_id) not in self.valid_providers):
                rejection_code = "REFERENTIAL_INTEGRITY_VIOLATION"
                rejection_reason = f"Provider ID '{provider_id}' does not exist in reference providers registry."

            # 6. Domain Boundary: treatment_cost
            else:
                try:
                    cost_val = float(treatment_cost)
                    if pd.isna(cost_val) or cost_val < 0:
                        rejection_code = "INVALID_DOMAIN_VALUE"
                        rejection_reason = f"Treatment cost '{treatment_cost}' cannot be negative or null."
                except (ValueError, TypeError):
                    rejection_code = "MALFORMED_DATA_TYPE"
                    rejection_reason = f"Treatment cost '{treatment_cost}' is not a valid numeric value."

            # 7. ISO Timestamp Format Check
            if rejection_code is None and pd.notna(encounter_timestamp):
                ts_str = str(encounter_timestamp).replace("Z", "+00:00")
                try:
                    datetime.fromisoformat(ts_str)
                except Exception:
                    rejection_code = "MALFORMED_TIMESTAMP"
                    rejection_reason = f"Encounter timestamp '{encounter_timestamp}' is not valid ISO-8601."

            if rejection_code is not None:
                valid_mask[idx] = False
                # Format raw record JSON safely
                raw_json = json.dumps(
                    {k: (None if pd.isna(v) else v) for k, v in row_dict.items()},
                    default=str
                )
                quarantine_records.append({
                    "run_id": run_id,
                    "source_row_index": int(idx),
                    "encounter_id": str(encounter_id) if pd.notna(encounter_id) else None,
                    "rejection_code": rejection_code,
                    "rejection_reason": rejection_reason,
                    "raw_record_json": raw_json,
                    "quarantined_at": now_iso,
                })
            else:
                seen_primary_keys.add(encounter_id)

        valid_df = df[valid_mask].copy().reset_index(drop=True)

        if quarantine_records:
            quarantined_df = pd.DataFrame(quarantine_records)
        else:
            quarantined_df = pd.DataFrame(columns=[
                "run_id", "source_row_index", "encounter_id",
                "rejection_code", "rejection_reason", "raw_record_json", "quarantined_at"
            ])

        rejection_counts = (
            quarantined_df["rejection_code"].value_counts().to_dict()
            if not quarantined_df.empty
            else {}
        )

        metrics = {
            "total_input_records": len(df),
            "valid_records": len(valid_df),
            "quarantined_records": len(quarantined_df),
            "rejections_by_code": rejection_counts,
        }

        return ValidationResult(
            valid_df=valid_df,
            quarantined_df=quarantined_df,
            metrics=metrics
        )
