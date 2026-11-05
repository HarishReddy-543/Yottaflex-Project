"""Privacy-Aware Data Engineering Pipeline CLI Entrypoint.

Provides commands to:
1. Generate synthetic reproducible datasets (small starter sample or scalable 100k+)
2. Execute the full end-to-end data pipeline
3. Run large-scale performance benchmarking
4. Inspect pipeline execution audit trails and quarantine logs
"""

import argparse
import json
import logging
from pathlib import Path
import sys
import time
import pandas as pd

from src.audit import AuditStore
from src.config_loader import get_project_root, load_pipeline_config
from src.generator import generate_encounters_dataset, generate_reference_providers
from src.pipeline import PrivacyPipeline


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CLI")


def handle_generate(args, root: Path, config: dict):
    """Generate synthetic test datasets and reference providers."""
    gen_cfg = config.get("dataset_generator", {})
    count = args.count or gen_cfg.get("default_sample_size", 500)
    seed = args.seed or gen_cfg.get("seed", 42)
    invalid_ratio = args.invalid_ratio if args.invalid_ratio is not None else gen_cfg.get("invalid_ratio", 0.05)
    duplicate_ratio = args.duplicate_ratio if args.duplicate_ratio is not None else gen_cfg.get("duplicate_ratio", 0.03)

    out_file = args.output or (root / "data/input/sample_data.csv")

    # Generate reference providers
    ref_file = root / "data/input/reference_providers.csv"
    generate_reference_providers(output_path=ref_file)
    logger.info(f"Generated reference providers at: {ref_file}")

    # Generate encounters
    df, meta = generate_encounters_dataset(
        num_records=count,
        invalid_ratio=invalid_ratio,
        duplicate_ratio=duplicate_ratio,
        seed=seed,
        output_path=out_file,
    )

    print("\n" + "=" * 60)
    print(" DATA GENERATION SUMMARY")
    print("=" * 60)
    print(f" Output Path       : {out_file}")
    print(f" Total Rows        : {meta['total_generated']}")
    print(f" Base Records      : {meta['base_records']}")
    print(f" Deliberate Errors : {meta['invalids_injected']}")
    print(f" Duplicates Added  : {meta['duplicates_injected']}")
    print(f" Random Seed       : {meta['seed']}")
    print(" Defect Breakdown  :")
    for defect, c in meta["defect_breakdown"].items():
        print(f"   - {defect:<24}: {c}")
    print("=" * 60 + "\n")


def handle_run(args, root: Path):
    """Run the pipeline on specified input file."""
    input_path = args.input or (root / "data/input/sample_data.csv")
    pipeline = PrivacyPipeline()
    result = pipeline.run(input_data=input_path, run_id=args.run_id)

    print("\n" + "=" * 65)
    print(f" PIPELINE EXECUTION SUMMARY: {result['status']}")
    print("=" * 65)
    print(f" Run ID             : {result['run_id']}")
    print(f" Execution Duration : {result['execution_seconds']} seconds")
    print(f" Input Records      : {result['input_count']}")
    print(f" Valid Records      : {result['valid_count']}")
    print(f" Quarantined Records: {result['quarantined_count']}")
    print(f" Published Records  : {result['published_count']}")
    print(f" Reconciliation     : {result['reconciliation']['reconciliation_status']}")
    print(f" Cost Reconciled    : {result['reconciliation']['financial_aggregate_reconciliation']['is_cost_balanced']}")
    if result["quarantine_file"]:
        print(f" Quarantine File    : {result['quarantine_file']}")
    print(" Published Files    :")
    for k, v in result["published_artifacts"].items():
        print(f"   - {k:<18}: {v}")
    print("=" * 65 + "\n")


def handle_benchmark(args, root: Path, config: dict):
    """Run performance benchmark on large volume (default 100,000 records)."""
    count = args.count or config.get("dataset_generator", {}).get("large_dataset_size", 100000)
    seed = 42

    print(f"\n[1/3] Generating synthetic benchmark dataset of {count:,} records...")
    t0 = time.time()
    benchmark_file = root / "data/input/benchmark_100k.csv"
    generate_reference_providers(output_path=root / "data/input/reference_providers.csv")
    df, meta = generate_encounters_dataset(
        num_records=count,
        invalid_ratio=0.03,
        duplicate_ratio=0.02,
        seed=seed,
        output_path=benchmark_file,
    )
    gen_time = round(time.time() - t0, 3)
    print(f"       Dataset generated in {gen_time}s ({int(len(df)/gen_time):,} records/sec)")

    print(f"[2/3] Executing pipeline across {len(df):,} records...")
    pipeline = PrivacyPipeline()
    t_pipe_start = time.time()
    result = pipeline.run(input_data=benchmark_file, run_id=f"BENCHMARK_{count}_{int(time.time())}")
    pipe_duration = round(time.time() - t_pipe_start, 3)
    throughput = int(len(df) / pipe_duration)

    print(f"[3/3] Compiling Performance Report...")
    benchmark_report = {
        "benchmark_timestamp": pd.Timestamp.now().isoformat() + "Z",
        "dataset_size": len(df),
        "total_runtime_seconds": pipe_duration,
        "throughput_records_per_second": throughput,
        "valid_published": result["published_count"],
        "quarantined": result["quarantined_count"],
        "reconciliation_status": result["reconciliation"]["reconciliation_status"],
        "optimization_notes": {
            "technique_applied": "Vectorized HMAC tokenization & column projection with SQLite WAL pragma",
            "future_optimization": "Apache Arrow chunked streaming / DuckDB out-of-core pipeline for 10M+ scaling"
        }
    }

    report_path = root / "reports/benchmark_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_report, f, indent=2)

    print("\n" + "=" * 65)
    print(f" BENCHMARK RESULTS ({count:,} RECORDS)")
    print("=" * 65)
    print(f" Total Runtime  : {pipe_duration} seconds")
    print(f" Throughput     : {throughput:,} records/second")
    print(f" Published Rows : {result['published_count']:,}")
    print(f" Quarantined    : {result['quarantined_count']:,}")
    print(f" Reconciliation : {result['reconciliation']['reconciliation_status']}")
    print(f" Report Path    : {report_path}")
    print("=" * 65 + "\n")


def handle_audit(args, root: Path, config: dict):
    """Display audit logs and quarantine statistics."""
    db_path = root / config.get("storage", {}).get("db_path", "data/audit/pipeline_metadata.sqlite")
    if not db_path.exists():
        print("No audit database found. Run the pipeline first.")
        return

    audit = AuditStore(db_path=db_path)
    runs = audit.get_all_runs()

    print("\n" + "=" * 80)
    print(f" PIPELINE AUDIT LOGS (Total Runs: {len(runs)})")
    print("=" * 80)
    print(f"{'Run ID':<30} {'Status':<10} {'Input':<8} {'Valid':<8} {'Quarantine':<12} {'Time(s)':<8}")
    print("-" * 80)
    for r in runs[:10]:
        print(f"{r['run_id']:<30} {r['status']:<10} {r['input_count']:<8} {r['valid_count']:<8} {r['quarantined_count']:<12} {round(r['execution_seconds'], 2):<8}")

    stats = audit.get_quarantine_stats()
    if stats:
        print("\n" + "-" * 80)
        print(" QUARANTINE REJECTION BREAKDOWN:")
        print("-" * 80)
        for s in stats:
            print(f" - {s['rejection_code']:<32}: {s['count']} records (e.g. {s['sample_reason']})")
    print("=" * 80 + "\n")


def main():
    root = get_project_root()
    config = load_pipeline_config(root / "config/config.yaml")

    parser = argparse.ArgumentParser(description="Privacy-Aware Data Engineering Pipeline CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # generate subcommand
    gen_p = subparsers.add_parser("generate", help="Generate synthetic test dataset")
    gen_p.add_argument("--count", type=int, default=None, help="Number of records to generate (default: 500)")
    gen_p.add_argument("--output", type=str, default=None, help="Output file path (default: data/input/sample_data.csv)")
    gen_p.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    gen_p.add_argument("--invalid-ratio", type=float, default=None, help="Ratio of invalid anomaly records")
    gen_p.add_argument("--duplicate-ratio", type=float, default=None, help="Ratio of duplicate records")

    # run subcommand
    run_p = subparsers.add_parser("run", help="Execute the data pipeline")
    run_p.add_argument("--input", type=str, default=None, help="Input CSV path (default: data/input/sample_data.csv)")
    run_p.add_argument("--run-id", type=str, default=None, help="Custom Run ID")

    # benchmark subcommand
    bench_p = subparsers.add_parser("benchmark", help="Run 100k benchmark performance test")
    bench_p.add_argument("--count", type=int, default=100000, help="Number of records for benchmark")

    # audit subcommand
    subparsers.add_parser("audit", help="Inspect pipeline execution audit history and quarantine stats")

    args = parser.parse_args()

    if args.command == "generate":
        handle_generate(args, root, config)
    elif args.command == "run":
        handle_run(args, root)
    elif args.command == "benchmark":
        handle_benchmark(args, root, config)
    elif args.command == "audit":
        handle_audit(args, root, config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
