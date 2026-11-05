# Quarantine Records Directory

This directory stores defective or anomalous records intercepted by the validation quality gate.

## Sample Files Included in Repository
- `sample_quarantined_records.csv`: Starter sample of quarantined anomaly records (40 rows) from the sample run.

## Quarantine Record Structure & Traceability
Each quarantined record contains full lineage back to the raw source data:
- `run_id`: Execution identifier during which the defect was intercepted.
- `source_row_index`: Zero-based row index in the raw input file.
- `encounter_id`: Extracted primary key (or null if missing).
- `rejection_code`: Machine-readable error classification:
  - `MISSING_REQUIRED_FIELD`: Null or blank mandatory fields (`patient_id`, `full_name`).
  - `DUPLICATE_PRIMARY_KEY`: Duplicate `encounter_id` within the batch.
  - `INVALID_DOMAIN_VALUE`: Out-of-bounds metrics (e.g. negative `treatment_cost`).
  - `REFERENTIAL_INTEGRITY_VIOLATION`: Foreign key not found in provider registry.
  - `MALFORMED_EMAIL`: RFC format violation.
  - `MALFORMED_TIMESTAMP`: Invalid ISO-8601 timestamp string.
- `rejection_reason`: Human-readable explanation of why the record was rejected.
- `raw_record_json`: Complete snapshot of the original input row for debugging and replay.
- `quarantined_at`: Timestamp when the record was quarantined.
