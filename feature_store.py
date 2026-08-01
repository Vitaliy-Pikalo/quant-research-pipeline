"""
feature_store.py — Point-in-time (PIT) feature store.

The single most common source of silent look-ahead bias in retail-grade
backtests is storing a feature indexed by the period it *describes* (e.g.
"Q1 2023 revenue") rather than the timestamp it became *publicly knowable*
(the 10-Q filing timestamp, which can be 30-45 days after quarter-end).

This store enforces a two-timestamp discipline on every feature:
  - period_end   : what period the value describes (for readability/joins)
  - known_at     : the actual PIT timestamp the value became available

`as_of(query_time)` only ever returns the latest value with known_at <=
query_time, which is the only query pattern that is backtest-safe.

Also tracks a `source_version` per feature (critical for LLM-derived
features, where regenerating an embedding/classification with a newer model
version changes historical values if you re-run your pipeline later —
without version pinning this silently reintroduces look-ahead bias).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class PITFeatureStore:
    db_path: str = ":memory:"

    def __post_init__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS features (
                entity_id     TEXT NOT NULL,
                feature_name  TEXT NOT NULL,
                period_end    TEXT,
                known_at      TEXT NOT NULL,
                value         REAL,
                source_version TEXT,
                PRIMARY KEY (entity_id, feature_name, known_at)
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_lookup ON features (entity_id, feature_name, known_at)"
        )
        self.conn.commit()

    def write(
        self,
        entity_id: str,
        feature_name: str,
        known_at: pd.Timestamp,
        value: float,
        period_end: pd.Timestamp | None = None,
        source_version: str = "v1",
    ) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO features VALUES (?, ?, ?, ?, ?, ?)",
            (
                entity_id,
                feature_name,
                str(period_end) if period_end is not None else None,
                str(known_at),
                float(value),
                source_version,
            ),
        )

    def write_batch(self, df: pd.DataFrame) -> None:
        """df columns: entity_id, feature_name, known_at, value, [period_end, source_version]"""
        required = {"entity_id", "feature_name", "known_at", "value"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"missing required columns: {missing}")
        rows = df.copy()
        if "period_end" not in rows.columns:
            rows["period_end"] = None
        if "source_version" not in rows.columns:
            rows["source_version"] = "v1"
        rows["known_at"] = rows["known_at"].astype(str)
        rows["period_end"] = rows["period_end"].astype(str)
        self.conn.executemany(
            "INSERT OR REPLACE INTO features VALUES (?, ?, ?, ?, ?, ?)",
            rows[
                ["entity_id", "feature_name", "period_end", "known_at", "value", "source_version"]
            ].itertuples(index=False, name=None),
        )
        self.conn.commit()

    def as_of(self, entity_ids: list[str], feature_names: list[str], query_time: pd.Timestamp) -> pd.DataFrame:
        """
        THE ONLY BACKTEST-SAFE READ PATH. Returns, for each (entity, feature),
        the most recent value with known_at <= query_time. Anything else
        (e.g. joining on period_end) risks look-ahead bias.
        """
        placeholders_e = ",".join(["?"] * len(entity_ids))
        placeholders_f = ",".join(["?"] * len(feature_names))
        q = f"""
            SELECT entity_id, feature_name, value, known_at
            FROM features
            WHERE entity_id IN ({placeholders_e})
              AND feature_name IN ({placeholders_f})
              AND known_at <= ?
            AND known_at = (
                SELECT MAX(known_at) FROM features f2
                WHERE f2.entity_id = features.entity_id
                  AND f2.feature_name = features.feature_name
                  AND f2.known_at <= ?
            )
        """
        params = entity_ids + feature_names + [str(query_time), str(query_time)]
        return pd.read_sql_query(q, self.conn, params=params)

    def panel_as_of(
        self, entity_ids: list[str], feature_names: list[str], query_times: list[pd.Timestamp]
    ) -> pd.DataFrame:
        """Convenience wrapper: builds a full (entity x feature) panel across
        multiple query timestamps, e.g. every monthly rebalance date."""
        frames = []
        for qt in query_times:
            df = self.as_of(entity_ids, feature_names, qt)
            df["query_time"] = qt
            frames.append(df)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def close(self):
        self.conn.close()
