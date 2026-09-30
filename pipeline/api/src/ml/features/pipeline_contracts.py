"""Fail-loud dtype and key contracts for pipeline boundaries."""

from __future__ import annotations

import pandas as pd


def require_columns(
    df: pd.DataFrame,
    required_columns: list[str],
    label: str,
) -> pd.DataFrame:
    """Ensure a DataFrame contains the required columns."""
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise KeyError(f"{label} is missing required columns: {missing}")
    return df


def coerce_string_columns(
    df: pd.DataFrame,
    columns: list[str],
    label: str,
) -> pd.DataFrame:
    """Coerce identifier columns to string without silent null repair."""
    normalized = df.copy()
    require_columns(normalized, columns, label)
    for column in columns:
        if normalized[column].isna().any():
            raise ValueError(f"{label}.{column} contains null values")
        normalized[column] = normalized[column].astype(str)
    return normalized


def coerce_nullable_text_columns(
    df: pd.DataFrame,
    columns: list[str],
    label: str,
) -> pd.DataFrame:
    """Give nullable text columns a fixed string dtype; missing values stay missing.

    An all-null object column is written to parquet as a null-typed column, which
    readers see as INTEGER. A run with no values then changes the schema that
    consumers pin, even though nothing about the data changed (TM-ACT-025).
    """
    normalized = df.copy()
    require_columns(normalized, columns, label)
    for column in columns:
        present = normalized[column].dropna()
        not_text = present[~present.map(lambda value: isinstance(value, str))]
        if not not_text.empty:
            raise TypeError(
                f"{label}.{column} holds non-text values: {sorted({type(v).__name__ for v in not_text})}"
            )
        normalized[column] = normalized[column].astype("string")
    return normalized


def contiguous_seasons(
    values: pd.Series,
    label: str,
    first: str | None = None,
) -> list[str]:
    """Distinct ``YYYY-YY`` seasons from ``values`` (optionally from ``first`` on), refusing gaps.

    A season missing from the middle would shrink a product without moving its
    first or last season, which is all the drift gate's coverage floor checks.
    Values before ``first`` are outside the window and are not validated.
    """
    seasons = sorted(values.dropna().astype(str).unique())
    if first is not None:
        seasons = [s for s in seasons if s >= first]
    malformed = [
        s for s in seasons
        if len(s) != 7 or s[4] != "-" or not (s[:4] + s[5:]).isdigit()
        or int(s[5:]) != (int(s[:4]) + 1) % 100
    ]
    if malformed:
        raise ValueError(f"{label} has malformed SEASON_ID values: {malformed}")
    if not seasons:
        raise ValueError(f"{label} has no seasons" + (f" from {first}" if first else ""))
    if first is not None and seasons[0] != first:
        raise ValueError(f"{label} starts at {seasons[0]}, not {first}")
    starts = [int(s[:4]) for s in seasons]
    gaps = [f"{a}->{b}" for a, b in zip(starts, starts[1:]) if b != a + 1]
    if gaps:
        raise ValueError(f"{label} seasons are not contiguous ({', '.join(gaps)}): {seasons}")
    return seasons


def seasons_supported_by_inputs(
    seasons: list[str],
    inputs: dict[str, pd.Series],
    label: str,
) -> tuple[list[str], dict[str, list[str]]]:
    """Keep the seasons every required input carries; only trailing seasons may be dropped.

    A season a producer has started (e.g. the scorecard) but a required input has
    not reached yet is dropped and reported, so a partial season is never
    published. A season missing from an input in the middle of the window is an
    input defect, not a rollover, and is refused.
    """
    present = {name: set(series.dropna().astype(str)) for name, series in inputs.items()}
    missing = {s: sorted(name for name, have in present.items() if s not in have) for s in seasons}
    supported = [s for s in seasons if not missing[s]]
    if not supported:
        raise ValueError(f"{label}: no season is carried by every required input: {missing}")
    last = seasons.index(supported[-1])
    interior = {s: missing[s] for s in seasons[: last + 1] if missing[s]}
    if interior:
        raise ValueError(f"{label}: required inputs lack seasons inside the window: {interior}")
    dropped = {s: missing[s] for s in seasons[last + 1 :]}
    return supported, dropped


def coerce_int_columns(
    df: pd.DataFrame,
    columns: list[str],
    label: str,
) -> pd.DataFrame:
    """Coerce numeric identifier columns to int64."""
    normalized = df.copy()
    require_columns(normalized, columns, label)
    for column in columns:
        normalized[column] = pd.to_numeric(
            normalized[column],
            errors="raise",
        ).astype("int64")
    return normalized


def coerce_datetime_columns(
    df: pd.DataFrame,
    columns: list[str],
    label: str,
) -> pd.DataFrame:
    """Coerce date columns to pandas datetime."""
    normalized = df.copy()
    require_columns(normalized, columns, label)
    for column in columns:
        normalized[column] = pd.to_datetime(
            normalized[column],
            errors="raise",
        )
    return normalized


def assert_unique_keys(
    df: pd.DataFrame,
    key_columns: list[str],
    label: str,
) -> pd.DataFrame:
    """Ensure key columns define a unique grain."""
    require_columns(df, key_columns, label)
    duplicates = df.duplicated(subset=key_columns, keep=False)
    if duplicates.any():
        sample = df.loc[duplicates, key_columns].head(10).to_dict("records")
        raise ValueError(f"{label} has duplicate keys for {key_columns}: {sample}")
    return df
