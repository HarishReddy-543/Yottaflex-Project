# Pipeline Audit & Metadata Directory

This directory stores operational metrics, run logs, and execution histories.

## Local Metadata Store
When the pipeline executes locally, it creates and updates an ACID-compliant SQLite database:
- `pipeline_metadata.sqlite`

## Managed Tables
1. `pipeline_runs`: Execution start/end timestamps, duration, status (`SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`), input row counts, valid counts, quarantined counts, and published counts.
2. `quarantined_records`: Complete relational index of all quarantined records across all historical runs.
3. `data_quality_metrics`: Granular quality counters and rejection reason distributions.
4. `analytical_encounters`: Published analytical table with unique primary key constraints enabling **idempotent UPSERT** (`INSERT OR REPLACE`).

> Note: `*.sqlite` and `*.db` binary database files are excluded from git to avoid committing local binary state. The database is initialized and managed automatically upon the first execution.
