"""Protect full historical comparison pools and expose career-length sensitivity."""

from copy import deepcopy

import pytest

from avalanche_career_comps import feedback_analysis, pipeline, special_teams


def profile(pid, *, goals=1, games=20, log_games=3):
    values = dict.fromkeys(special_teams.WITHOUT_LIFT, 1.0)
    values.update(goals_per_82=goals, log_games=log_games)
    return {
        "player_id": pid,
        "name": str(pid),
        "nhl_games": games,
        "path": [{"season_id": 1, "games": games}],
        "features": values,
    }


def test_missing_pk_cannot_remove_the_closest_historical_comparison():
    target = profile(7, goals=1.01)
    pool = [profile(pid, goals=pid) for pid in (1, 2, 3)]
    minutes = {(7, 1): (20, 1200), (2, 1): (20, 0), (3, 1): (20, 1200)}
    frozen = deepcopy((target, pool, minutes))
    ranked, _, details = feedback_analysis.rank_preserving_pool(target, pool, minutes)
    assert (target, pool, minutes) == frozen
    assert ranked[0]["player_id"] == 1
    assert details["ranked_candidate_ids"] == [1, 2, 3]
    assert details["pk_incomplete_candidate_ids"] == [1]
    assert details["pk_status"] == "pk_omitted_to_preserve_pool"
    assert special_teams.PK_FEATURE not in details["weights"]


@pytest.mark.parametrize("career_games", [True, False])
def test_pk_requires_every_candidate_and_keeps_exactly_ten_percent_weight(career_games):
    pool = [profile(1), profile(2, goals=2)]
    minutes = {(7, 1): (20, 1200), (1, 1): (20, 0), (2, 1): (20, 600)}
    _, _, details = feedback_analysis.rank_preserving_pool(
        profile(7), pool, minutes, include_career_games=career_games
    )
    assert details["pk_status"] == "pk_included"
    assert details["ranked_candidate_ids"] == [1, 2]
    assert details["weights"][special_teams.PK_FEATURE] == pytest.approx(0.1)
    assert sum(details["weights"].values()) == pytest.approx(1)


def test_career_length_can_be_context_without_affecting_the_match():
    target = profile(7, log_games=8)
    pool = [profile(1, log_games=3), profile(2, log_games=8)]
    with_games, _, _ = feedback_analysis.rank_preserving_pool(
        target, pool, {}, include_career_games=True
    )
    without_games, _, details = feedback_analysis.rank_preserving_pool(
        target, pool, {}, include_career_games=False
    )
    assert with_games[0]["player_id"] == 2
    assert without_games[0]["player_id"] == 1
    assert all(p["distance"] == 0 for p in without_games)
    assert "log_games" not in details["weights"]


def test_pool_preserving_article_and_cale_overlay_agree_and_leave_goalies_unchanged():
    reports, _ = feedback_analysis.analyze(include_career_games=True)
    baseline, _ = pipeline.analyze()
    previous_goalies = {
        (r["window"], r["player_id"]): r for r in baseline["roster"]["rows"] if r["position"] == "G"
    }
    for row in reports["roster"]["rows"]:
        if row["position"] == "G":
            assert row == previous_goalies[row["window"], row["player_id"]]
        else:
            assert row["candidate_ids"] == row["ranked_candidate_ids"]
    makar = next(
        r
        for r in reports["roster"]["rows"]
        if r["player_id"] == 8480069 and r["window"] == "whole_career"
    )
    assert len(makar["ranked_candidate_ids"]) == 45
    assert (
        makar["matches"][0]["player_id"]
        == reports["makar"]["isolation"]["rows"][0]["nearest_id"]
        == 8445621
    )
    assert reports["makar"]["isolation"]["rows"][0]["ratio_to_median"] == pytest.approx(
        4.6097637271
    )


def test_production_only_sensitivity_recalculates_the_benchmark_and_neighbours():
    reports, _ = feedback_analysis.analyze(include_career_games=False)
    case = reports["makar"]["isolation"]
    assert "log_games" not in reports["makar"]["weights"]
    assert case["rows"][0]["ratio_to_median"] == pytest.approx(5.1330451175)
    bourque = next(r for r in case["rows"] if r["player_id"] == 8445621)
    assert bourque["nearest_id"] == 8480069
    assert 8445621 in case["changed_historical_neighbours"]


def test_selected_default_omits_career_length_and_keeps_full_careers_primary():
    reports, _ = feedback_analysis.analyze()
    assert reports["method_revision"]["career_games_weighted"] is False
    assert "Full observed careers primary" in reports["method_revision"]["career_window"]
    for row in reports["roster"]["rows"]:
        assert "log_games" not in row["weights"]
    assert reports["makar"]["isolation"]["rows"][0]["ratio_to_median"] == pytest.approx(
        5.1330451175
    )
