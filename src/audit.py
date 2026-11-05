"""Audit Trail and Metadata Store Module.

Manages SQLite metadata storage:
- pipeline_runs: execution status, durations, row counts, and failures
- quarantined_records: traceable source captures with error diagnostics
- data_quality_metrics: granular quality check tallies
- analytical_encounters: target analytical store with idempotent upsert capability
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
import pandas as pd


logger = logging.getLogger(__name__)


class AuditStore:
    """Manages SQLite storage for pipeline operational audit, quality metrics, and target encounters."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def get_connection(self) -> sqlite3.Connection:
        """Create a connection with foreign key support enabled."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")  # High-performance write-ahead logging
        return conn

    def _init_tables(self) -> None:
        """Initialize database schema if not present."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Pipeline Runs Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    run_id TEXT PRIMARY KEY,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    status TEXT NOT NULL,
                    input_count INTEGER DEFAULT 0,
                    valid_count INTEGER DEFAULT 0,
                    quarantined_count INTEGER DEFAULT 0,
                    published_count INTEGER DEFAULT 0,
                    execution_seconds REAL DEFAULT 0.0,
                    failure_reason TEXT,
                    created_at TEXT NOT NULL
                );
            """)

            # 2. Quarantined Records Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quarantined_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    source_row_index INTEGER,
                    encounter_id TEXT,
                    rejection_code TEXT NOT NULL,
                    rejection_reason TEXT NOT NULL,
                    raw_record_json TEXT NOT NULL,
                    quarantined_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id) ON DELETE CASCADE
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quarantine_run ON quarantined_records(run_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quarantine_code ON quarantined_records(rejection_code);")

            # 3. Data Quality Metrics Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_quality_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    metric_type TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id) ON DELETE CASCADE
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_run ON data_quality_metrics(run_id);")

            # 4. Target Analytical Encounters Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analytical_encounters (
                    encounter_id TEXT PRIMARY KEY,
                    patient_token TEXT NOT NULL,
                    masked_name TEXT,
                    masked_email TEXT,
                    gender TEXT,
                    age_group TEXT,
                    provider_id TEXT NOT NULL,
                    diagnosis_code TEXT,
                    diagnosis_desc TEXT,
                    treatment_cost REAL,
                    encounter_timestamp TEXT,
                    run_id TEXT NOT NULL,
                    published_at TEXT NOT NULL
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytical_token ON analytical_encounters(patient_token);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytical_diag ON analytical_encounters(diagnosis_code);")
            conn.commit()

    def record_run_start(self, run_id: str, input_count: int = 0) -> None:
        """Record beginning of a pipeline execution."""
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO pipeline_runs (
                    run_id, start_time, status, input_count, created_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (run_id, now, "RUNNING", input_count, now))
            conn.commit()

    def record_run_completion(
        self,
        run_id: str,
        status: str,
        valid_count: int,
        quarantined_count: int,
        published_count: int,
        execution_seconds: float,
        failure_reason: Optional[str] = None,
    ) -> None:
        """Record conclusion of pipeline execution."""
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE pipeline_runs
                SET end_time = ?,
                    status = ?,
                    valid_count = ?,
                    quarantined_count = ?,
                    published_count = ?,
                    execution_seconds = ?,
                    failure_reason = ?
                WHERE run_id = ?
            """, (
                now, status, valid_count, quarantined_count,
                published_count, execution_seconds, failure_reason, run_id
            ))
            conn.commit()

    def log_quarantine_records(self, quarantined_df: pd.DataFrame) -> None:
        """Persist quarantined records into SQLite store."""
        if quarantined_df.empty:
            return

        with self.get_connection() as conn:
            records = quarantined_df.to_dict(orient="records")
            conn.executemany("""
                INSERT INTO quarantined_records (
                    run_id, source_row_index, encounter_id,
                    rejection_code, rejection_reason, raw_record_json, quarantined_at
                ) VALUES (
                    :run_id, :source_row_index, :encounter_id,
                    :rejection_code, :rejection_reason, :raw_record_json, :quarantined_at
                )
            """, records)
            conn.commit()

    def log_metrics(self, run_id: str, metrics: Dict[str, Any]) -> None:
        """Persist data quality metrics."""
        now = datetime.now(timezone.utc).isoformat()
        rows = []
        for name, val in metrics.items():
            if isinstance(val, (int, float)):
                rows.append((run_id, name, float(val), "COUNTER", now))
            elif isinstance(val, dict):
                for sub_k, sub_v in val.items():
                    if isinstance(sub_v, (int, float)):
                        rows.append((run_id, f"{name}.{sub_k}", float(sub_v), "BREAKDOWN", now))

        if rows:
            with self.get_connection() as conn:
                conn.executemany("""
                    INSERT INTO data_quality_metrics (
                        run_id, metric_name, metric_value, metric_type, recorded_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, rows)
                conn.commit()

    def publish_analytical_encounters_idempotent(self, df: pd.DataFrame) -> int:
        """Publish analytical records using an idempotent UPSERT strategy.

        If encounter_id already exists from a previous or partial run,
        it replaces the existing row, guaranteeing idempotency.
        """
        if df.empty:
            return 0

        # Required columns in analytical table
        expected_cols = [
            "encounter_id", "patient_token", "masked_name", "masked_email",
            "gender", "age_group", "provider_id", "diagnosis_code",
            "diagnosis_desc", "treatment_cost", "encounter_timestamp",
            "run_id", "published_at"
        ]

        # Ensure all columns exist
        df_to_insert = df.copy()
        for col in expected_cols:
            if col not in df_to_insert.columns:
                df_to_insert[col] = None

        df_to_insert = df_to_insert[expected_cols]

        records = df_to_insert.to_dict(orient="records")

        with self.get_connection() as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO analytical_encounters (
                    encounter_id, patient_token, masked_name, masked_email,
                    gender, age_group, provider_id, diagnosis_code,
                    diagnosis_desc, treatment_cost, encounter_timestamp,
                    run_id, published_at
                ) VALUES (
                    :encounter_id, :patient_token, :masked_name, :masked_email,
                    :gender, :age_group, :provider_id, :diagnosis_code,
                    :diagnosis_desc, :treatment_cost, :encounter_timestamp,
                    :run_id, :published_at
                )
            """, records)
            conn.commit()

        return len(records)

    def get_run_summary(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve operational summary for a specific run."""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pipeline_runs WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_runs(self) -> List[Dict[str, Any]]:
        """Retrieve all pipeline executions."""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pipeline_runs ORDER BY start_time DESC")
            return [dict(r) for r in cursor.fetchall()]

    def get_quarantine_stats(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve aggregated quarantine statistics."""
        query = """
            SELECT rejection_code, COUNT(*) as count, MIN(rejection_reason) as sample_reason
            FROM quarantined_records
        """
        params = []
        if run_id:
            query += " WHERE run_id = ?"
            params.append(run_id)
        query += " GROUP BY rejection_code ORDER BY count DESC"

        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def get_total_analytical_count(self) -> int:
        """Count distinct records in the published analytical table."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM analytical_encounters")
            return cursor.fetchone()[0]
