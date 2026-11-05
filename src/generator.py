"""Synthetic Dataset Generator.

Generates realistic healthcare patient encounter datasets with:
- Normal valid records with realistic clinical and demographic fields
- Deliberately injected anomalies and edge cases:
  * Malformed email / phone / national_id
  * Missing required fields (null patient_id, null full_name)
  * Duplicate primary keys (encounter_id collision)
  * Invalid foreign keys (unrecognized provider_id)
  * Out-of-bounds metrics (negative treatment_cost)
  * Invalid / malformed timestamps
- Reproducibility via configurable seed.
"""

from datetime import datetime, timedelta
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


# Standard Reference Providers
DEFAULT_PROVIDERS = [
    {"provider_id": "PRV-101", "provider_name": "Metro General Hospital", "department": "Cardiology", "facility_code": "FAC-A"},
    {"provider_id": "PRV-102", "provider_name": "Sunrise Health Clinic", "department": "Endocrinology", "facility_code": "FAC-B"},
    {"provider_id": "PRV-103", "provider_name": "Pine Valley Medical", "department": "Pulmonology", "facility_code": "FAC-C"},
    {"provider_id": "PRV-104", "provider_name": "Summit Oncology Center", "department": "Oncology", "facility_code": "FAC-D"},
    {"provider_id": "PRV-105", "provider_name": "Lakeview Family Care", "department": "General Medicine", "facility_code": "FAC-E"},
]

# Standard Diagnoses
DIAGNOSES = [
    ("E11.9", "Type 2 diabetes mellitus without complications", 250.0, 1800.0),
    ("I10", "Essential (primary) hypertension", 180.0, 1200.0),
    ("J45.9", "Other and unspecified asthma", 300.0, 2200.0),
    ("M54.5", "Low back pain, unspecified", 150.0, 1500.0),
    ("K21.9", "Gastro-esophageal reflux disease without esophagitis", 200.0, 1100.0),
    ("F41.1", "Generalized anxiety disorder", 220.0, 1400.0),
    ("E78.5", "Hyperlipidemia, unspecified", 190.0, 1300.0),
    ("J06.9", "Acute upper respiratory infection", 110.0, 650.0),
]

FIRST_NAMES = [
    "Ravi", "Priya", "Kiran", "Amit", "Sneha", "Rahul", "Ananya", "Vikram",
    "Pooja", "Arjun", "Deepa", "Suresh", "Divya", "Manoj", "Kavita", "Rajesh",
    "John", "Sarah", "Michael", "Emily", "David", "Jessica", "James", "Maria"
]

LAST_NAMES = [
    "Kumar", "Reddy", "Rao", "Sharma", "Patel", "Verma", "Singh", "Nair",
    "Iyer", "Gupta", "Joshi", "Deshmukh", "Smith", "Johnson", "Brown", "Williams"
]

DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "healthcare.org", "company.com"]


def generate_reference_providers(output_path: Optional[str | Path] = None) -> pd.DataFrame:
    """Generate and optionally save reference providers dataset."""
    df = pd.DataFrame(DEFAULT_PROVIDERS)
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)
    return df


def generate_encounters_dataset(
    num_records: int = 500,
    invalid_ratio: float = 0.05,
    duplicate_ratio: float = 0.03,
    seed: int = 42,
    output_path: Optional[str | Path] = None
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Generate synthetic patient encounter dataset with controlled edge cases.

    Args:
        num_records: Total number of base records to generate.
        invalid_ratio: Fraction of records with deliberate validation defects.
        duplicate_ratio: Fraction of records duplicated.
        seed: Random seed for exact reproducibility.
        output_path: Optional path to write output CSV.

    Returns:
        Tuple of (DataFrame, metadata dictionary with expected counts).
    """
    rng = np.random.default_rng(seed)

    # 1. Base Valid Records Generation
    first_names = rng.choice(FIRST_NAMES, size=num_records)
    last_names = rng.choice(LAST_NAMES, size=num_records)
    full_names = [f"{f} {l}" for f, l in zip(first_names, last_names)]

    domains = rng.choice(DOMAINS, size=num_records)
    emails = [
        f"{f.lower()}.{l.lower()}{rng.integers(10, 999)}@{d}"
        for f, l, d in zip(first_names, last_names, domains)
    ]

    phone_numbers = [
        f"+1-{rng.integers(200, 999):03d}-{rng.integers(100, 999):03d}-{rng.integers(1000, 9999):04d}"
        for _ in range(num_records)
    ]

    national_ids = [
        f"{rng.integers(100, 999):03d}-{rng.integers(10, 99):02d}-{rng.integers(1000, 9999):04d}"
        for _ in range(num_records)
    ]

    # Patients (with some returning patients)
    num_unique_patients = max(10, int(num_records * 0.7))
    patient_ids = [f"PAT-{rng.integers(1000, 1000 + num_unique_patients):05d}" for _ in range(num_records)]

    # Encounters
    encounter_ids = [f"ENC-{i+1:07d}" for i in range(num_records)]

    # Birth dates between 1940 and 2015
    start_birth = datetime(1940, 1, 1)
    birth_days = rng.integers(0, 27000, size=num_records)
    birth_dates = [(start_birth + timedelta(days=int(d))).strftime("%Y-%m-%d") for d in birth_days]

    genders = rng.choice(["Male", "Female", "Other"], size=num_records, p=[0.48, 0.48, 0.04])

    valid_provider_ids = [p["provider_id"] for p in DEFAULT_PROVIDERS]
    provider_ids = rng.choice(valid_provider_ids, size=num_records)

    diag_indices = rng.integers(0, len(DIAGNOSES), size=num_records)
    diag_codes = [DIAGNOSES[i][0] for i in diag_indices]
    diag_descs = [DIAGNOSES[i][1] for i in diag_indices]

    base_costs = [
        round(float(rng.uniform(DIAGNOSES[i][2], DIAGNOSES[i][3])), 2)
        for i in diag_indices
    ]

    # Encounter timestamps within past 365 days
    now = datetime(2026, 11, 1, 10, 0, 0)
    minutes_ago = rng.integers(0, 525600, size=num_records)
    encounter_timestamps = [
        (now - timedelta(minutes=int(m))).isoformat() + "Z"
        for m in minutes_ago
    ]

    df = pd.DataFrame({
        "encounter_id": encounter_ids,
        "patient_id": patient_ids,
        "full_name": full_names,
        "email": emails,
        "phone_number": phone_numbers,
        "national_id": national_ids,
        "birth_date": birth_dates,
        "gender": genders,
        "provider_id": provider_ids,
        "diagnosis_code": diag_codes,
        "diagnosis_desc": diag_descs,
        "treatment_cost": base_costs,
        "encounter_timestamp": encounter_timestamps,
    })

    # Add ingestion_timestamp
    df["ingestion_timestamp"] = datetime(2026, 11, 5, 23, 0, 0).isoformat() + "Z"

    # 2. Inject Controlled Edge Cases & Deliberately Labelled Anomalies
    num_invalids = int(num_records * invalid_ratio)
    invalid_counts = {
        "missing_patient_id": 0,
        "missing_full_name": 0,
        "malformed_email": 0,
        "negative_cost": 0,
        "invalid_provider_id": 0,
        "malformed_timestamp": 0,
    }

    if num_invalids > 0:
        # Pick random indices to corrupt
        defect_indices = rng.choice(num_records, size=num_invalids, replace=False)
        subsets = np.array_split(defect_indices, 6)

        # 1. Missing patient_id
        for idx in subsets[0]:
            df.at[idx, "patient_id"] = np.nan
            invalid_counts["missing_patient_id"] += 1

        # 2. Missing full_name
        for idx in subsets[1]:
            df.at[idx, "full_name"] = None
            invalid_counts["missing_full_name"] += 1

        # 3. Malformed email (missing @ or domain)
        for idx in subsets[2]:
            df.at[idx, "email"] = "not-a-valid-email.com"
            invalid_counts["malformed_email"] += 1

        # 4. Negative treatment cost
        for idx in subsets[3]:
            df.at[idx, "treatment_cost"] = -abs(df.at[idx, "treatment_cost"])
            invalid_counts["negative_cost"] += 1

        # 5. Invalid foreign key provider_id
        for idx in subsets[4]:
            df.at[idx, "provider_id"] = "PRV-999-NONEXISTENT"
            invalid_counts["invalid_provider_id"] += 1

        # 6. Malformed timestamp
        for idx in subsets[5]:
            df.at[idx, "encounter_timestamp"] = "INVALID_TIMESTAMP_2026_XYZ"
            invalid_counts["malformed_timestamp"] += 1

    # 3. Inject Duplicate Records
    num_duplicates = int(num_records * duplicate_ratio)
    duplicate_records_count = 0
    if num_duplicates > 0:
        dup_indices = rng.choice(num_records, size=num_duplicates, replace=False)
        duplicates_df = df.iloc[dup_indices].copy()
        # Append duplicates to dataframe to test deduplication / collision handling
        df = pd.concat([df, duplicates_df], ignore_index=True)
        duplicate_records_count = num_duplicates

    # Shuffle slightly while keeping deterministic seed
    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    metadata = {
        "total_generated": len(df),
        "base_records": num_records,
        "invalids_injected": num_invalids,
        "duplicates_injected": duplicate_records_count,
        "defect_breakdown": invalid_counts,
        "seed": seed
    }

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_p, index=False)

    return df, metadata
