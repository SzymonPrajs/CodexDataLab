from __future__ import annotations

from typing import Any

import polars as pl


def schema_and_nulls(df: pl.DataFrame) -> dict[str, Any]:
    null_counts = df.null_count()
    rows = []
    for name, dtype in df.schema.items():
        null_value = null_counts.select(name).item()
        rows.append(
            {
                "column": name,
                "dtype": str(dtype),
                "nulls": int(null_value),
            }
        )
    return {"rows": rows}


def numeric_summary(df: pl.DataFrame) -> dict[str, Any]:
    rows = []
    for name, dtype in df.schema.items():
        if dtype.is_numeric():
            stats = df.select(
                [
                    pl.col(name).min().alias("min"),
                    pl.col(name).max().alias("max"),
                    pl.col(name).mean().alias("mean"),
                ]
            )
            row = stats.to_dicts()[0]
            row["column"] = name
            rows.append(row)
    return {"rows": rows}


def value_counts(df: pl.DataFrame, column: str, *, limit: int = 10) -> dict[str, Any]:
    counts = df.select(pl.col(column).value_counts()).unnest(column)
    counts = counts.sort("counts", descending=True).head(limit)
    return {"rows": counts.to_dicts()}


def groupby_count(df: pl.DataFrame, columns: list[str]) -> dict[str, Any]:
    group = df.group_by(columns).len().sort("len", descending=True)
    return {"rows": group.to_dicts()}


def categorical_summary(df: pl.DataFrame, *, limit: int = 3) -> dict[str, Any]:
    rows = []
    for name, dtype in df.schema.items():
        if dtype == pl.Utf8 or dtype == pl.Categorical:
            counts = df.select(pl.col(name).value_counts()).unnest(name)
            count_col = "counts" if "counts" in counts.columns else "count"
            counts = counts.sort(count_col, descending=True).head(limit)
            row = {
                "column": name,
                "unique": int(df.select(pl.col(name).n_unique()).item()),
                "top_values": counts.to_dicts(),
            }
            rows.append(row)
    return {"rows": rows}
