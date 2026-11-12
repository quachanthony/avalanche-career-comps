"""Protect article-chart coordinates and goalie display units."""

from copy import deepcopy
from math import sqrt

import pytest

from avalanche_career_comps import lineup_radar
from avalanche_career_comps.article_radar import (
    ARTICLE_NOTE,
    article_note,
    chart_data,
    coverage_text,
    image_stem,
    value_formatter,
    write_gallery,
)


def row(window="whole_career"):
    return {
        "window": window,
        "player_id": 7,
        "name": "Current Skater",
        "position": "F",
        "age": 27,
        "games": 100,
        "candidate_ids": [1, 2],
        "ranked_candidate_ids": [1, 2],
        "pk_status": "pk_below_minimum",
        "weights": {"goals_per_82": 0.5, "assists_per_82": 0.5},
        "target_features": {"goals_per_82": 2, "assists_per_82": 4},
        "candidate_means": {"goals_per_82": 0, "assists_per_82": 0},
        "scales": {"goals_per_82": 1, "assists_per_82": 1},
        "matches": [
            {
                "name": "Alumnus",
                "player_id": 1,
                "distance": sqrt(2.5),
                "features": {"goals_per_82": 1, "assists_per_82": 2},
                "games": 200,
                "last_age": 27,
            }
        ],
    }


def test_article_charts_keep_windows_separate_and_reconcile_the_saved_distance():
    report = {"rows": [row(), row("age_aligned")]}
    original = deepcopy(report)
    charts = chart_data(report)
    assert [chart["window"] for chart in charts] == ["whole_career", "age_aligned"]
    assert charts[0]["distance"] == pytest.approx(sqrt(2.5))
    assert charts[0]["axes"][0]["current_raw"] == 2
    assert report == original
    report["rows"][0]["matches"][0]["distance"] = 0
    with pytest.raises(ValueError, match="do not reconcile"):
        chart_data(report)


def test_article_charts_reject_duplicate_windows_and_withdrawn_hits_model():
    with pytest.raises(ValueError, match="Duplicate"):
        chart_data({"rows": [row(), row()]})
    modified = row()
    modified["weights"]["hits_per_game"] = 0.1
    with pytest.raises(ValueError, match="excludes hits"):
        chart_data({"rows": [modified]})


@pytest.mark.parametrize("raw,display", [(0.0032, "+0.32"), (-0.0007, "-0.07"), (0, "+0.00")])
def test_goalie_save_rate_gap_is_formatted_in_percentage_points_without_mutation(raw, display):
    axis = {"key": "relative_save_percentage", "current_raw": raw}
    assert value_formatter(axis, "current", {}) == display
    assert axis["current_raw"] == raw


def test_article_filename_keeps_stable_identity_and_readable_name():
    assert image_stem(7, "José O'Connor") == "7-jose-o-connor"


def test_separate_galleries_link_their_existing_window_csv(tmp_path):
    results = tmp_path / "model" / "results.json"
    results.parent.mkdir()
    results.write_text("{}")
    for window in ("whole_career", "age_aligned"):
        results.with_name(f"{window}-matches.csv").write_text("player,match\n")
    out = tmp_path / "web"
    for directory in ("full-career", "age-adjusted"):
        (out / directory).mkdir(parents=True)
    report = {"rows": [row(), row("age_aligned")]}
    write_gallery(report, chart_data(report), out, results)
    assert "whole_career-matches.csv" in (out / "full-career/index.html").read_text()
    assert "age_aligned-matches.csv" in (out / "age-adjusted/index.html").read_text()


def test_weak_comparison_limits_remain_visible_outside_the_image():
    data = chart_data({"rows": [row()]})[0]
    data["quality_flags"] = ["small_comparison_pool", "distant_analogue"]
    text = coverage_text(data)
    assert "No strong analogue" in text
    assert "only 2 eligible alumni" in text
    assert "distant match" in text


@pytest.mark.parametrize(
    "feature",
    ["quality_starts_above_league_per_100_starts", "era_relative_shutouts_per_100_starts"],
)
@pytest.mark.parametrize("raw,display", [(0.842, "+0.84"), (-1.25, "-1.25"), (0, "+0.00")])
def test_goalie_per_100_start_differences_are_not_multiplied_by_100_again(feature, raw, display):
    axis = {"key": feature, "historical_raw": raw}
    original = deepcopy(axis)
    assert value_formatter(axis, "historical", {}) == display
    assert axis == original


def test_goalie_performance_chart_reconciles_distance_and_preserves_context_independently():
    goalie = row()
    goalie.update(
        position="G",
        pk_status="not_applicable_goalie",
        weights={
            "relative_save_percentage": 0.25,
            "adjusted_shots_per_game": 0.25,
            "quality_starts_above_league_per_100_starts": 0.25,
            "era_relative_shutouts_per_100_starts": 0.25,
        },
        target_features={
            "relative_save_percentage": 0.003,
            "adjusted_shots_per_game": 30,
            "quality_starts_above_league_per_100_starts": 2,
            "era_relative_shutouts_per_100_starts": 1,
        },
        candidate_means={
            "relative_save_percentage": 0,
            "adjusted_shots_per_game": 20,
            "quality_starts_above_league_per_100_starts": 0,
            "era_relative_shutouts_per_100_starts": 0,
        },
        scales={
            "relative_save_percentage": 0.001,
            "adjusted_shots_per_game": 5,
            "quality_starts_above_league_per_100_starts": 2,
            "era_relative_shutouts_per_100_starts": 1,
        },
        goalie_context={"games": 100, "starts": 90, "quality_starts": 50, "shutouts": 5},
    )
    goalie["matches"][0].update(
        features={
            "relative_save_percentage": 0.002,
            "adjusted_shots_per_game": 25,
            "quality_starts_above_league_per_100_starts": 1,
            "era_relative_shutouts_per_100_starts": 0.5,
        },
        distance=sqrt(0.625),
        goalie_context={"games": 200, "starts": 180, "quality_starts": 100, "shutouts": 10},
    )
    original = deepcopy(goalie)
    chart = chart_data({"rows": [goalie]})[0]
    assert chart["goalie_performance"] is True
    assert chart["distance"] == pytest.approx(sqrt(0.625))
    assert "log_games" not in [axis["key"] for axis in chart["axes"]]
    assert "appearances are context only" in coverage_text(chart)
    chart["goalie_context"]["games"] = 7
    chart["historical_goalie_context"]["starts"] = 8
    assert goalie == original


def test_notes_follow_selected_goalie_method_and_keep_legacy_reports_reproducible():
    legacy = {"rows": []}
    performance = {"rows": [], "goalie_method": {"name": "performance"}}
    assert article_note(legacy) == ARTICLE_NOTE + "\n"
    assert lineup_radar.article_note(legacy) == lineup_radar.NOTE + "\n"
    for note in (article_note(performance), lineup_radar.article_note(performance)):
        assert "QS+" in note and "SO+" in note
        assert "excess quality starts and shutouts per 100 starts" in note
        assert "fixed .900" in note
        assert "Apps/82" not in note
        assert "appearances per 82-game season" not in note
        assert "sample sizes" in note
