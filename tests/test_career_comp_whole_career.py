"""Small observed careers distinguish full windows from age-aligned comparisons."""

from copy import deepcopy
from math import log1p
from statistics import pstdev

import pytest

from avalanche_career_comps.analysis import analyze, build_profile


def _season(year, **changes):
    return {
        "season_id": year * 10000 + year + 1,
        "games": 82,
        "goals": 10,
        "assists": 20,
        "shots": 100,
        "pim": 30,
        **changes,
    }


def _player(player_id, *, start=1993, birth="1970-06-01", **changes):
    return {
        "player_id": player_id,
        "name": f"Player {player_id}",
        "position": "C",
        "birth_date": birth,
        "avs_games": 150,
        "is_active": False,
        "seasons": [_season(start + offset) for offset in range(3)],
        **changes,
    }


def _bundle():
    return {
        "config": {"last_season": 20252026},
        "league": [
            {
                "season_id": year * 10000 + year + 1,
                "goals_per_team_game": 3,
                "shots_per_team_game": 30,
                "games_per_team": 82,
                "goalie_goal_rate": 0.1,
            }
            for year in range(1980, 2027)
            if year != 2004
        ],
        "roster": [{"player_id": 1, "name": "Player 1", "position": "C"}],
        "players": [
            _player(1, start=2023, birth="2000-06-01", is_active=True),
            _player(2),
            _player(3),
        ],
    }


def _league(bundle):
    return {row["season_id"]: row for row in bundle["league"]}


def test_retired_skater_recent_window_ends_at_last_played_calendar_season():
    bundle = _bundle()
    retired = _player(
        2,
        seasons=[
            _season(1993, goals=82, assists=0),
            _season(1998, goals=41, assists=0),
            _season(2000, goals=0, assists=0),
        ],
    )
    profile = build_profile(retired, _league(bundle), 20252026, end_at_last_played=True)
    assert profile["first_season"] == 19931994
    assert profile["last_season"] == profile["window_end_season"] == 20002001
    assert profile["career_seasons"] == 8  # Interior missed years remain in the calendar.
    assert profile["features"]["goals_per_82"] == pytest.approx(41)
    # Career: 123/246=.5 points/game. Final 1998–2000 calendar window: 41/164=.25.
    assert profile["features"]["scoring_trajectory"] == pytest.approx(-0.25)
    assert profile["is_active"] is False


def test_retired_goalie_workload_retains_interior_missed_years_and_excludes_lockout():
    bundle = _bundle()
    league = _league(bundle)
    league[20072008]["games_per_team"] = 41
    retired = _player(
        2,
        position="G",
        seasons=[
            {
                "season_id": year * 10000 + year + 1,
                "games": games,
                "shots_against": 30 * games,
                "goals_against": 2.7 * games,
                "shutouts": 0,
            }
            for year, games in [(2002, 40), (2005, 20), (2007, 20)]
        ],
    )
    profile = build_profile(retired, league, 20252026, end_at_last_played=True)
    # 2002 through 2007 includes 2003 and 2006 without appearances, but no 2004–05.
    assert profile["career_seasons"] == 5
    assert profile["nhl_games"] == 80
    assert profile["features"]["schedule_adjusted_games_per_season"] == pytest.approx(20)
    assert profile["features"]["relative_save_percentage"] == pytest.approx(0.01)
    assert profile["last_season"] == 20072008


def test_whole_career_includes_post_target_age_seasons_but_keeps_global_cutoff():
    bundle = _bundle()
    bundle["players"][1]["seasons"].append(_season(1996, goals=100))
    age = analyze(bundle)["results"][0]
    whole = analyze(bundle, career_window="whole_career")["results"][0]
    assert age["matches"][0]["player_id"] == 2  # Identical at age 25; stable ID breaks tie.
    assert age["matches"][0]["nhl_games"] == 246
    assert whole["matches"][0]["player_id"] == 3
    full_candidate = next(row for row in whole["matches"] if row["player_id"] == 2)
    assert full_candidate["nhl_games"] == 328
    assert full_candidate["last_age"] == 26
    assert full_candidate["totals"]["goals"] == 130
    assert full_candidate["features"]["goals_per_82"] == pytest.approx(32.5)

    # An unusable ongoing-season observation must affect neither side of either branch.
    expected_age = deepcopy(age)
    expected_whole = deepcopy(whole)
    for player in bundle["players"]:
        player["seasons"].append(_season(2026, goals=9999, shots=None))
    assert analyze(bundle)["results"][0] == expected_age
    assert analyze(bundle, career_window="whole_career")["results"][0] == expected_whole


def test_whole_career_still_excludes_current_roster_other_positions_and_quebec_only():
    bundle = _bundle()
    bundle["players"][1]["avs_games"] = 100
    bundle["players"][2]["avs_games"] = 0  # Full NHL history does not grant COL eligibility.
    bundle["players"].extend(
        [
            _player(4, start=2023, birth="2000-06-01", is_active=True),
            _player(5, position="D"),
            _player(6, avs_games=99),
        ]
    )
    bundle["roster"].append({"player_id": 4, "name": "Player 4", "position": "C"})
    result = analyze(bundle, career_window="whole_career")["results"][0]
    assert result["candidate_count"] == 1
    assert result["eligible_candidate_ids"] == [2]
    assert result["age_pool_control"]["candidate_ids"] == [2]
    assert result["sensitivities"]["threshold_low"]["candidate_count"] == 2


def test_missing_full_career_tail_excludes_candidate_instead_of_shortening_window():
    bundle = _bundle()
    bundle["players"][1]["seasons"].append(_season(1996, shots=None))
    age = analyze(bundle)["results"][0]
    whole = analyze(bundle, career_window="whole_career")["results"][0]
    assert age["candidate_count"] == 2
    assert age["matches"][0]["player_id"] == 2
    assert whole["candidate_count"] == 1
    assert whole["eligible_candidate_ids"] == [3]
    assert whole["age_pool_control"]["candidate_ids"] == [3]
    assert whole["excluded_reasons"]["missing_shots"] == 1


def test_active_source_metadata_labels_unfinished_alumni_without_changing_distance():
    bundle = _bundle()
    bundle["players"][1]["is_active"] = True
    result = analyze(bundle, career_window="whole_career")["results"][0]
    assert result["target"]["is_active"] is True
    assert result["matches"][0]["is_active"] is True
    assert "alumnus_active_at_source_snapshot" in result["quality_flags"]
    bundle["players"][1]["is_active"] = None
    unknown = analyze(bundle, career_window="whole_career")["results"][0]
    assert unknown["matches"][0]["is_active"] is None
    assert unknown["matches"][0]["features"] == result["matches"][0]["features"]
    assert unknown["matches"][0]["distance"] == result["matches"][0]["distance"]
    assert "alumnus_active_at_source_snapshot" not in unknown["quality_flags"]


def test_paired_control_uses_exact_age_and_full_coverage_intersection_and_auditable_gaps():
    bundle = _bundle()
    bundle["players"][1]["seasons"].append(_season(1996, goals=30))
    for season in bundle["players"][2]["seasons"]:
        season["goals"] = 20
    bundle["players"].extend(
        [
            _player(4, seasons=[_season(1993)]),  # Full valid; retired too young for age pool.
            _player(5, seasons=[_season(1993 + i) for i in range(3)] + [_season(1996, shots=None)]),
            _player(6, avs_games=75),  # Sensitivity-only; not in either primary control.
        ]
    )
    result = analyze(bundle, career_window="whole_career")["results"][0]
    control = result["age_pool_control"]
    assert result["eligible_candidate_ids"] == [2, 3, 4]
    assert control["candidate_count"] == 2
    assert control["candidate_ids"] == [2, 3]
    assert sorted(row["player_id"] for row in control["matches"]) == [2, 3]
    assert sorted(row["player_id"] for row in control["age_aligned_matches"]) == [2, 3]
    assert result["excluded_reasons"]["missing_shots"] == 1

    for match_key, scale_key in [
        ("matches", "scales"),
        ("age_aligned_matches", "age_aligned_scales"),
    ]:
        matches = control[match_key]
        for feature, weight in result["feature_weights"].items():
            expected_scale = pstdev(row["features"][feature] for row in matches) or 1.0
            assert control[scale_key][feature] == pytest.approx(expected_scale)
            for match in matches:
                difference = result["target_features"][feature] - match["features"][feature]
                assert match["contributions"][feature] == pytest.approx(
                    weight * (difference / expected_scale) ** 2
                )
        for match in matches:
            assert sum(match["contributions"].values()) == pytest.approx(match["distance"] ** 2)


def test_original_default_stays_age_aligned_with_hand_auditable_features_and_id_tie():
    bundle = _bundle()
    bundle["players"][1]["seasons"].append(_season(1996, goals=1000, shots=None))
    original = analyze(bundle)
    assert original == analyze(bundle, career_window="age_aligned")
    result = original["results"][0]
    assert [row["player_id"] for row in result["matches"]] == [2, 3]
    assert result["matches"][0]["distance"] == pytest.approx(0)
    assert result["target_features"] == {
        "goals_per_82": 10,
        "assists_per_82": 20,
        "shots_per_82": 100,
        "pim_per_82": 30,
        "log_games": log1p(246),
        "debut_age": 23,
        "scoring_trajectory": 0,
    }
    assert result["matches"][0]["last_age"] == 25
    assert "career_window" not in original
    assert "eligible_candidate_ids" not in result
    assert "window_end_season" not in result["matches"][0]


def test_full_target_can_be_compared_when_original_recent_window_is_unavailable():
    bundle = _bundle()
    bundle["players"][0]["seasons"] = [_season(year) for year in (2017, 2018, 2019)]
    assert analyze(bundle)["results"][0]["reason"] == "no_recent_seasons"
    whole = analyze(bundle, career_window="whole_career")["results"][0]
    assert whole["status"] == "matched"
    assert whole["target"]["window_end_season"] == 20192020
    assert whole["age_pool_control"]["candidate_count"] == 0
    assert whole["age_pool_control"]["matches"] == []
    assert whole["age_pool_control"]["age_aligned_matches"] == []
