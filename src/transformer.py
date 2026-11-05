"""Dataset Transformer and Data Minimization Engine.

Applies privacy transformations and enforces strict data minimization:
- Retains only approved analytical columns
- Ensures raw sensitive identifiers are purged
- Attaches operational lineage metadata (run_id, published_at)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List
import pandas as pd
from src.privacy import PrivacyTransformer


class DatasetTransformer:
    """Transforms validated data into minimized analytical dataset."""

    def __init__(self, privacy_rules: Dict[str, Any], secret_salt: str = "default_secure_salt"):
        self.privacy_rules = privacy_rules
        self.privacy_engine = PrivacyTransformer(privacy_rules=privacy_rules, secret_salt=secret_salt)
        self.minimized_columns = privacy_rules.get("minimized_analytical_columns", [])
        self.dropped_fields = privacy_rules.get("dropped_sensitive_fields", [])

    def transform(self, valid_df: pd.DataFrame, run_id: str) -> pd.DataFrame:
        """Apply privacy rules, inject lineage metadata, and filter minimized columns.

        Args:
            valid_df: Validated DataFrame.
            run_id: Pipeline execution identifier.

        Returns:
            Minimized analytical DataFrame ready for target publishing.
        """
        if valid_df.empty:
            return pd.DataFrame(columns=self.minimized_columns)

        # 1. Apply Privacy Transformations (Tokenization, Masking, Generalization)
        transformed_df = self.privacy_engine.apply_transformations(valid_df)

        # 2. Attach Operational Lineage Metadata
        published_timestamp = datetime.now(timezone.utc).isoformat()
        transformed_df["run_id"] = run_id
        transformed_df["published_at"] = published_timestamp

        # 3. Ensure Numeric and Analytical Types are Standard
        if "treatment_cost" in transformed_df.columns:
            transformed_df["treatment_cost"] = transformed_df["treatment_cost"].astype(float)

        # 4. Enforce Data Minimization: Keep only analytical columns
        available_columns = [col for col in self.minimized_columns if col in transformed_df.columns]
        minimized_df = transformed_df[available_columns].copy()

        # 5. Sanity Check: Assert that raw sensitive fields were purged
        for dropped in self.dropped_fields:
            if dropped in minimized_df.columns:
                raise RuntimeError(
                    f"Privacy Violation: Field '{dropped}' was expected to be dropped, but exists in minimized output!"
                )

        return minimized_df
