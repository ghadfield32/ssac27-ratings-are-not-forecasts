"""
RAPM Pipeline Orchestrator.

Coordinates the full LA-RAPM pipeline:
  1. Aggregate possessions into stints
  2. Run EDA analysis
  3. Fit per-season RAPM
  4. Fit multi-season pooled RAPM
  5. Validate against BPM
  6. Merge to Gold

Following the injury_pipeline and clustering_pipeline orchestrator patterns.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional

from .config import RapmPipelineConfig
from ..pipeline_contracts import coerce_string_columns
from .stint_aggregator import aggregate_possessions_to_stints
from .la_rapm import (
    fit_single_season_rapm,
    fit_multi_season_rapm,
    fit_multi_season_od_rapm,
)
from .eda.rapm_eda import run_stint_eda, save_eda_report


class RapmPipeline:
    """Orchestrator for the LA-RAPM pipeline."""

    def __init__(self, config: RapmPipelineConfig = None):
        self.config = config or RapmPipelineConfig()
        self._stints_by_season: Dict[str, pd.DataFrame] = {}

    @staticmethod
    def _normalize_merge_keys(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize merge keys so parquet-inferred dtypes do not break joins.

        Gold player_season_features uses SEASON_ID; RAPM outputs use SEASON.
        If SEASON is absent but SEASON_ID is present, add a transient SEASON
        alias so merge_to_gold / validate can join on ["PLAYER_ID", "SEASON"].
        The persisted Gold contract remains SEASON_ID-only.
        """
        df = df.copy()
        if "SEASON" not in df.columns and "SEASON_ID" in df.columns:
            df["SEASON"] = df["SEASON_ID"]
        key_columns = [c for c in ["PLAYER_ID", "SEASON"] if c in df.columns]
        if not key_columns:
            return df
        return coerce_string_columns(df, key_columns, "RAPM merge frame")

    def load_possessions(self, season: str = None) -> pd.DataFrame:
        """Load possessions data.

        Parameters
        ----------
        season : str, optional
            If provided, load per-season file first, else fall back to combined.

        Returns
        -------
        pd.DataFrame
        """
        if season:
            per_season_dir = self.config.possessions_by_season_dir
            per_season_file = per_season_dir / f"{season}.parquet"
            if per_season_file.exists():
                poss = pd.read_parquet(per_season_file)
                print(f"Loaded {len(poss):,} possessions for {season}")
                return poss
            raise FileNotFoundError(
                f"Per-season possessions not found for {season}: {per_season_file}"
            )

        path = self.config.possessions_path
        assert path.exists(), f"Possessions not found: {path}. Run process_all_pbp_seasons.py first."
        poss = pd.read_parquet(path)
        print(f"Loaded {len(poss):,} possessions from {path}")
        return poss

    def load_rotation_stints(self, season: str = None) -> pd.DataFrame:
        """Load game rotation stint data.

        Parameters
        ----------
        season : str, optional
            If provided, filter to this season.

        Returns
        -------
        pd.DataFrame
        """
        path = self.config.rotation_stints_path
        assert path.exists(), f"Rotation stints not found: {path}"
        stints = pd.read_parquet(path)
        if season:
            stints = stints[stints["SEASON"] == season]
        print(f"Loaded {len(stints):,} rotation stints" + (f" for {season}" if season else ""))
        return stints

    def aggregate_stints(self, season: str = None) -> pd.DataFrame:
        """Aggregate possessions into stints and save.

        Parameters
        ----------
        season : str, optional
            Season to process.

        Returns
        -------
        pd.DataFrame of stints.
        """
        poss = self.load_possessions(season)
        rotation = self.load_rotation_stints(season)

        stints = aggregate_possessions_to_stints(
            poss, rotation, self.config, season=season
        )

        if len(stints) > 0:
            # Save to Silver
            output = self.config.stints_output_path
            output.parent.mkdir(parents=True, exist_ok=True)
            stints.to_parquet(output, index=False)
            print(f"Saved {len(stints):,} stints to {output}")

            self._stints_by_season[season or "latest"] = stints

        return stints

    def load_stints(
        self,
        season: str = None,
        luck_adjusted: bool = False,
        prior_mode: str = "date_censored",
    ) -> pd.DataFrame:
        """Load previously saved stints.

        Parameters
        ----------
        season : str, optional
            Season to load.
        luck_adjusted : bool
            If True, require luck-adjusted LA stints for the requested prior mode.
        prior_mode : {"lagged", "same_season"}
            Which luck-adjusted stint artifact family to load.

        Returns
        -------
        pd.DataFrame
        """
        # Cache key includes luck_adjusted flag
        cache_key = f"{season}_la_{prior_mode}" if luck_adjusted else season
        if cache_key and cache_key in self._stints_by_season:
            return self._stints_by_season[cache_key]

        if luck_adjusted:
            la_dir = self.config.la_stints_dir(prior_mode)
            if season and la_dir.exists():
                la_file = la_dir / f"{season}.parquet"
                if la_file.exists():
                    stints = pd.read_parquet(la_file)
                    print(
                        f"Loaded {len(stints):,} LA stints for {season} "
                        f"from {la_file.name}"
                    )
                    self._stints_by_season[cache_key] = stints
                    return stints
            raise FileNotFoundError(
                f"Luck-adjusted stints not found for season={season}, "
                f"prior_mode={prior_mode}. Expected file in {la_dir}."
            )

        per_season_dir = self.config.stints_by_season_dir
        if season and per_season_dir.exists():
            per_season_file = per_season_dir / f"{season}.parquet"
            if per_season_file.exists():
                stints = pd.read_parquet(per_season_file)
                print(
                    f"Loaded {len(stints):,} stints for {season} "
                    f"from {per_season_file.name}"
                )
                self._stints_by_season[cache_key or season] = stints
                return stints
            raise FileNotFoundError(
                f"Per-season stints not found for {season}: {per_season_file}"
            )

        path = self.config.stints_output_path
        if season is None and path.exists():
            stints = pd.read_parquet(path)
            print(f"Loaded {len(stints):,} stints from {path}")
            return stints

        raise FileNotFoundError(
            f"No stints found for {season or 'any season'}. "
            f"Run process_all_pbp_seasons.py first."
        )

    def run_eda(self, season: str = None) -> dict:
        """Run EDA analysis on stint data.

        Parameters
        ----------
        season : str, optional
            Season to analyze.

        Returns
        -------
        dict with EDA results.
        """
        stints = self.load_stints(season)
        results = run_stint_eda(stints, self.config, season=season)

        # Save report
        output_dir = self.config.eda_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        save_eda_report(results, output_dir / f"rapm_eda_{season or 'latest'}.json")

        return results

    def fit_per_season(self, seasons: List[str] = None) -> Dict[str, pd.DataFrame]:
        """Fit RAPM per season and cache results.

        Parameters
        ----------
        seasons : list of str, optional
            Seasons to fit. Defaults to available_seasons.

        Returns
        -------
        Dict mapping season -> RAPM results DataFrame.
        """
        if seasons is None:
            seasons = self.config.available_seasons

        output_dir = self.config.rapm_by_season_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {}
        for season in seasons:
            print(f"\n{'='*60}")
            print(f"Fitting RAPM for {season}")
            print(f"{'='*60}")

            try:
                stints = self.load_stints(season)
            except FileNotFoundError:
                print(f"  SKIP: No stints for {season}")
                continue

            if len(stints) == 0:
                print(f"  SKIP: Empty stints for {season}")
                continue

            rapm_df = fit_single_season_rapm(stints, self.config)
            rapm_df["SEASON"] = season

            # Save per-season
            rapm_df.to_parquet(output_dir / f"{season}.parquet", index=False)
            results[season] = rapm_df
            print(f"  Saved {len(rapm_df)} player RAPM estimates for {season}")

        return results

    def fit_multi_season(self, target_season: str = None) -> pd.DataFrame:
        """Fit multi-season pooled RAPM.

        Parameters
        ----------
        target_season : str, optional
            Anchor season. Defaults to latest available.

        Returns
        -------
        pd.DataFrame with multi-season RAPM estimates.
        """
        # Determine seasons to pool
        if target_season is None:
            target_season = self.config.available_seasons[-1]

        seasons = sorted(self.config.available_seasons)
        target_idx = seasons.index(target_season) if target_season in seasons else len(seasons) - 1
        start_idx = max(0, target_idx - self.config.seasons_back + 1)
        pool_seasons = seasons[start_idx:target_idx + 1]

        print(f"\n{'='*60}")
        print(f"Multi-season RAPM: pooling {pool_seasons}")
        print(f"{'='*60}")

        # Load stints for each season
        season_stints = {}
        for season in pool_seasons:
            try:
                stints = self.load_stints(season)
                if len(stints) > 0:
                    season_stints[season] = stints
            except FileNotFoundError:
                print(f"  No stints for {season}, skipping")

        if len(season_stints) == 0:
            print("ERROR: No season stints available for multi-season fit")
            return pd.DataFrame()

        rapm_df = fit_multi_season_rapm(season_stints, target_season, self.config)

        # Save
        output = self.config.rapm_multi_season_path
        output.parent.mkdir(parents=True, exist_ok=True)
        rapm_df.to_parquet(output, index=False)
        print(f"Saved {len(rapm_df)} multi-season RAPM estimates to {output}")

        return rapm_df

    def fit_multi_season_od(
        self,
        target_season: str = None,
        luck_adjusted: bool = True,
        prior_mode: str = "date_censored",
    ) -> pd.DataFrame:
        """Fit multi-season offensive/defensive RAPM split.

        Produces RAPM_OFFENSE and RAPM_DEFENSE in addition to RAPM_NET.
        By default uses luck-adjusted stints (rapm_stints_la_by_season) so
        that shooting variance is removed before fitting.

        Parameters
        ----------
        target_season : str, optional
            Anchor season. Defaults to latest available.
        luck_adjusted : bool
            If True, load LA stints (luck-adjusted). Default True.
        prior_mode : {"lagged", "same_season"}
            Which luck-adjusted stint artifact family to load.

        Returns
        -------
        pd.DataFrame with PLAYER_ID, SEASON, RAPM_OFFENSE, RAPM_DEFENSE,
        RAPM_NET, N_STINTS, TOTAL_POSS
        """
        if target_season is None:
            target_season = self.config.available_seasons[-1]

        seasons = sorted(self.config.available_seasons)
        if target_season in seasons:
            target_idx = seasons.index(target_season)
        else:
            target_idx = len(seasons) - 1
        start_idx = max(0, target_idx - self.config.seasons_back + 1)
        pool_seasons = seasons[start_idx:target_idx + 1]

        print(f"\n{'='*60}")
        print(f"Multi-season OD RAPM: pooling {pool_seasons}")
        la_label = " (luck-adjusted)" if luck_adjusted else " (raw)"
        print(f"Stints source: {la_label}")
        print(f"{'='*60}")

        season_stints = {}
        for season in pool_seasons:
            try:
                if luck_adjusted:
                    stints = self.load_stints(
                        season,
                        luck_adjusted=True,
                        prior_mode=prior_mode,
                    )
                else:
                    stints = self.load_stints(season, luck_adjusted=False)
                if len(stints) > 0:
                    season_stints[season] = stints
            except FileNotFoundError:
                print(f"  No stints for {season}, skipping")

        if len(season_stints) == 0:
            print(f"  No luck-adjusted stints for {target_season} pool — skipping OD fit")
            return pd.DataFrame()


        rapm_od = fit_multi_season_od_rapm(
            season_stints, target_season, self.config
        )

        output = self.config.rapm_od_path_for_mode(prior_mode)
        output.parent.mkdir(parents=True, exist_ok=True)
        rapm_od.to_parquet(output, index=False)
        print(f"Saved {len(rapm_od):,} OD RAPM estimates to {output}")

        return rapm_od

    def validate(self, rapm_df: pd.DataFrame) -> dict:
        """Validate RAPM estimates against BPM.

        Parameters
        ----------
        rapm_df : pd.DataFrame
            RAPM results with PLAYER_ID, SEASON, RAPM_NET.

        Returns
        -------
        dict with validation results.
        """
        print(f"\n{'='*60}")
        print("RAPM VALIDATION")
        print(f"{'='*60}")

        # Load Gold for BPM comparison
        gold_path = self.config.gold_psf_path
        assert gold_path.exists(), f"Gold PSF not found: {gold_path}"
        gold = self._normalize_merge_keys(pd.read_parquet(gold_path))
        rapm_df = self._normalize_merge_keys(rapm_df)

        # Merge RAPM with Gold
        if "SEASON" in rapm_df.columns:
            merged = gold.merge(
                rapm_df[["PLAYER_ID", "SEASON", "RAPM_NET"]].rename(columns={"RAPM_NET": "LA_RAPM_NET"}),
                on=["PLAYER_ID", "SEASON"],
                how="inner",
            )
        else:
            merged = gold.merge(
                rapm_df[["PLAYER_ID", "RAPM_NET"]].rename(columns={"RAPM_NET": "LA_RAPM_NET"}),
                on="PLAYER_ID",
                how="inner",
            )

        print(f"Merged: {len(merged):,} player-seasons")

        results = {"n_merged": len(merged)}

        # Correlation with BPM for high-minute players
        for min_mp in [500, 1000, 1500, 2000]:
            mask = (merged["MP"] >= min_mp) & merged["BPM_BBREF"].notna() & merged["LA_RAPM_NET"].notna()
            n = mask.sum()
            if n > 10:
                r = np.corrcoef(merged.loc[mask, "LA_RAPM_NET"], merged.loc[mask, "BPM_BBREF"])[0, 1]
                results[f"bpm_corr_mp{min_mp}"] = {"r": round(float(r), 4), "n": int(n)}
                status = "PASS" if r >= self.config.min_bpm_correlation else "FAIL"
                print(f"  corr(RAPM_NET, BPM_BBREF) for MP>={min_mp}: r={r:.3f} (n={n}) [{status}]")
            else:
                print(f"  corr(RAPM_NET, BPM_BBREF) for MP>={min_mp}: insufficient data (n={n})")

        # Top/bottom sanity
        if "PLAYER_NAME" in merged.columns:
            top10 = merged.nlargest(10, "LA_RAPM_NET")[["PLAYER_NAME", "SEASON", "LA_RAPM_NET", "BPM_BBREF"]]
            bot10 = merged.nsmallest(10, "LA_RAPM_NET")[["PLAYER_NAME", "SEASON", "LA_RAPM_NET", "BPM_BBREF"]]

            print(f"\nTop 10 RAPM:")
            for _, row in top10.iterrows():
                name = str(row["PLAYER_NAME"]) if pd.notna(row["PLAYER_NAME"]) else "?"
                bpm = f"{row['BPM_BBREF']:.1f}" if pd.notna(row["BPM_BBREF"]) else "N/A"
                print(f"  {name:25s} {row.get('SEASON',''):8s} RAPM={row['LA_RAPM_NET']:6.2f}  BPM={bpm}")

            print(f"\nBottom 10 RAPM:")
            for _, row in bot10.iterrows():
                name = str(row["PLAYER_NAME"]) if pd.notna(row["PLAYER_NAME"]) else "?"
                bpm = f"{row['BPM_BBREF']:.1f}" if pd.notna(row["BPM_BBREF"]) else "N/A"
                print(f"  {name:25s} {row.get('SEASON',''):8s} RAPM={row['LA_RAPM_NET']:6.2f}  BPM={bpm}")

        # Coverage check
        coverage_pct = len(merged) / max(len(gold), 1)
        results["coverage_pct"] = round(float(coverage_pct), 4)
        print(f"\nCoverage: {len(merged):,} / {len(gold):,} ({coverage_pct:.1%})")

        # Overall pass/fail
        corr_2000 = results.get("bpm_corr_mp2000", {}).get("r", 0)
        results["overall_pass"] = corr_2000 >= self.config.min_bpm_correlation
        print(f"\nOverall: {'PASS' if results['overall_pass'] else 'FAIL'} (r={corr_2000:.3f} vs threshold {self.config.min_bpm_correlation})")

        return results

    def merge_to_gold(self, rapm_df: pd.DataFrame) -> None:
        """Merge RAPM estimates into Gold player_season_features.

        Fixes the old merge bug: joins on [PLAYER_ID, SEASON] not just PLAYER_ID.

        Parameters
        ----------
        rapm_df : pd.DataFrame
            RAPM results with PLAYER_ID, SEASON, RAPM_NET (and optionally RAPM_OFFENSE, RAPM_DEFENSE).
        """
        gold_path = self.config.gold_psf_path
        assert gold_path.exists(), f"Gold PSF not found: {gold_path}"
        gold_raw = pd.read_parquet(gold_path)
        gold_had_season_id = "SEASON_ID" in gold_raw.columns
        gold = self._normalize_merge_keys(gold_raw)
        rapm_df = self._normalize_merge_keys(rapm_df)

        print(f"\n{'='*60}")
        print("MERGE RAPM TO GOLD")
        print(f"{'='*60}")
        print(f"Gold: {len(gold):,} rows, {len(gold.columns)} columns")

        # Drop all existing RAPM-related columns to avoid _x/_y conflicts
        # Session 426: Also drop _x/_y collision artifacts from prior double-merges
        drop_candidates = (
            [c for c in gold.columns if c.startswith("RAPM_")]
            + [c for c in gold.columns if c in ("N_STINTS", "TOTAL_POSS")]
            + [c for c in gold.columns if c.startswith("N_STINTS_") or c.startswith("TOTAL_POSS_")]
        )
        if drop_candidates:
            print(f"Dropping existing RAPM columns: {drop_candidates}")
            gold = gold.drop(columns=drop_candidates)

        # Determine merge columns
        merge_cols = ["PLAYER_ID", "RAPM_NET"]
        if "RAPM_OFFENSE" in rapm_df.columns:
            merge_cols.extend(["RAPM_OFFENSE", "RAPM_DEFENSE"])
        if "N_STINTS" in rapm_df.columns:
            merge_cols.append("N_STINTS")
        if "TOTAL_POSS" in rapm_df.columns:
            merge_cols.append("TOTAL_POSS")

        # Merge on [PLAYER_ID, SEASON] only. A PLAYER_ID-only merge copies one
        # season's rating onto every season of that player, so it is refused.
        if "SEASON" not in rapm_df.columns:
            raise ValueError(
                "merge_to_gold requires a SEASON column on rapm_df; a PLAYER_ID-only "
                "merge would broadcast one season's RAPM across all seasons."
            )
        merge_cols.append("SEASON")
        gold_updated = gold.merge(
            rapm_df[merge_cols],
            on=["PLAYER_ID", "SEASON"],
            how="left",
            validate="many_to_one",
        )

        # Coverage report
        rapm_coverage = gold_updated["RAPM_NET"].notna().sum()
        rapm_pct = rapm_coverage / max(len(gold_updated), 1)

        print(f"RAPM coverage: {rapm_coverage:,} / {len(gold_updated):,} ({rapm_pct:.1%})")
        print(f"Columns: {len(gold.columns)} -> {len(gold_updated.columns)}")

        if gold_had_season_id:
            gold_updated["SEASON_ID"] = gold_updated["SEASON"]
            gold_updated = gold_updated.drop(columns=["SEASON"])

        # Save
        gold_updated.to_parquet(gold_path, index=False)
        print(f"Saved updated Gold to {gold_path}")
