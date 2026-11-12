"""Keep the Makar diagnostic tied to the actual article pool and statistical ruler."""

from copy import deepcopy

import pytest

from avalanche_career_comps import distinctiveness, makar_deep_dive


@pytest.mark.parametrize("threshold,expected", [(82, [2, 3]), (100, [])])
def test_primary_pool_uses_selected_article_threshold_and_preserves_inputs(threshold, expected):
    available = [
        {"player_id": 1, "avs_games": 81},
        {"player_id": 2, "avs_games": 82},
        {"player_id": 3, "avs_games": 94},
    ]
    frozen_config = {"min_avs_skater_games": 100, "min_avs_goalie_games": 50}
    article = {"config": {**frozen_config, "min_avs_skater_games": threshold}}
    original = deepcopy(available)
    tenure, pool = makar_deep_dive.primary_pool(available, article)
    assert tenure == threshold
    assert [p["player_id"] for p in pool] == expected
    assert available == original
    assert frozen_config == {"min_avs_skater_games": 100, "min_avs_goalie_games": 50}


@pytest.mark.parametrize("invalid", [0, -1, True, 82.0, "82"])
def test_primary_pool_rejects_invalid_threshold(invalid):
    with pytest.raises(ValueError, match="positive integer"):
        makar_deep_dive.primary_pool([], {"config": {"min_avs_skater_games": invalid}})


def test_article_narrative_uses_actual_winners_counts_and_signed_rate_differences():
    case = {
        "closest_match": {"player_id": 2, "name": "Article Defender"},
        "reference_count": 25,
        "ratio_to_median": 3.2,
    }
    broad = {
        "closest_match": {"player_id": 3, "name": "Ray Bourque"},
        "reference_count": 40,
        "ratio_to_median": 1.7,
    }
    report = {
        "primary_tenure": 82,
        "windows": {
            "age_aligned": {
                "age": 27,
                "cases": {
                    "article": case,
                    "all_alumni_without_pk": broad,
                    "covered_alumni_without_pk": case,
                },
                "comparisons": [
                    {
                        "player_id": makar_deep_dive.TARGET,
                        "features": {
                            "goals_per_82": 20,
                            "assists_per_82": 10,
                            "adjusted_pp_points_per_82": 10,
                        },
                    },
                    {
                        "player_id": 2,
                        "name": "Article Defender",
                        "features": {
                            "goals_per_82": 10,
                            "assists_per_82": 20,
                            "adjusted_pp_points_per_82": 5,
                        },
                    },
                ],
            }
        },
    }
    text = makar_deep_dive.narrative(report)
    assert "82-Colorado-game rule" in text
    assert "40 eligible" in text and "25 alumni" in text
    assert "Article Defender" in text and "selected Ray Bourque" in text
    assert "100% higher goals / 82" in text
    assert "50% lower assists / 82" in text
    assert "36 eligible" not in text and "Sandis Ozolinsh" not in text


def test_rate_leadership_distinguishes_ties_from_strictly_higher_values():
    keys = makar_deep_dive.DISPLAY_RATES
    target = {"features": dict.fromkeys(keys, 3)}
    pool = [
        {"player_id": 1, "name": "Lower", "features": dict.fromkeys(keys, 1)},
        {"player_id": 2, "name": "Tied", "features": dict.fromkeys(keys, 3)},
        {"player_id": 3, "name": "Higher", "features": dict.fromkeys(keys, 4)},
    ]
    result = makar_deep_dive.compare_rates(target, pool)
    for item in result.values():
        assert item["target_rank"] == 2
        assert item["historical_profiles_below"] == 1
        assert item["historical_profiles_tied"] == 1
        assert item["historical_leader"] == "Higher"


def article_fixture():
    target = {"player_id": 9, "name": "Target", "features": {"goals_per_82": 4}}
    pool = [
        {"player_id": i, "name": f"Peer {i}", "features": {"goals_per_82": float(i)}}
        for i in (1, 2, 3)
    ]
    case = distinctiveness.neighbour_audit(target, pool, {"goals_per_82": 1})
    selected = {
        "ranked_candidate_ids": [1, 2, 3],
        "matches": [deepcopy(case["closest_match"])],
        "weights": deepcopy(case["weights"]),
        "scales": deepcopy(case["scales"]),
        "target_features": deepcopy(target["features"]),
    }
    return target, pool, case, selected


def test_diagnostic_reconciles_the_card_before_interpreting_isolation():
    target, pool, case, selected = article_fixture()
    makar_deep_dive.reconcile_article(case, target, pool, selected)
    assert case["closest_match"]["player_id"] == 3
    assert makar_deep_dive.gap_shares(case) == {"goals_per_82": 1.0}


@pytest.mark.parametrize("change", ["pool", "match", "distance", "scale", "feature", "weight"])
def test_diagnostic_rejects_another_pool_or_ruler_even_when_the_story_looks_similar(change):
    target, pool, case, selected = article_fixture()
    if change == "pool":
        selected["ranked_candidate_ids"] = [1, 2]
    elif change == "match":
        selected["matches"][0]["player_id"] = 2
    elif change == "distance":
        selected["matches"][0]["distance"] *= 2
    elif change == "scale":
        selected["scales"]["goals_per_82"] *= 2
    elif change == "feature":
        selected["target_features"]["goals_per_82"] = 0
    elif change == "weight":
        selected["weights"]["goals_per_82"] = 0.5
    with pytest.raises(ValueError):
        makar_deep_dive.reconcile_article(case, target, pool, selected)


def radar_fixture():
    target = {
        "player_id": makar_deep_dive.TARGET,
        "name": "Cale Makar",
        "features": {"goals_per_82": 4.0},
    }
    peers = [
        {
            "player_id": makar_deep_dive.BARRIE,
            "name": "Tyson Barrie",
            "features": {"goals_per_82": 3.0},
        },
        {
            "player_id": makar_deep_dive.LILES,
            "name": "John-Michael Liles",
            "features": {"goals_per_82": 1.0},
        },
        {"player_id": 1, "name": "Other", "features": {"goals_per_82": 2.0}},
    ]
    case = distinctiveness.neighbour_audit(target, peers, {"goals_per_82": 1})
    return {
        "window": "age_aligned",
        "age": 27,
        "target_name": target["name"],
        "cases": {"article": case},
        "comparisons": [
            {"player_id": p["player_id"], "name": p["name"], "games": 100, "article_rank": i}
            for i, p in enumerate([target, *peers])
        ],
    }


def test_liles_and_article_match_radars_share_the_same_statistical_and_radial_ruler():
    data = radar_fixture()
    original = deepcopy(data)
    charts = makar_deep_dive.comparison_radars(data)
    assert data == original
    assert [c["historical_id"] for c in charts] == [makar_deep_dive.BARRIE, makar_deep_dive.LILES]
    assert charts[0]["bounds"] == charts[1]["bounds"]
    left, right = charts[0]["axes"][0], charts[1]["axes"][0]
    assert left["current_z"] == right["current_z"]
    assert left["pool_mean"] == right["pool_mean"]
    assert left["pool_sd"] == right["pool_sd"]
    assert charts[1]["distance"] == pytest.approx(3 * charts[0]["distance"])


def test_liles_radar_rejects_an_uncovered_comparator_instead_of_fabricating_spokes():
    data = radar_fixture()
    case = data["cases"]["article"]
    case["target_rankings"] = [
        p for p in case["target_rankings"] if p["player_id"] != makar_deep_dive.LILES
    ]
    with pytest.raises(ValueError, match="lacks complete"):
        makar_deep_dive.comparison_radars(data)
