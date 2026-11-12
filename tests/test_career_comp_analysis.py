"""Hand-auditable examples protect era scaling, career cutoffs and eligibility."""

from copy import deepcopy
from math import log1p

import pytest

from avalanche_career_comps.analysis import analyze, build_profile, collapse_seasons, season_age


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


def _player(player_id, start=1993, birth="1970-06-01", **changes):
    return {
        "player_id": player_id,
        "name": f"Player {player_id}",
        "position": "C",
        "birth_date": birth,
        "avs_games": 150,
        "is_active": False,
        "seasons": [_season(start + i) for i in range(3)],
        **changes,
    }


def _bundle():
    league = [
        {
            "season_id": y * 10000 + y + 1,
            "goals_per_team_game": 3,
            "shots_per_team_game": 30,
            "games_per_team": 82,
        }
        for y in range(1980, 2027)
        if y != 2004
    ]
    current = _player(1, start=2023, birth="2000-06-01", is_active=True)
    return {
        "config": {"last_season": 20252026},
        "league": league,
        "roster": [{"player_id": 1, "name": "Player 1", "position": "C"}],
        "players": [current, _player(2), _player(3)],
    }


def _league(bundle):
    return {r["season_id"]: r for r in bundle["league"]}


def test_february_age_changes_after_birthday_and_never_uses_calendar_age_only():
    assert season_age("2000-02-01", 20252026) == 26
    assert season_age("2000-02-02", 20252026) == 25


def test_era_adjustment_recovers_identical_careers_and_raw_baseline_changes_match():
    bundle = _bundle()
    # Player 2 scored twice as much in a league with twice the offense/shots.
    for row in bundle["players"][1]["seasons"]:
        row.update(goals=20, assists=40, shots=200)
    for row in bundle["league"]:
        if row["season_id"] // 10000 in {1993, 1994, 1995}:
            row.update(goals_per_team_game=6, shots_per_team_game=60)
    # Player 3 played later, with the same raw counts as today's player.
    bundle["players"][2] = _player(
        3, start=2003, birth="1980-06-01", seasons=[_season(2003), _season(2005), _season(2006)]
    )
    # Match all age cutoffs at 25; the last of these is later and must be truncated.
    result = analyze(bundle)["results"][0]
    assert result["matches"][0]["player_id"] == 2
    assert result["matches"][0]["distance"] == pytest.approx(0)
    profile = result["matches"][0]
    assert profile["features"]["goals_per_82"] == pytest.approx(10)
    assert profile["features"]["assists_per_82"] == pytest.approx(20)
    assert profile["features"]["shots_per_82"] == pytest.approx(100)
    # Era off gives Player 3 the closer scoring profile (not necessarily all career size).
    assert result["sensitivities"]["unadjusted"]["player_id"] == 3


def test_historical_future_and_current_incomplete_season_never_enter_features():
    bundle = _bundle()
    expected = analyze(bundle)
    # Candidate's age-26 season and every 2026–27 row are beyond their cutoffs.
    bundle["players"][1]["seasons"].append(_season(1996, goals=9999, shots=None))
    bundle["players"][0]["seasons"].append(_season(2026, goals=9999, shots=None))
    actual = analyze(bundle)
    assert actual["results"][0]["target_features"] == expected["results"][0]["target_features"]
    assert actual["results"][0]["matches"] == expected["results"][0]["matches"]
    assert actual["results"][0]["matches"][0]["last_age"] == 25


def test_position_current_roster_and_zero_colorado_games_are_excluded():
    bundle = _bundle()
    bundle["players"][1]["position"] = "D"
    bundle["players"][2]["avs_games"] = 0  # Quebec-only eligibility remains zero.
    bundle["players"].append(_player(4))
    bundle["roster"].append({"player_id": 4, "name": "Player 4", "position": "C"})
    result = analyze(bundle)["results"][0]
    assert result["status"] == "no_eligible_comparison"
    assert result["matches"] == []
    assert result["candidate_count"] == 0


def test_threshold_sensitivity_is_explicit_and_never_silently_loosened():
    bundle = _bundle()
    bundle["players"][1]["avs_games"] = 94
    bundle["players"][2]["seasons"][0]["goals"] = 15
    result = analyze(bundle)["results"][0]
    assert result["matches"][0]["player_id"] == 3
    assert result["sensitivities"]["threshold_low"]["player_id"] == 2
    assert result["sensitivities"]["threshold_low"]["changed"]
    assert result["candidate_count"] == 1
    assert "small_comparison_pool" in result["quality_flags"]


def test_missing_measurement_is_not_zero_and_young_career_is_insufficient():
    bundle = _bundle()
    bundle["players"][1]["seasons"][0]["shots"] = None
    result = analyze(bundle)["results"][0]
    assert result["candidate_count"] == 1
    assert result["excluded_reasons"]["missing_shots"] == 1
    bundle["players"][0]["seasons"] = [_season(2025, games=49)]
    result = analyze(bundle)["results"][0]
    assert result["status"] == "insufficient_data"
    assert result["reason"] == "insufficient_nhl_games"


def test_traded_player_team_rows_are_combined_before_rates_are_computed():
    player = _player(
        1, seasons=[_season(1995, games=20, goals=2), _season(1995, games=30, goals=9)]
    )
    rows = collapse_seasons(player, 19951996)
    assert len(rows) == 1
    assert rows[0]["games"] == 50
    assert rows[0]["goals"] == 11
    player["seasons"][1]["assists"] = None
    assert collapse_seasons(player, 19951996)[0]["assists"] is None


def test_distance_contributions_sum_to_square_and_ties_use_id():
    result = analyze(_bundle())["results"][0]
    assert [m["player_id"] for m in result["matches"]] == [2, 3]
    for match in result["matches"]:
        assert sum(match["contributions"].values()) == pytest.approx(match["distance"] ** 2)
    assert result["target_features"]["log_games"] == pytest.approx(log1p(246))
    assert result["stability"]["not_a_probability"]
    # The named PIM omission must not also count as a second identical variant.
    assert "no_pim" in result["sensitivities"]
    assert "without_pim_per_82" not in result["sensitivities"]
    assert result["stability"]["variants"] == len(result["sensitivities"])


def test_recent_trend_uses_last_three_calendar_seasons_not_last_three_appearances():
    bundle = _bundle()
    player = bundle["players"][0]
    player["seasons"] = [_season(2020, goals=100), _season(2022, goals=20), _season(2025, goals=10)]
    profile = build_profile(player, _league(bundle), 20252026)
    career_ppg = (130 + 60) / 246
    assert profile["features"]["scoring_trajectory"] == pytest.approx(30 / 82 - career_ppg)


def test_career_ending_too_young_is_not_forced_into_comparison_pool():
    bundle = _bundle()
    bundle["players"][1]["seasons"] = [_season(1991)]
    result = analyze(bundle)["results"][0]
    assert result["candidate_count"] == 1
    assert result["excluded_reasons"]["career_ended_before_comparable_age"] == 1


def test_goalies_use_goalie_league_rate_and_shot_weighting_not_mean_season_rates():
    bundle = _bundle()
    player = _player(
        1,
        position="G",
        seasons=[
            {
                "season_id": 19931994,
                "games": 50,
                "shots_against": 1500,
                "goals_against": 120,
                "shutouts": 3,
            },
            {
                "season_id": 19941995,
                "games": 10,
                "shots_against": 300,
                "goals_against": 30,
                "shutouts": 0,
            },
        ],
    )
    league = _league(bundle)
    league[19931994]["goalie_goal_rate"] = 0.09
    league[19941995]["goalie_goal_rate"] = 0.08
    # One shortened season's appearances are adjusted to an 82-game schedule.
    league[19941995]["games_per_team"] = 41
    profile = build_profile(player, league, 19941995)
    assert profile["features"]["relative_save_percentage"] == pytest.approx((135 + 24 - 150) / 1800)
    assert profile["features"]["schedule_adjusted_games_per_season"] == pytest.approx(35)
    assert profile["features"]["adjusted_shots_per_game"] == pytest.approx(30)


def test_zero_shot_goalie_appearance_stays_missing_in_path_not_zero_sv():
    bundle = _bundle()
    player = _player(
        1,
        position="G",
        seasons=[
            {
                "season_id": 19931994,
                "games": 50,
                "shots_against": 1500,
                "goals_against": 120,
                "shutouts": 3,
            },
            {
                "season_id": 19941995,
                "games": 1,
                "shots_against": 0,
                "goals_against": 0,
                "shutouts": 0,
            },
        ],
    )
    profile = build_profile(player, _league(bundle), 19941995)
    assert profile["path"][-1]["relative_save_percentage"] is None
    assert profile["features"]["relative_save_percentage"] == pytest.approx(0.02)


def test_duplicate_player_ids_raise_instead_of_overwriting_identity():
    bundle = _bundle()
    bundle["players"].append(deepcopy(bundle["players"][0]))
    with pytest.raises(ValueError, match="duplicate player_id"):
        analyze(bundle)
