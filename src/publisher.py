"""Target Publishing and Reconciliation Engine.

Publishes:
- Minimized analytical dataset to SQLite, Parquet, and CSV
- Quarantined records to explicit audit storage
- Validation and Reconciliation reports with zero-discrepancy mathematical proofs
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from src.audit import AuditStore


logger = logging.getLogger(__name__)


class Publisher:
    """Publishes analytical data, persists quarantines, and generates reconciliation reports."""

    def __init__(
        self,
        audit_store: AuditStore,
        output_dir: str | Path = "data/output",
        quarantine_dir: str | Path = "data/quarantine",
        reports_dir: str | Path = "reports",
        target_format: str = "both",
    ):
        self.audit_store = audit_store
        self.output_dir = Path(output_dir)
        self.quarantine_dir = Path(quarantine_dir)
        self.reports_dir = Path(reports_dir)
        self.target_format = target_format.lower()

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def publish_analytical_dataset(
        self,
        df: pd.DataFrame,
        run_id: str
    ) -> Dict[str, str]:
        """Publish minimized analytical dataset to SQLite, CSV, and Parquet.

        Returns:
            Dictionary of published file paths.
        """
        published_artifacts = {}

        # 1. Publish to SQLite with Idempotent UPSERT
        self.audit_store.publish_analytical_encounters_idempotent(df)

        if df.empty:
            return published_artifacts

        # 2. Publish to CSV (both latest canonical and run-specific)
        if self.target_format in ["csv", "both"]:
            run_csv_path = self.output_dir / f"analytical_encounters_{run_id}.csv"
            canonical_csv_path = self.output_dir / "analytical_encounters.csv"
            df.to_csv(run_csv_path, index=False)
            df.to_csv(canonical_csv_path, index=False)
            published_artifacts["csv_run"] = str(run_csv_path)
            published_artifacts["csv_canonical"] = str(canonical_csv_path)

        # 3. Publish to Parquet (both latest canonical and run-specific)
        if self.target_format in ["parquet", "both"]:
            run_parquet_path = self.output_dir / f"analytical_encounters_{run_id}.parquet"
            canonical_parquet_path = self.output_dir / "analytical_encounters.parquet"
            df.to_parquet(run_parquet_path, index=False, engine="pyarrow")
            df.to_parquet(canonical_parquet_path, index=False, engine="pyarrow")
            published_artifacts["parquet_run"] = str(run_parquet_path)
            published_artifacts["parquet_canonical"] = str(canonical_parquet_path)

        return published_artifacts

    def publish_quarantine(
        self,
        quarantined_df: pd.DataFrame,
        run_id: str
    ) -> Optional[str]:
        """Persist quarantined records to SQLite and export CSV file."""
        if quarantined_df.empty:
            return None

        # 1. SQLite persistence
        self.audit_store.log_quarantine_records(quarantined_df)

        # 2. Export run-specific quarantine CSV
        quarantine_file = self.quarantine_dir / f"quarantined_records_{run_id}.csv"
        quarantined_df.to_csv(quarantine_file, index=False)
        return str(quarantine_file)

    def generate_reconciliation_report(
        self,
        run_id: str,
        raw_df: pd.DataFrame,
        valid_df: pd.DataFrame,
        quarantined_df: pd.DataFrame,
        published_df: pd.DataFrame,
        profiling_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Perform end-to-end mathematical count reconciliation and key aggregate checks."""
        input_count = len(raw_df)
        valid_count = len(valid_df)
        quarantined_count = len(quarantined_df)
        published_count = len(published_df)

        # Mathematical integrity check: input == valid + quarantined
        is_balanced = (input_count == valid_count + quarantined_count) and (valid_count == published_count)

        # Key Aggregates Reconciliation: treatment cost sum
        raw_valid_cost_sum = round(float(valid_df["treatment_cost"].sum()), 2) if not valid_df.empty and "treatment_cost" in valid_df.columns else 0.0
        published_cost_sum = round(float(published_df["treatment_cost"].sum()), 2) if not published_df.empty and "treatment_cost" in published_df.columns else 0.0
        cost_diff = round(abs(raw_valid_cost_sum - published_cost_sum), 4)
        cost_reconciled = (cost_diff == 0.0)

        # Categorical Breakdown Reconciliation
        diag_counts = (
            published_df["diagnosis_code"].value_counts().to_dict()
            if not published_df.empty and "diagnosis_code" in published_df.columns
            else {}
        )

        quarantine_breakdown = (
            quarantined_df["rejection_code"].value_counts().to_dict()
            if not quarantined_df.empty and "rejection_code" in quarantined_df.columns
            else {}
        )

        reconciliation = {
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "reconciliation_status": "BALANCED" if (is_balanced and cost_reconciled) else "DISCREPANCY_DETECTED",
            "counts": {
                "input_records": input_count,
                "valid_records": valid_count,
                "quarantined_records": quarantined_count,
                "published_records": published_count,
                "formula_check": f"{input_count} == {valid_count} (valid) + {quarantined_count} (quarantined)",
                "is_count_balanced": is_balanced,
            },
            "financial_aggregate_reconciliation": {
                "source_valid_cost_sum": raw_valid_cost_sum,
                "published_cost_sum": published_cost_sum,
                "difference": cost_diff,
                "is_cost_balanced": cost_reconciled,
            },
            "quarantine_summary": {
                "total_quarantined": quarantined_count,
                "breakdown_by_reason": quarantine_breakdown,
            },
            "published_distribution_summary": {
                "diagnosis_frequencies": diag_counts,
            },
        }

        # Save to reports directory
        recon_path = self.reports_dir / "reconciliation_report.json"
        with open(recon_path, "w", encoding="utf-8") as f:
            json.dump(reconciliation, f, indent=2)

        validation_report = {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "SUCCESS" if (is_balanced and cost_reconciled) else "WARNING",
            "profiling_summary": profiling_metrics.get("dataset_metrics", {}),
            "reconciliation": reconciliation["counts"],
            "quarantine_reasons": quarantine_breakdown,
        }

        val_path = self.reports_dir / "validation_report.json"
        with open(val_path, "w", encoding="utf-8") as f:
            json.dump(validation_report, f, indent=2)

        return reconciliation
