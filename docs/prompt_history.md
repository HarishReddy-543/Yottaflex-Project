# AI Prompt History and Transparency Report

In compliance with the **YottaFlex AI Candidate Project Submission Guidelines** (Section 03: *Use LLMs Transparently* and FAQ Question 6), this document details all AI prompts used during development, how AI was leveraged, and what was personally reviewed, changed, and validated by the candidate.

---

## 1. Summary of AI Tools and Candidate Ownership

### AI Tools Utilized
1. **Google Antigravity** (IDE & Agent Framework) — **AI Model**: Gemini 3.8 Flash
2. **ChatGPT** (OpenAI) — Architecture review, planning, and design guidance

### Candidate Review & Engineering Validation Matrix

| Activity Area | AI Acceleration | Candidate Review & Engineering Validation |
| :--- | :--- | :--- |
| **Domain Architecture** | Prompted AI for realistic healthcare schema design, ICD-10 diagnosis codes, and privacy rules. | Formulated exact entities, primary/foreign keys (`encounter_id`, `patient_id`, `provider_id`), referential integrity logic, and field nullability rules. |
| **Pipeline Scaffolding** | Generated boilerplate modules for profiling, validation, and privacy transformation. | Personally reviewed and verified cryptographic HMAC tokenization, regex patterns, and data minimization gates. |
| **Edge Cases & Testing** | Suggested comprehensive test fixtures covering happy path, nulls, duplicates, and edge cases. | Handled Python 3.13 deprecation warnings (`datetime.utcnow()`), added custom assertions, and verified all 25 tests pass. |
| **Performance Benchmarking** | Drafted CLI benchmark harness for 100k records. | Verified WAL mode performance, memory footprint, throughput metrics (~4,300–8,850 records/sec), and wrote optimization analysis. |

---

## 2. Complete Prompt Log

### Prompt 1: Initial Requirements Analysis and Architectural Planning
- **Tool**: Google Antigravity
- **AI Model**: Gemini 3.8 Flash
- **Prompt**:
  > "Analyze the YottaFlex AI Associate AI Data Forward Deployed Engineer 72-Hour Code Challenge problem statement:
  > Problem: Profile synthetic datasets for sensitive fields, apply configurable masking or tokenization, and publish a minimized analytical dataset with a documented audit trail.
  > Suggest a clean, modular Python-based architecture incorporating data profiling, strict validation with quarantine routing, deterministic HMAC tokenization, data minimization, SQLite audit logs, automated tests, and reproducible sample generators."
- **Outcome**: Formulated the 5-layer pipeline architecture (Ingestion -> Profiler -> Validator -> Privacy Transformer -> Publisher & Audit Store).

---

### Prompt 2: Synthetic Generator & Edge Case Injection
- **Tool**: Google Antigravity
- **AI Model**: Gemini 3.8 Flash
- **Prompt**:
  > "Design a synthetic healthcare dataset generator using NumPy and Pandas that can generate reproducible datasets (seeded) for small starter batches (500 rows) and scalable volumes (100,000+ rows).
  > Include normal records and controlled injection of defects: null primary keys (encounter_id), duplicate encounter_ids, missing mandatory fields (patient_id, full_name), invalid foreign keys (unregistered provider_id), negative treatment costs, and malformed emails/timestamps."
- **Outcome**: Implemented `src/generator.py` with reproducible seed support, reference providers generation, and configurable defect ratios.

---

### Prompt 3: Data Profiling and Sensitive Field Detection
- **Tool**: Google Antigravity
- **AI Model**: Gemini 3.8 Flash
- **Prompt**:
  > "Create a data profiler module that inspects columns for data types, null counts, null percentages, distinct values, and duplicate rows.
  > Automatically classify columns as DIRECT_IDENTIFIER, SURROGATE_IDENTIFIER, QUASI_IDENTIFIER, or SENSITIVE_CLINICAL using regex patterns and semantic keyword matching. Recommend privacy treatments (MASK, TOKENIZE, GENERALIZE, DROP, KEEP)."
- **Outcome**: Implemented `src/profiler.py` and structured JSON profiling reports.

---

### Prompt 4: Validation Engine and Explicit Quarantine Path
- **Tool**: Google Antigravity
- **AI Model**: Gemini 3.8 Flash
- **Prompt**:
  > "Write a DatasetValidator class that checks schema conformance, primary key uniqueness (encounter_id), referential integrity against provider IDs (provider_id), domain boundaries (treatment_cost >= 0), and RFC email formats.
  > Route failing records to an explicit quarantine dataframe with columns: run_id, source_row_index, encounter_id, rejection_code, rejection_reason, raw_record_json, and quarantined_at."
- **Outcome**: Implemented `src/validator.py` with full source record traceability.

---

### Prompt 5: Privacy Engine and Data Minimization Gate
- **Tool**: Google Antigravity
- **AI Model**: Gemini 3.8 Flash
- **Prompt**:
  > "Implement privacy transformations:
  > 1. Deterministic HMAC-SHA256 tokenization using secret salt for patient_id -> patient_token.
  > 2. Name masking (R*** K****), email masking (ra***@domain.com), phone masking (***-***-1234).
  > 3. Age cohort generalization from birth dates (<18, 18-29, 30-49, 50-64, 65+).
  > 4. Data minimization gate that strictly purges raw sensitive fields and verifies dropped fields do not appear in the published analytical dataset."
- **Outcome**: Implemented `src/privacy.py` and `src/transformer.py`.

---

### Prompt 6: Audit Store and Idempotent Upsert
- **Tool**: Google Antigravity
- **AI Model**: Gemini 3.8 Flash
- **Prompt**:
  > "Implement a SQLite audit store managing pipeline_runs, quarantined_records, data_quality_metrics, and analytical_encounters.
  > Use SQLite WAL mode and an idempotent UPSERT strategy (INSERT OR REPLACE) so rerunning the same batch does not create duplicate rows in the analytical table."
- **Outcome**: Implemented `src/audit.py` and `src/publisher.py`.

---

### Prompt 7: Automated Test Suite (Pytest)
- **Tool**: Google Antigravity
- **AI Model**: Gemini 3.8 Flash
- **Prompt**:
  > "Write a comprehensive Pytest test suite covering: happy path, empty input, null primary keys, missing required fields, duplicates, negative cost edge case, referential integrity violations, deterministic tokenization, privacy leakage assertions (asserting forbidden raw fields never leak into output), and mathematical count reconciliation."
- **Outcome**: Created 25 test cases across 7 test files (`tests/test_*.py`).

---

### Prompt 8: Python 3.13 Deprecation Fixes and Code Quality
- **Tool**: Google Antigravity
- **AI Model**: Gemini 3.8 Flash
- **Prompt**:
  > "In Python 3.13, datetime.utcnow() is deprecated. Refactor all occurrences across src/ and tests/ to datetime.now(timezone.utc) to ensure clean execution with zero warnings."
- **Outcome**: Refactored timestamp generation across all modules.

---

### Prompt 9: Project Architecture Review and Implementation Guidance
- **Tool**: ChatGPT (OpenAI)
- **AI Model**: GPT-4o
- **Prompt (Reconstructed Summary)**:
  > "Help me develop a Privacy-Aware Data Engineering Pipeline for the YottaFlex AI 72-hour coding challenge. Explain the project architecture, recommend a Python-based technology stack, design the folder structure, and implement the synthetic data generator with reproducible sample data and automated tests. Explain each implementation step clearly."
- **Outcome**: Received architectural guidance, project organization recommendations, Python implementation assistance, synthetic dataset generation guidance, and testing recommendations.
- **Candidate Review**: Reviewed the suggested architecture and implementation, verified that the healthcare encounter schema (`encounter_id`, `patient_id`, `provider_id`, `diagnosis_code`, `treatment_cost`) met all problem statement requirements, and aligned all modules, tests, and documentation to this unified schema.

---

## 3. Schema and Implementation Consistency Verification

All artifacts across this repository use a single, unified domain schema:
- **Primary Source Entity**: `patients_encounters` (`encounter_id`, `patient_id`, `full_name`, `email`, `phone_number`, `national_id`, `birth_date`, `gender`, `provider_id`, `diagnosis_code`, `diagnosis_desc`, `treatment_cost`, `encounter_timestamp`)
- **Reference Entity**: `reference_providers` (`provider_id`, `provider_name`, `department`, `facility_code`)
- **Published Minimized Entity**: `analytical_encounters` (`encounter_id`, `patient_token`, `masked_name`, `masked_email`, `gender`, `age_group`, `provider_id`, `diagnosis_code`, `diagnosis_desc`, `treatment_cost`, `encounter_timestamp`, `run_id`, `published_at`)
- **Audit Stores**: `pipeline_runs`, `quarantined_records`, `data_quality_metrics`

This guarantees complete alignment across `docs/data_dictionary.md`, `src/`, `config/`, `tests/`, and this prompt report.

---

## 4. Candidate Validation Statement
I confirm that:
1. I have personally directed, reviewed, and validated every component of this repository.
2. The logic, architecture, trade-offs, and test assertions are thoroughly understood and verified.
3. All code runs locally without external credentials and produces verified outputs.
4. Both AI tools utilized (Google Antigravity with Gemini 3.8 Flash, and ChatGPT with GPT-4o) have been transparently disclosed with their respective roles.
5. I am prepared to walk through any line of code, explain the design choices, and discuss scalability considerations during the technical interview.
