"""Tests for Synthetic Dataset Generator."""

import pandas as pd
import pytest
from src.generator import generate_encounters_dataset, generate_reference_providers


def test_generate_reference_providers():
    """Verify reference provider dataset structure."""
    df = generate_reference_providers()
    assert not df.empty
    assert "provider_id" in df.columns
    assert len(df) >= 5
    assert df["provider_id"].is_unique


def test_reproducible_generation():
    """Verify generator produces identical datasets given identical seeds."""
    df1, meta1 = generate_encounters_dataset(num_records=100, seed=123)
    df2, meta2 = generate_encounters_dataset(num_records=100, seed=123)

    assert meta1["total_generated"] == meta2["total_generated"]
    pd.testing.assert_frame_equal(df1, df2)


def test_controlled_invalids_and_duplicates_injection():
    """Verify deliberate anomalies are injected proportionally."""
    num_records = 200
    df, meta = generate_encounters_dataset(
        num_records=num_records,
        invalid_ratio=0.10,
        duplicate_ratio=0.05,
        seed=42
    )

    assert meta["invalids_injected"] == 20
    assert meta["duplicates_injected"] == 10
    assert len(df) == 210  # 200 base + 10 duplicates
    assert sum(meta["defect_breakdown"].values()) == 20
