"""Protect the common career ruler and equal-opportunity nearest-other comparison."""

from copy import deepcopy
from math import log1p

import pytest

from avalanche_career_comps import distinctiveness, makar_compact, makar_deep_dive


def fixture(target_value=12):
    def profile(pid, name, value):
        games = 100 + 50 * value
        features = dict.fromkeys(makar_compact.FEATURE_LABELS, float(value))
        features["log_games"] = log1p(games)
        return {"player_id": pid, "name": name, "features": features, "games": games}

    target = profile(makar_compact.TARGET, "Cale Makar", target_value)
    peers = [
        profile(makar_deep_dive.BARRIE, "Tyson Barrie", 1),
        profile(makar_deep_dive.BOURQUE, "Ray Bourque", 5),
        profile(makar_deep_dive.OZOLINSH, "Sandis Ozolinsh", 2),
        profile(makar_deep_dive.LILES, "John-Michael Liles", 3),
        profile(9, "Other alumnus", 4),
    ]
    case = distinctiveness.neighbour_audit(
        target, peers, dict.fromkeys(makar_compact.FEATURE_LABELS, 1)
    )
    source = {
        "cutoff": "2025–26",
        "primary_tenure": 82,
        "windows": {
            "whole_career": {
                "cases": {"all_alumni_without_pk": case},
                "comparisons": [target, *peers],
            }
        },
    }
    article = {
        "config": {"min_avs_skater_games": 82},
        "rows": [
            {
                "window": "whole_career",
                "player_id": makar_compact.TARGET,
                "candidate_ids": [p["player_id"] for p in peers],
                "ranked_candidate_ids": [makar_deep_dive.BARRIE, makar_deep_dive.LILES],
                "matches": [{"name": "Tyson Barrie"}],
            }
        ],
    }
    return source, article


def test_compact_analysis_is_career_only_and_preserves_source_models():
    source, article = fixture()
    original = deepcopy((source, article))
    report = makar_compact.consolidate(source, article)
    assert (source, article) == original
    assert report["window"] == "whole_career" and "windows" not in report
    assert [p["player_id"] for p in report["profiles"]] == list(makar_compact.DISPLAY_IDS)
    assert set(report["feature_order"]) == set(makar_compact.FEATURE_LABELS)
    assert "pk_minutes_per_game" not in report["feature_order"]
    assert report["roster_rankings_changed"] is False
    for player in report["profiles"]:
        for key in report["feature_order"]:
            expected = (player["features"][key] - report["candidate_means"][key]) / report[
                "scales"
            ][key]
            assert player["z_scores"][key] == pytest.approx(expected)
            assert report["radial_bounds"][0] <= expected <= report["radial_bounds"][1]


def test_every_player_has_equal_match_opportunities_and_no_self_match():
    source, article = fixture()
    report = makar_compact.consolidate(source, article)
    scores = report["isolation"]
    assert scores["neighbour_universe_count"] == 6
    assert scores["possible_matches_per_player"] == 5
    assert scores["historical_gaps_changed_by_adding_target"] is False
    for row in [*scores["rows"], *scores["historical_reference"]]:
        assert row["player_id"] != row["nearest_id"]
    assert (
        scores["typical_gap"]
        == source["windows"]["whole_career"]["cases"]["all_alumni_without_pk"]["reference_median"]
    )


def test_changed_historical_neighbours_require_review_instead_of_a_silent_new_benchmark():
    source, article = fixture(target_value=5.05)
    with pytest.raises(ValueError, match="historical nearest match"):
        makar_compact.consolidate(source, article)


@pytest.mark.parametrize("change", ["cohort", "pk", "tenure", "missing_player"])
def test_compact_comparison_rejects_inconsistent_pools_or_incomplete_shared_features(change):
    source, article = fixture()
    case = source["windows"]["whole_career"]["cases"]["all_alumni_without_pk"]
    if change == "cohort":
        article["rows"][0]["candidate_ids"].pop()
    elif change == "pk":
        case["weights"]["pk_minutes_per_game"] = 0.1
    elif change == "tenure":
        article["config"]["min_avs_skater_games"] = 100
    else:
        data = source["windows"]["whole_career"]
        data["comparisons"] = [
            p for p in data["comparisons"] if p["player_id"] != makar_deep_dive.LILES
        ]
    with pytest.raises(ValueError):
        makar_compact.consolidate(source, article)
