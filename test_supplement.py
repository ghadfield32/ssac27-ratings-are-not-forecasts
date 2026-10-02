import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location("pmi_supplement", Path(__file__).with_name("supplement_analysis.py"))
if SPEC.loader is None:
    raise RuntimeError("supplement loader unavailable")
MODULE = importlib.util.module_from_spec(SPEC)


@pytest.fixture
def supplement():
    assert Path(SPEC.origin).is_file(), "offline supplement has not been implemented"
    SPEC.loader.exec_module(MODULE)
    return MODULE


@pytest.fixture
def package(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    frame = pd.DataFrame({
        "EVAL_ORDER": range(8), "GAME_ID": [f"002{22 if i < 4 else 23}{i:05d}" for i in range(8)],
        "SEASON": ["2022-23"] * 4 + ["2023-24"] * 4,
        "GAME_DATE": [f"2022-10-{i:02d}" for i in range(1, 5)] + [f"2023-10-{i:02d}" for i in range(1, 5)],
        "PHASE": ["development"] * 4 + ["holdout"] * 4,
        "MATCHED": [True] * 8, "ACTUAL": np.arange(8, dtype=float),
        "EARLY_SEASON": [False] * 8, "ROOKIE_HEAVY": [False] * 8, "TEAM_CHANGE": [False] * 8,
    })
    models = ("pregame_v1", "B0_home_only", "B1_prev_v2", "B2_prev_incumbent")
    params = {}
    for model in models:
        frame[f"PLAYER_PART_{model}"] = np.arange(8, dtype=float)
        params[model] = {"h": 0, "q10": -1, "q90": 1, "n_development_games": 4}
    frame.to_csv(data / "pmi_games_track_b.csv", index=False)
    (data / "frozen_parameters.json").write_text(json.dumps({"track_b": params}), encoding="utf-8")
    return tmp_path


def test_missing_matched_prediction_refuses(supplement, package):
    path = package / "data/pmi_games_track_b.csv"
    frame = pd.read_csv(path, dtype={"GAME_ID": str})
    frame.loc[7, "PLAYER_PART_pregame_v1"] = np.nan
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="finite"):
        supplement.load_track(package, "track_b")


def test_duplicate_game_refuses(supplement, package):
    path = package / "data/pmi_games_track_b.csv"
    frame = pd.read_csv(path, dtype={"GAME_ID": str})
    frame.loc[7, "GAME_ID"] = frame.loc[6, "GAME_ID"]
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="unique"):
        supplement.load_track(package, "track_b")


def test_temporal_overlap_refuses(supplement, package):
    path = package / "data/pmi_games_track_b.csv"
    frame = pd.read_csv(path, dtype={"GAME_ID": str})
    frame.loc[0, "GAME_DATE"] = "2024-01-01"
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="precede"):
        supplement.load_track(package, "track_b")


def test_unmatched_missing_prediction_remains_missing_and_inputs_unchanged(supplement, package):
    path = package / "data/pmi_games_track_b.csv"
    frame = pd.read_csv(path, dtype={"GAME_ID": str})
    frame.loc[7, "MATCHED"] = False
    frame.loc[7, "PLAYER_PART_pregame_v1"] = np.nan
    frame.to_csv(path, index=False)
    before = path.read_bytes()
    loaded, _ = supplement.load_track(package, "track_b")
    assert np.isnan(loaded.loc[7, "PLAYER_PART_pregame_v1"])
    assert path.read_bytes() == before


def test_interval_score_penalties_are_hand_calculable(supplement):
    result = supplement.interval_metrics(np.array([-2., 0., 2.]), np.zeros(3), -1., 1.)
    assert result["interval_score_80"] == pytest.approx(26 / 3)
    assert result["coverage_80"] == pytest.approx(1 / 3)
    assert result["mean_interval_width"] == 2
    assert result["below_interval_fraction"] == pytest.approx(1 / 3)
    assert result["above_interval_fraction"] == pytest.approx(1 / 3)


def test_rescaling_coefficients_do_not_see_holdout_labels(supplement):
    x = np.array([0., 1., 2., 3.])
    a, b = supplement.fit_development_scale(x, 2 * x + 3)
    assert a == pytest.approx(3)
    assert b == pytest.approx(2)
    # The API accepts development arrays only; applying it takes no evaluation labels.
    prediction = a + b * np.array([4., 5.])
    assert prediction.tolist() == pytest.approx([11, 13])


def test_calendar_bootstrap_keeps_pairing_and_seasons(supplement):
    dates = pd.to_datetime(["2023-10-02", "2023-10-10", "2024-10-01", "2024-10-08"])
    seasons = np.array(["2023-24", "2023-24", "2024-25", "2024-25"])
    sq = np.array([[1., 1.], [4., 4.], [9., 9.], [16., 16.]])
    draws, counts = supplement.calendar_mse_draws(sq, dates, seasons, 7, 50, 123)
    assert counts == {"2023-24": 2, "2024-25": 2}
    assert np.array_equal(draws[:, 0], draws[:, 1])
    repeated, _ = supplement.calendar_mse_draws(sq, dates, seasons, 7, 50, 123)
    assert np.array_equal(draws, repeated)
    assert np.isfinite(draws).all()


def test_invalid_intervals_and_nonfinite_losses_refuse(supplement):
    with pytest.raises(ValueError):
        supplement.interval_metrics(np.array([0.]), np.array([0.]), 1., -1.)
    with pytest.raises(ValueError):
        supplement.calendar_mse_draws(np.array([[np.nan]]), pd.to_datetime(["2023-10-02"]), np.array(["2023-24"]), 7, 10, 1)


@pytest.mark.parametrize("column,row,value", [
    ("SEASON", 0, None),
    ("SEASON", 7, "2023-99"),
    ("SEASON", 7, "2025-26"),
    ("GAME_DATE", 7, "2030-01-01"),
    ("GAME_ID", 7, "0029909999"),
])
def test_corrupt_season_identity_and_dates_refuse(supplement, package, column, row, value):
    path = package / "data/pmi_games_track_b.csv"
    frame = pd.read_csv(path, dtype={"GAME_ID": str})
    frame.loc[row, column] = value
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError):
        supplement.load_track(package, "track_b")


def test_main_refuses_nonbound_snapshot_before_writing(supplement, package, tmp_path, monkeypatch):
    (package / "data/pmi_games_track_a.csv").write_bytes((package / "data/pmi_games_track_b.csv").read_bytes())
    params_path = package / "data/frozen_parameters.json"
    params = json.loads(params_path.read_text(encoding="utf-8"))
    params["track_a"] = params["track_b"]
    params_path.write_text(json.dumps(params), encoding="utf-8")
    (package / "data/expected.json").write_text("{}", encoding="utf-8")
    output = tmp_path / "results"
    monkeypatch.setattr(sys, "argv", ["supplement_analysis.py", "--package", str(package), "--output", str(output)])
    with pytest.raises(RuntimeError, match="binding"):
        supplement.main()
    assert not output.exists()
