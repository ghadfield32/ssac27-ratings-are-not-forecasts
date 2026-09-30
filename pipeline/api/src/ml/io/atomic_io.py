"""Atomic file writers for shared-volume artifacts.

The Airflow scheduler runs as the ``astro`` user (uid 50000), and every
container that manually writes shared data/cache/gold artifacts must use the
same identity. Historically the datascience container wrote as root, which left
root-owned 0644 files that the scheduler could not overwrite. A direct
``df.to_parquet(path)`` also truncates the existing file in place, which can
fail with ``[Errno 13] Permission denied`` when the existing target was written
by a different user. Writing to a sibling temp file and ``os.replace``-ing it
into the directory keeps publication atomic and sidesteps per-file ownership
entirely: ``os.replace`` only needs write permission on the *directory*, not on
the existing target. See DATA_ENGINEERING_PIPELINE.md §0.9 (cross-container
ownership contract) and PIPELINE_STANDARDS_TEMPLATE.md (shared-volume write
hygiene).

This is the canonical implementation. ``scripts/xfg/_atomic_io.py`` re-exports
from here so there is a single source of truth.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
from pathlib import Path
from typing import Any

import pandas as pd


def _temp_path(target: Path) -> Path:
    return target.with_name(f".{target.name}.{os.getpid()}.tmp")


def _make_group_writable(path: Path) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    path.chmod(mode | 0o660)


def write_parquet_atomic(df: Any, target: Path, **kwargs: Any) -> None:
    """Write a DataFrame or PyArrow table through a sibling temp file, then replace.

    PyArrow tables are accepted so pipeline contracts that embed custom schema
    metadata still use the one governed shared-volume publication boundary.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = _temp_path(target)
    try:
        if isinstance(df, pd.DataFrame):
            df.to_parquet(tmp, **kwargs)
        else:
            import pyarrow as pa
            import pyarrow.parquet as pq

            if not isinstance(df, pa.Table):
                raise TypeError(
                    "write_parquet_atomic expects a pandas DataFrame or pyarrow.Table"
                )
            pq.write_table(df, tmp, **kwargs)
        _make_group_writable(tmp)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()


def write_json_atomic(obj: Any, target: Path, **kwargs: Any) -> None:
    """Write a JSON artifact through a sibling temp file, then replace.

    The JSON analogue of :func:`write_parquet_atomic` — served card/summary
    JSONs land on the same shared volume and hit the identical cross-container
    ownership hazard (root-written datascience container vs astro scheduler).
    ``**kwargs`` are forwarded to :func:`json.dump` (e.g. ``indent``, ``default``).
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = _temp_path(target)
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, **kwargs)
        _make_group_writable(tmp)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()


def copy_file_atomic(source: Path, target: Path) -> None:
    """Copy a completed artifact to a canonical path through atomic replace."""
    source = Path(source)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = _temp_path(target)
    try:
        shutil.copy2(source, tmp)
        _make_group_writable(tmp)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()
