# Design Decisions and Trade-offs Note

This document explains the key engineering decisions, assumptions, architectural trade-offs, and future scalability considerations for the Privacy-Aware Data Engineering Pipeline.

---

## 1. Technology Selection: Python + Pandas + SQLite

### Context & Decision
The challenge requires a runnable, fully demonstrable data engineering pipeline runnable locally with zero external credentials, capable of processing starter datasets and scalable 100,000+ record batches.

### Options Considered
1. **PySpark / Apache Spark**: Excellent for multi-terabyte distributed clusters; however, introduces heavy Java/Hadoop environment dependencies, executor overhead, and brittle local execution setups for evaluators.
2. **DuckDB / Polars**: Extremely fast columnar analytical engines.
3. **Python + Pandas + SQLite**: Standard, universally portable, zero-configuration local stack that is fully ACID-compliant, transparent, and debuggable.

### Trade-off
- **Benefit**: Zero installation friction for recruiters/evaluators. Benchmarking proves the pipeline processes **102,000 records in 11.5 seconds (~8,851 records/sec)**, well exceeding requirements without heavyweight infrastructure.
- **Limitation**: In-memory Pandas limits single-node processing to datasets that fit in available RAM (~5-10 million records).

---

## 2. Privacy Architecture: Deterministic Tokenization vs. Reversible Encryption

### Context & Decision
Healthcare analytical pipelines need to enable longitudinal patient tracking (linking multiple visits for the same patient across time) without exposing actual Patient IDs or National IDs.

### Options Considered
1. **Reversible Symmetric Encryption (e.g. AES-256-GCM)**: Allows decryption back to cleartext, but introduces complex secret key distribution risks. If analytical consumers obtain read access to the encrypted data, a leaked AES key compromises the entire patient directory.
2. **Non-Deterministic Tokenization (Random UUIDs)**: Completely hides patient identity, but loses longitudinal joinability (the same patient on day 2 receives a different UUID).
3. **Deterministic Cryptographic HMAC-SHA256 with Secret Salt**: Computes a keyed cryptographic hash `HMAC_SHA256(patient_id, salt) -> TOK_PAT_xxxxxx`.

### Trade-off
- **Benefit**: Perfectly preserves joinability across datasets and time horizons; irreversible without brute-force; protects against rainbow table attacks via salt rotation; eliminates key management overhead for downstream analytical teams.
- **Limitation**: If salt is compromised and the search space of patient IDs is small, a dictionary attack could infer identity. Mitigation: use strong salts (`hmac_secret_salt` injected via environment variable `PIPELINE_HMAC_SALT`).

---

## 3. Data Quality Strategy: Strict Quarantine Routing vs. Batch Abort

### Context & Decision
When defective records (missing fields, duplicate keys, negative treatment costs, invalid provider references) appear in an incoming batch:

### Options Considered
1. **Fail-Fast (Abort Pipeline)**: Stops pipeline execution immediately upon the first bad row.
   - *Problem*: In real-world enterprise healthcare feeds, a single defective row out of 100,000 would repeatedly block critical daily reporting.
2. **Silent Drop / Coercion**: Silently drops or sets bad values to defaults (`None`, `0`).
   - *Problem*: Loss of data integrity and zero auditability. Reconciliations fail silently.
3. **Explicit Quarantine Routing with Traceable Source Snapshots**: Segregates defective rows into a dedicated `quarantined_records` table with explicit machine-readable error codes (`rejection_code`), reasons, and raw JSON payloads.

### Trade-off
- **Benefit**: Ensures uninterrupted processing of valid analytical data while delivering 100% auditability and source traceability for engineering teams to diagnose and remediate errors.

---

## 4. Idempotency & Safe Reruns

### Context & Decision
Pipelines frequently experience intermittent network drops, operator retries, or rerun requests for the same source file. Rerunning a batch must not corrupt historical state or artificially duplicate rows.

### Implementation
- The target SQLite analytical store uses an **UPSERT strategy** on the primary key `encounter_id`:
  ```sql
  INSERT OR REPLACE INTO analytical_encounters (...) VALUES (...)
  ```
- Re-executing the same batch updates existing analytical records and logs a new distinct entry in `pipeline_runs` with the new `run_id`.
- Verified in automated test `tests/test_idempotency.py`: two consecutive runs of identical records leave the analytical table count constant while preserving execution audit history.

---

## 5. Performance Benchmarking & Identified Optimization

### Benchmark Results
- **Dataset Size**: 102,000 records
- **Pipeline Runtime**: 11.52 seconds
- **Throughput**: ~8,851 records/second
- **Reconciliation**: BALANCED (Zero discrepancy)

### Optimization Implemented
- SQLite Write-Ahead Logging (`PRAGMA journal_mode = WAL;`) and batch insertion (`executemany`) avoided thousands of single-row disk syncs.
- Vectorized array operations in generator and profiler eliminated slow iterative Python loops.

### Next Reasonable Optimization (Identified for 10M+ Scaling)
- **Arrow / DuckDB Chunked Streaming**: Instead of loading the entire raw file into a single Pandas DataFrame, stream chunks via PyArrow or DuckDB (`pd.read_csv(..., chunksize=50000)` or DuckDB out-of-core scans). This ensures steady RAM utilization regardless of file size.
