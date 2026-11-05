"""End-to-End Privacy-Aware Data Engineering Pipeline Orchestrator."""

from datetime import datetime, timezone
import logging
from pathlib import Path
import time
from typing import Any, Dict, Optional
import uuid
import pandas as pd

from src.audit import AuditStore
from src.config_loader import get_project_root, load_pipeline_config, load_privacy_rules
from src.generator import generate_reference_providers
from src.profiler import DatasetProfiler
from src.publisher import Publisher
from src.transformer import DatasetTransformer
from src.validator import DatasetValidator


# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("PipelineOrchestrator")


class PrivacyPipeline:
    """Orchestrates ingestion, profiling, validation, privacy transformation, and analytical publishing."""

    def __init__(
        self,
        config_path: str = "config/config.yaml",
        rules_path: str = "config/privacy_rules.yaml",
        custom_config: Optional[Dict[str, Any]] = None,
        custom_rules: Optional[Dict[str, Any]] = None,
    ):
        self.root = get_project_root()
        self.config = custom_config or load_pipeline_config(self.root / config_path)
        self.rules = custom_rules or load_privacy_rules(self.root / rules_path)

        storage_cfg = self.config.get("storage", {})
        db_path = self.root / storage_cfg.get("db_path", "data/audit/pipeline_metadata.sqlite")
        self.audit_store = AuditStore(db_path=db_path)

        output_dir = self.root / storage_cfg.get("output_dir", "data/output")
        quarantine_dir = self.root / storage_cfg.get("quarantine_dir", "data/quarantine")
        reports_dir = self.root / storage_cfg.get("reports_dir", "reports")
        target_format = storage_cfg.get("target_format", "both")

        self.publisher = Publisher(
            audit_store=self.audit_store,
            output_dir=output_dir,
            quarantine_dir=quarantine_dir,
            reports_dir=reports_dir,
            target_format=target_format,
        )

        # Initialize reference providers for referential integrity checking
        ref_providers_df = generate_reference_providers()
        valid_provider_ids = set(ref_providers_df["provider_id"].tolist())

        self.profiler = DatasetProfiler()
        self.validator = DatasetValidator(valid_providers=valid_provider_ids)

        secret_salt = self.config.get("pipeline", {}).get("hmac_secret_salt", "yottaflex_default_salt")
        self.transformer = DatasetTransformer(privacy_rules=self.rules, secret_salt=secret_salt)

    def run(
        self,
        input_data: str | Path | pd.DataFrame,
        run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute the end-to-end data pipeline.

        Args:
            input_data: Path to input CSV file, or an in-memory DataFrame.
            run_id: Optional custom run identifier; auto-generated if omitted.

        Returns:
            Dictionary containing run metrics, artifacts, and reconciliation outcome.
        """
        start_time = time.time()
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        if not run_id:
            run_id = f"RUN_{now_str}_{uuid.uuid4().hex[:6].upper()}"

        logger.info(f"Starting pipeline execution [Run ID: {run_id}]")

        try:
            # 1. Ingestion
            if isinstance(input_data, pd.DataFrame):
                raw_df = input_data.copy()
                source_description = "in_memory_dataframe"
            else:
                input_path = Path(input_data)
                if not input_path.is_absolute():
                    input_path = self.root / input_path
                if not input_path.exists():
                    raise FileNotFoundError(f"Input file does not exist: {input_path}")
                raw_df = pd.read_csv(input_path)
                source_description = str(input_path)

            input_count = len(raw_df)
            self.audit_store.record_run_start(run_id=run_id, input_count=input_count)
            logger.info(f"Ingested {input_count} records from {source_description}")

            # 2. Profiling
            profiling_metrics = self.profiler.profile(raw_df)
            logger.info(
                f"Data Profiling Complete: {profiling_metrics['dataset_metrics']['sensitive_column_count']} "
                f"sensitive columns detected: {profiling_metrics['dataset_metrics']['sensitive_columns']}"
            )

            # 3. Validation & Quarantine
            validation_result = self.validator.validate(raw_df, run_id=run_id)
            valid_df = validation_result.valid_df
            quarantined_df = validation_result.quarantined_df

            logger.info(
                f"Validation finished: {len(valid_df)} valid, "
                f"{len(quarantined_df)} quarantined records"
            )

            # Persist Quarantine
            quarantine_file = self.publisher.publish_quarantine(quarantined_df, run_id=run_id)

            # 4. Privacy Transformation & Data Minimization
            published_df = self.transformer.transform(valid_df, run_id=run_id)
            logger.info(
                f"Privacy transformation & minimization complete. Published shape: {published_df.shape}"
            )

            # 5. Target Publishing (SQLite, Parquet, CSV)
            published_artifacts = self.publisher.publish_analytical_dataset(published_df, run_id=run_id)

            # 6. Reconciliation & Data Quality Metrics
            reconciliation = self.publisher.generate_reconciliation_report(
                run_id=run_id,
                raw_df=raw_df,
                valid_df=valid_df,
                quarantined_df=quarantined_df,
                published_df=published_df,
                profiling_metrics=profiling_metrics,
            )

            # Log quality metrics into SQLite
            self.audit_store.log_metrics(run_id, {
                "input_count": input_count,
                "valid_count": len(valid_df),
                "quarantined_count": len(quarantined_df),
                "published_count": len(published_df),
                **validation_result.metrics.get("rejections_by_code", {})
            })

            execution_seconds = round(time.time() - start_time, 4)
            status = "SUCCESS" if reconciliation["reconciliation_status"] == "BALANCED" else "PARTIAL_SUCCESS"

            self.audit_store.record_run_completion(
                run_id=run_id,
                status=status,
                valid_count=len(valid_df),
                quarantined_count=len(quarantined_df),
                published_count=len(published_df),
                execution_seconds=execution_seconds,
            )

            logger.info(
                f"Pipeline execution completed [{status}] in {execution_seconds}s. "
                f"Published: {len(published_df)} rows."
            )

            return {
                "run_id": run_id,
                "status": status,
                "execution_seconds": execution_seconds,
                "input_count": input_count,
                "valid_count": len(valid_df),
                "quarantined_count": len(quarantined_df),
                "published_count": len(published_df),
                "reconciliation": reconciliation,
                "quarantine_file": quarantine_file,
                "published_artifacts": published_artifacts,
            }

        except Exception as e:
            execution_seconds = round(time.time() - start_time, 4)
            error_msg = str(e)
            logger.error(f"Pipeline failed [Run ID: {run_id}]: {error_msg}", exc_info=True)
            self.audit_store.record_run_completion(
                run_id=run_id,
                status="FAILED",
                valid_count=0,
                quarantined_count=0,
                published_count=0,
                execution_seconds=execution_seconds,
                failure_reason=error_msg,
            )
            raise
