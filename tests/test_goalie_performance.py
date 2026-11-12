"""Validate complete exposures and season-relative goalie performance rates."""

from copy import deepcopy

import pytest

from avalanche_career_comps import analysis
from avalanche_career_comps import goalie_performance as performance


def stint(team, games, starts, shutouts, seconds, *, sequence=1):
    return {
        "leagueAbbrev": "NHL",
        "gameTypeId": 2,
        "season": 20242025,
        "teamName": {"default": team},
        "sequence": sequence,
        "gamesPlayed": games,
        "gamesStarted": starts,
        "shutouts": shutouts,
        "timeOnIce": f"{seconds // 60}:{seconds % 60:02d}",
        "shotsAgainst": games * 25,
        "goalsAgainst": games * 2,
    }


def test_traded_goalie_uses_both_real_team_stints_once():
    payload = {
        "playerId": 7,
        "position": "G",
        "seasonTotals": [
            stint("Team A", 2, 1, 1, 7200),
            stint("Team B", 3, 3, 0, 10800, sequence=2),
        ],
    }
    original = deepcopy(payload)
    rows = performance.landing_seasons(payload, 20242025)
    assert payload == original
    assert rows[7, 20242025] == {
        "games": 5,
        "starts": 4,
        "shutouts": 1,
        "seconds": 18000,
        "shots_against": 125,
        "goals_against": 10,
    }
    payload["seasonTotals"].append(stint("Team A", 2, 1, 1, 7200))
    with pytest.raises(ValueError, match="Duplicate"):
        performance.landing_seasons(payload, 20242025)


@pytest.mark.parametrize("bad_team", ["TOT", "NHL", "Two Teams Total", ""])
def test_combined_rows_do_not_double_count_the_real_team_stints(bad_team):
    payload = {"playerId": 7, "position": "G", "seasonTotals": [stint(bad_team, 3, 3, 1, 10800)]}
    with pytest.raises(ValueError, match="combined or missing"):
        performance.landing_seasons(payload, 20242025)


def test_cutoff_and_game_type_are_explicit():
    future = stint("Team", 3, 3, 1, 10800)
    future["season"] = 20252026
    playoffs = stint("Team", 3, 3, 1, 10800)
    playoffs["gameTypeId"] = 3
    payload = {"playerId": 7, "position": "G", "seasonTotals": [future, playoffs]}
    assert performance.landing_seasons(payload, 20242025) == {}


@pytest.mark.parametrize("field", ["gamesStarted", "shutouts", "timeOnIce"])
def test_missing_values_are_not_silently_zero(field):
    row = stint("Team", 3, 3, 0, 10800)
    row[field] = None
    with pytest.raises((ValueError, TypeError)):
        performance.landing_seasons(
            {"playerId": 7, "position": "G", "seasonTotals": [row]}, 20242025
        )


def summary(pid, starts, shutouts, *, sid=20242025):
    return {
        "playerId": pid,
        "seasonId": sid,
        "gamesPlayed": starts,
        "gamesStarted": starts,
        "shutouts": shutouts,
        "timeOnIce": starts * 3600,
        "shotsAgainst": starts * 25,
        "goalsAgainst": starts * 2,
    }


def test_league_rate_uses_starts_and_combined_player_seasons_not_mean_of_percentages():
    rows = [summary(1, 10, 2), summary(2, 90, 3)]
    players, league = performance.league_seasons(rows, 20242025, 20242025)
    assert len(players) == 2
    assert league[20242025]["shutout_rate"] == pytest.approx(0.05)
    with pytest.raises(ValueError, match="Duplicate"):
        performance.league_seasons([*rows, rows[0]], 20242025, 20242025)


def feature_fixture():
    profile = {
        "player_id": 7,
        "nhl_games": 103,
        "path": [{"season_id": 20232024, "games": 12}, {"season_id": 20242025, "games": 91}],
    }
    known = {
        (7, 20232024): {"games": 12, "starts": 10, "shutouts": 2, "seconds": 36000},
        (7, 20242025): {"games": 91, "starts": 90, "shutouts": 3, "seconds": 324000},
    }
    saved = {
        "player_seasons": known,
        "league_seasons": {20232024: {"shutout_rate": 0.05}, 20242025: {"shutout_rate": 0.10}},
    }
    quality = {
        "player_seasons": {
            (7, 20232024): {"games": 12, "starts": 10, "quality_starts": 8},
            (7, 20242025): {"games": 91, "starts": 90, "quality_starts": 45},
        },
        "league_seasons": {
            20232024: {"starts": 100, "quality_starts": 60},
            20242025: {"starts": 100, "quality_starts": 40},
        },
    }
    return profile, saved, quality


def test_performance_features_sum_counts_and_season_exposures_before_dividing():
    profile, saved, quality = feature_fixture()
    original = deepcopy((profile, saved, quality))
    result = performance.features(profile, saved, quality)
    assert (profile, saved, quality) == original
    # SO expectation = 10*.05 + 90*.10 = 9.5; actual = 5 over 100 starts.
    assert result["features"][performance.SHUTOUT_FEATURE] == pytest.approx(-4.5)
    # QS expectation = 10*.60 + 90*.40 = 42; actual = 53 over 100 starts.
    assert result["features"][performance.QUALITY_FEATURE] == pytest.approx(11)
    assert result["context"]["raw_quality_start_percentage"] == pytest.approx(53)
    assert result["context"]["raw_shutouts_per_100_starts"] == pytest.approx(5)
    assert "log_games" not in result["features"]


def test_relief_only_season_keeps_zero_starts_and_zero_quality_starts():
    profile, saved, quality = feature_fixture()
    profile["path"][0]["games"] = 1
    profile["nhl_games"] = 92
    saved["player_seasons"][7, 20232024].update(games=1, starts=0, shutouts=0)
    quality["player_seasons"][7, 20232024].update(games=1, starts=0, quality_starts=0)
    result = performance.features(profile, saved, quality)
    assert result["context"]["starts"] == 90
    assert result["context"]["quality_starts"] == 45


@pytest.mark.parametrize(
    "issue", ["missing_season", "games", "starts", "excess_qs", "missing_league"]
)
def test_quality_features_fail_closed_on_partial_coverage_or_exposure_disagreement(issue):
    profile, saved, quality = feature_fixture()
    key = 7, 20232024
    if issue == "missing_season":
        del quality["player_seasons"][key]
    elif issue == "missing_league":
        del quality["league_seasons"][20232024]
    elif issue == "games":
        quality["player_seasons"][key]["games"] += 1
    elif issue == "starts":
        quality["player_seasons"][key]["starts"] += 1
    else:
        quality["player_seasons"][key]["quality_starts"] = 11
    with pytest.raises((ValueError, analysis.ProfileError)):
        performance.features(profile, saved, quality)
