# Published Analytical Dataset Directory

This directory stores the clean, privacy-preserved, and minimized analytical outputs produced by the pipeline.

## Sample Files Included in Repository
- `sample_analytical_encounters.csv`: Starter sample of published analytical records (475 rows).
- `sample_analytical_encounters.parquet`: High-performance columnar Parquet version.

## Schema & Privacy Protections
- `encounter_id`: Preserved primary key.
- `patient_token`: Deterministic cryptographic HMAC-SHA256 surrogate token (`TOK_PAT_xxxxxx`).
- `masked_name`: Name initial masking (`R*** K****`).
- `masked_email`: Domain-preserving email mask (`ra***@domain.com`).
- `gender`: Retained demographic dimension.
- `age_group`: Generalized birth date cohorts (`<18`, `18-29`, `30-49`, `50-64`, `65+`).
- `provider_id`: Validated healthcare provider reference key.
- `diagnosis_code`: Clinical ICD-10 diagnosis code.
- `diagnosis_desc`: Clinical diagnosis description.
- `treatment_cost`: Verified non-negative financial metric.
- `encounter_timestamp`: Standard ISO-8601 visit timestamp.
- `run_id`: Pipeline execution lineage ID.
- `published_at`: Publication ISO-8601 timestamp.

> All raw sensitive identifiers (`patient_id`, `full_name`, `email`, `phone_number`, `national_id`, `birth_date`) are completely purged under the **Data Minimization Principle**.
