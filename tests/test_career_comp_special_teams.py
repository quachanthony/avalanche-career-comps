"""Verify special-teams units and complete-window minute coverage."""

import pytest

from avalanche_career_comps.special_teams import (
    PK_FEATURE,
    PP_FEATURE,
    WITHOUT_LIFT,
    pk_context,
    pp_profile,
    rank_without_lift,
)


def test_power_play_profile_sums_adjusted_counts_in_window():
    profile = {
        "name": "Test Skater",
        "player_id": 7,
        "nhl_games": 82,
        "features": {"goals_per_82": 20},
        "path": [{"season_id": 1, "games": 20}, {"season_id": 2, "games": 62}],
    }
    history = {
        1: {"games": 20, "goals": 5, "assists": 9},
        2: {"games": 62, "goals": 15, "assists": 21},
    }
    scoring = {
        (7, 1): {"gamesPlayed": 20, "goals": 5, "assists": 9, "ppPoints": 5},
        (7, 2): {"gamesPlayed": 62, "goals": 15, "assists": 21, "ppPoints": 10},
        (7, 3): {"gamesPlayed": 82, "goals": 60, "assists": 70, "ppPoints": 65},
    }
    adjusted = pp_profile(profile, history, scoring, {1: 2.0, 2: 0.5})
    assert adjusted["features"][PP_FEATURE] == pytest.approx(15)
    assert profile["features"] == {"goals_per_82": 20}


def test_penalty_kill_context_keeps_true_zeros_and_requires_all_games():
    profile = {
        "player_id": 7,
        "nhl_games": 82,
        "path": [{"season_id": 1, "games": 20}, {"season_id": 2, "games": 62}],
    }
    one_season = {(7, 1): (20, 0)}
    assert pk_context(profile, one_season)["minutes_per_game"] is None
    assert pk_context(profile, {**one_season, (7, 2): (62, 0)})["minutes_per_game"] == 0
    assert pk_context(profile, {**one_season, (7, 2): (62, 4920)})["minutes_per_game"] == 1


@pytest.mark.parametrize(
    ("target_seconds", "missing_candidate", "status", "winner"),
    [
        (1200, 1, "pk_included", 3),
        (1180, 1, "pk_below_minimum", 1),
        (1200, 3, "insufficient_pk_candidates", 1),
    ],
)
def test_pk_ranking_uses_only_complete_careers_with_regular_target_use(
    target_seconds, missing_candidate, status, winner
):
    def profile(pid):
        return {
            "player_id": pid,
            "name": str(pid),
            "nhl_games": 20,
            "path": [{"season_id": 1, "games": 20}],
            "features": {**dict.fromkeys(WITHOUT_LIFT, 1), "scoring_trajectory": pid},
        }

    minutes = {(7, 1): (20, target_seconds), (2, 1): (20, 0), (3, 1): (20, 1200)}
    minutes.pop((missing_candidate, 1), None)
    ranked, _, details = rank_without_lift(profile(7), [profile(i) for i in (1, 2, 3)], minutes)
    assert ranked[0]["player_id"] == winner
    assert details["pk_status"] == status
    assert "scoring_trajectory" not in details["weights"]
    if status == "pk_included":
        assert details["ranked_candidate_ids"] == [2, 3]
        assert details["weights"][PK_FEATURE] == pytest.approx(0.1)
        assert details["same_pool_without_pk_match"] == "2"
    else:
        assert details["ranked_candidate_ids"] == [1, 2, 3]
        assert PK_FEATURE not in details["weights"]
