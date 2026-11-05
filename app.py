"""Interactive Streamlit Dashboard for Privacy-Aware Data Pipeline.

Provides visual interfaces for:
1. Pipeline Operations & Execution Logs
2. Data Profiling & Sensitive Field Detection
3. Quarantine Triage & Root Cause Diagnostics
4. Published Analytical Dataset Explorer
5. Audit Trail & Data Reconciliation
"""

import json
from pathlib import Path
import sqlite3
import pandas as pd
import streamlit as st

from src.config_loader import get_project_root, load_pipeline_config
from src.pipeline import PrivacyPipeline


st.set_page_config(
    page_title="Privacy-Aware Data Engineering Pipeline",
    page_icon="🛡️",
    layout="wide",
)

root = get_project_root()
config = load_pipeline_config()
db_path = root / config.get("storage", {}).get("db_path", "data/audit/pipeline_metadata.sqlite")


def get_db_connection():
    return sqlite3.connect(str(db_path))


st.title("🛡️ Privacy-Aware Data Engineering Pipeline")
st.markdown(
    "**Associate AI Data Forward Deployed Engineer Challenge** | "
    "Automated Profiling, Configurable Privacy Masking/Tokenization, Data Minimization & Audit Trail"
)

tabs = st.tabs([
    "📊 Pipeline Overview & Runs",
    "🔍 Sensitive Field Profiling",
    "🚫 Quarantine Inspector",
    "📈 Published Analytical Data",
    "⚖️ Reconciliation & Audit",
])

# Tab 1: Overview & Runs
with tabs[0]:
    st.header("Pipeline Runs & Execution Metrics")

    col1, col2, col3, col4 = st.columns(4)

    if db_path.exists():
        with get_db_connection() as conn:
            runs_df = pd.read_sql_query("SELECT * FROM pipeline_runs ORDER BY start_time DESC", conn)
            analytical_count = pd.read_sql_query("SELECT COUNT(*) as count FROM analytical_encounters", conn).iloc[0]["count"]
            quarantine_count = pd.read_sql_query("SELECT COUNT(*) as count FROM quarantined_records", conn).iloc[0]["count"]

        total_runs = len(runs_df)
        success_runs = len(runs_df[runs_df["status"] == "SUCCESS"])

        col1.metric("Total Executions", total_runs)
        col2.metric("Successful Runs", success_runs)
        col3.metric("Published Encounters", f"{analytical_count:,}")
        col4.metric("Quarantined Records", f"{quarantine_count:,}")

        st.subheader("Recent Execution Audit Trail")
        st.dataframe(
            runs_df[[
                "run_id", "status", "input_count", "valid_count",
                "quarantined_count", "published_count", "execution_seconds", "start_time"
            ]],
            use_container_width=True
        )
    else:
        st.info("No runs recorded yet. Run the pipeline via CLI or below.")

    st.divider()
    st.subheader("⚡ Trigger Pipeline Run")
    sample_file = root / "data/input/sample_data.csv"
    if st.button("Run Pipeline on Sample Data", type="primary"):
        with st.spinner("Processing pipeline..."):
            pipeline = PrivacyPipeline()
            res = pipeline.run(input_data=sample_file)
            st.success(f"Pipeline executed successfully! Run ID: {res['run_id']} in {res['execution_seconds']}s")
            st.rerun()

# Tab 2: Profiling
with tabs[1]:
    st.header("Sensitive Field Profiling & PII Classification")
    val_report_path = root / "reports/validation_report.json"

    if val_report_path.exists():
        with open(val_report_path, "r", encoding="utf-8") as f:
            v_data = json.load(f)

        st.subheader("Dataset Metrics")
        st.json(v_data.get("profiling_summary", {}))

    sample_csv = root / "data/input/sample_data.csv"
    if sample_csv.exists():
        st.subheader("Raw Ingested Sample (Top 5)")
        st.dataframe(pd.read_csv(sample_csv).head(5), use_container_width=True)

# Tab 3: Quarantine
with tabs[2]:
    st.header("Quarantine & Rejection Analysis")
    if db_path.exists():
        with get_db_connection() as conn:
            q_stats = pd.read_sql_query("""
                SELECT rejection_code, COUNT(*) as count, MIN(rejection_reason) as sample_reason
                FROM quarantined_records
                GROUP BY rejection_code
                ORDER BY count DESC
            """, conn)

            q_records = pd.read_sql_query("""
                SELECT run_id, source_row_index, encounter_id, rejection_code, rejection_reason, raw_record_json, quarantined_at
                FROM quarantined_records
                ORDER BY id DESC LIMIT 50
            """, conn)

        st.subheader("Rejection Reasons Breakdown")
        st.dataframe(q_stats, use_container_width=True)

        st.subheader("Recent Quarantined Records (Traceable Source Snapshot)")
        st.dataframe(q_records, use_container_width=True)
    else:
        st.info("No quarantine records found.")

# Tab 4: Published Data
with tabs[3]:
    st.header("Published Analytical Dataset (Privacy-Preserved & Minimized)")
    out_csv = root / "data/output/analytical_encounters.csv"
    if out_csv.exists():
        df_out = pd.read_csv(out_csv)
        st.markdown(f"**Total Records Published**: {len(df_out):,}")
        st.markdown(
            "Notice: Direct identifiers (`patient_id`, `full_name`, `email`, `phone_number`, `national_id`) "
            "have been **purged** or **transformed** into `patient_token`, `masked_name`, `masked_email`, and `age_group`."
        )
        st.dataframe(df_out.head(20), use_container_width=True)

        st.subheader("Clinical Metrics Summary")
        colA, colB = st.columns(2)
        with colA:
            st.markdown("**Diagnosis Distribution**")
            st.bar_chart(df_out["diagnosis_code"].value_counts())
        with colB:
            st.markdown("**Age Cohort Distribution**")
            st.bar_chart(df_out["age_group"].value_counts())
    else:
        st.info("No published analytical dataset available yet.")

# Tab 5: Reconciliation & Audit
with tabs[4]:
    st.header("Reconciliation Proof & Financial Aggregates")
    recon_path = root / "reports/reconciliation_report.json"
    if recon_path.exists():
        with open(recon_path, "r", encoding="utf-8") as f:
            recon = json.load(f)

        st.json(recon)
    else:
        st.info("Reconciliation report not generated yet.")

    bench_path = root / "reports/benchmark_report.json"
    if bench_path.exists():
        st.subheader("Latest 100k Benchmark Report")
        with open(bench_path, "r", encoding="utf-8") as f:
            bench = json.load(f)
        st.json(bench)
