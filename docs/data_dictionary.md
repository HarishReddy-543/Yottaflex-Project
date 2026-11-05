# Data Dictionary: Healthcare Encounters Pipeline

This data dictionary outlines the schema specifications for the raw source ingestion layer, reference lookup entities, quarantined anomaly storage, and the published minimized analytical layer.

---

## 1. Raw Source Entity: `patients_encounters`

The ingestion entity capturing clinical encounters for patients.

| Column Name | Data Type | Nullable | Uniqueness | Sensitivity Class | Description & Business Rules |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `encounter_id` | String | No | Unique (PK) | Non-Sensitive Key | Deterministic primary key formatted as `ENC-XXXXXXX`. Mandatory; duplicate or null values are quarantined. |
| `patient_id` | String | No | Non-Unique (FK) | Surrogate Identifier | Hospital patient identity number (e.g., `PAT-01001`). Mandatory; links multiple visits for the same patient. |
| `full_name` | String | No | Non-Unique | Direct PII | Patient's legal first and last name. Must not be blank. |
| `email` | String | Yes | Non-Unique | Direct PII | Contact email address. Must conform to RFC email regex (`^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$`). |
| `phone_number` | String | Yes | Non-Unique | Direct PII | Patient's telephone number formatted with country/area codes. |
| `national_id` | String | Yes | Unique | Direct PII / Gov ID | Social security or national ID number (`XXX-XX-XXXX`). |
| `birth_date` | Date / String | Yes | Non-Unique | Quasi-Identifier | Patient's date of birth (`YYYY-MM-DD`). |
| `gender` | String | Yes | Non-Unique | Quasi-Identifier | Patient gender (`Male`, `Female`, `Other`). |
| `provider_id` | String | No | Non-Unique (FK) | Reference Key | Attending healthcare provider ID. Must exist in `reference_providers`. |
| `diagnosis_code` | String | No | Non-Unique | Sensitive Clinical | ICD-10 clinical diagnosis code (e.g., `E11.9`, `I10`, `J45.9`). |
| `diagnosis_desc` | String | No | Non-Unique | Clinical Attribute | Clinical diagnosis text description. |
| `treatment_cost` | Float | No | Non-Unique | Financial / Metric | Cost of treatment. Domain boundary rule: must be a non-negative float (`>= 0.0`). |
| `encounter_timestamp` | Timestamp | No | Non-Unique | Event Time | ISO-8601 UTC timestamp of clinical visit. |
| `ingestion_timestamp` | Timestamp | No | Non-Unique | Audit Attribute | ISO-8601 UTC timestamp of ingestion into pipeline. |

---

## 2. Reference Entity: `reference_providers`

Lookup table representing registered clinical healthcare facilities and providers.

| Column Name | Data Type | Nullable | Uniqueness | Description |
| :--- | :--- | :--- | :--- | :--- |
| `provider_id` | String | No | Unique (PK) | Provider unique identifier (e.g. `PRV-101`). |
| `provider_name` | String | No | Non-Unique | Name of facility or healthcare provider. |
| `department` | String | No | Non-Unique | Medical specialty department. |
| `facility_code` | String | No | Non-Unique | Physical clinic/facility code. |

---

## 3. Quarantine Entity: `quarantined_records`

Audit trail table storing defective or anomalous records with complete source lineage.

| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `id` | Integer (PK) | Auto-incrementing audit log identifier. |
| `run_id` | String (FK) | Unique execution identifier of pipeline run. |
| `source_row_index` | Integer | Zero-based index of record in raw input file. |
| `encounter_id` | String | Extracted encounter identifier, or null if missing. |
| `rejection_code` | String | Machine-readable rejection code (e.g., `DUPLICATE_PRIMARY_KEY`, `MISSING_REQUIRED_FIELD`, `INVALID_DOMAIN_VALUE`, `REFERENTIAL_INTEGRITY_VIOLATION`, `MALFORMED_EMAIL`, `MALFORMED_TIMESTAMP`). |
| `rejection_reason` | String | Human-readable explanation of why record failed quality gate. |
| `raw_record_json` | String (JSON) | Complete snapshot of original input row for debugging and replay. |
| `quarantined_at` | Timestamp | ISO-8601 timestamp when quarantine occurred. |

---

## 4. Published Analytical Entity: `analytical_encounters`

The minimized, privacy-preserved analytical data asset published to SQLite, CSV, and Parquet.

| Column Name | Data Type | Nullable | Sensitivity & Privacy Treatment | Purpose & Description |
| :--- | :--- | :--- | :--- | :--- |
| `encounter_id` | String (PK) | No | Preserved | Unique encounter identifier for analytical grain. |
| `patient_token` | String | No | Deterministic HMAC-SHA256 Token | Pseudonymized surrogate key (`TOK_PAT_xxxxxx`). Enables cohort joinability and longitudinal analysis without exposing real patient ID. |
| `masked_name` | String | Yes | Name Initial Mask (`R*** K****`) | Masked representation for reporting and audit verification. |
| `masked_email` | String | Yes | Email Mask (`ra***@domain.com`) | Preserves domain for categorization; masks individual user handle. |
| `gender` | String | Yes | Quasi-Identifier (Retained) | Demographic dimension. |
| `age_group` | String | Yes | Generalized Cohort | Generalization of `birth_date` into cohorts (`<18`, `18-29`, `30-49`, `50-64`, `65+`). Prevents re-identification. |
| `provider_id` | String (FK) | No | Validated Reference | Verified reference key to healthcare provider. |
| `diagnosis_code` | String | No | Analytical Feature | ICD-10 diagnosis code for epidemiology and clinical reporting. |
| `diagnosis_desc` | String | No | Analytical Feature | Human-readable diagnosis description. |
| `treatment_cost` | Float | No | Analytical Metric | Non-negative financial metric for healthcare economics. |
| `encounter_timestamp` | Timestamp | No | Event Time | ISO-8601 timestamp of visit. |
| `run_id` | String | No | Audit Lineage | Execution ID that published this analytical record. |
| `published_at` | Timestamp | No | Operational Lineage | ISO-8601 timestamp of publication. |

### Purged / Dropped Columns
Under the **Data Minimization Principle** (GDPR / HIPAA compliance), the following columns are purged from the analytical layer:
- Raw `patient_id`
- Raw `full_name`
- Raw `email`
- Raw `phone_number`
- Raw `national_id`
- Raw `birth_date`
