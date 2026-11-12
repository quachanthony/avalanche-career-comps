"""Hand-auditable seasons protect era environments, peer scope and matched pools."""

from copy import deepcopy
from math import sqrt

import pytest

from avalanche_career_comps.analysis import SKATER_WEIGHTS, ProfileError, analyze, build_profile
from avalanche_career_comps.era import EraProfiles, analyze_era, peer_contexts


def _sid(year):
    return year * 10000 + year + 1


def _season(year, **changes):
    return {
        "season_id": _sid(year),
        "games": 82,
        "goals": 10,
        "assists": 20,
        "shots": 100,
        "pim": 30,
        **changes,
    }


def _player(player_id, start, birth, **changes):
    return {
        "player_id": player_id,
        "name": f"Player {player_id}",
        "position": "C",
        "birth_date": birth,
        "avs_games": 150,
        "is_active": player_id == 1,
        "seasons": [_season(start + offset) for offset in range(5)],
        **changes,
    }


def _peer(player_id, row, **changes):
    return {"player_id": player_id, "position": "F", **row, **changes}


def _bundle():
    config = {
        "reference_goals_per_team_game": 3.0,
        "reference_assists_per_team_game": 5.0,
        "minimum_peer_group_size": 2,
        "peer_min_games_equivalent_82": 2,
        "similarity_weights": dict(SKATER_WEIGHTS),
        "last_season": 20252026,
        "methods": ["baseline", "separate_assists", "season_relative"],
        "career_windows": ["age_aligned", "whole_career"],
        "peer_min_games_sensitivities": [10, 30],
        "source_agreement": "Require matching player-season games and counts.",
    }
    config.update(minimum_peer_group_size=2, peer_min_games_equivalent_82=2)
    players = [
        _player(1, 2021, "2000-06-01"),
        _player(2, 1991, "1970-06-01"),
        _player(3, 1991, "1970-06-01"),
    ]
    for row in players[2]["seasons"]:
        row.update(goals=15, assists=10, shots=120, pim=40)
    peers = [_peer(player["player_id"], row) for player in players for row in player["seasons"]]
    seasons = sorted({row["season_id"] for row in peers})
    for season in seasons:
        year = season // 10000
        # These league peers never wore an Avalanche sweater and must still matter.
        peers.extend(
            [
                _peer(900000 + year, _season(year, goals=0, assists=0, shots=0, pim=0)),
                _peer(910000 + year, _season(year, goals=30, assists=60, shots=300, pim=90)),
            ]
        )
    return {
        "config": {
            "last_season": 20252026,
            "min_avs_skater_games": 100,
            "min_avs_goalie_games": 50,
        },
        "era_config": config,
        "roster": [{"player_id": 1, "name": "Player 1", "position": "C"}],
        "players": players,
        "league": [
            {
                "season_id": _sid(year),
                "games_per_team": 82,
                "goals_per_team_game": 3,
                "shots_per_team_game": 30,
                "goalie_goal_rate": 0.1,
            }
            for year in range(1980, 2027)
            if year != 2004
        ],
        "era_peers": peers,
        "era_environments": [
            {"season_id": season, "goals_per_team_game": 3, "assists_per_team_game": 5}
            for season in seasons
        ],
    }


def _league(bundle):
    return {row["season_id"]: row for row in bundle["league"]}


def test_separate_assist_environment_recovers_production_and_coherent_scoring_trend():
    bundle = _bundle()
    for player in bundle["players"][:2]:
        for offset, row in enumerate(player["seasons"]):
            row["assists"] = (0 if offset < 2 else 20) * (2 if player["player_id"] == 2 else 1)
    for env in bundle["era_environments"]:
        if env["season_id"] < 20000000:
            env["assists_per_team_game"] = 10
    builder = EraProfiles(bundle, "separate_assists")
    target, historical = bundle["players"][:2]
    current = builder(target, _league(bundle), 20252026, end_at_last_played=True)
    retired = builder(historical, _league(bundle), 20252026, end_at_last_played=True)
    assert current["features"] == retired["features"]
    assert current["features"]["goals_per_82"] == pytest.approx(10)
    assert current["features"]["assists_per_82"] == pytest.approx(12)
    # Final three seasons: 30 points/game-season; full career: 22 per 82.
    assert current["features"]["scoring_trajectory"] == pytest.approx(8 / 82)
    baseline = build_profile(historical, _league(bundle), 20252026, end_at_last_played=True)
    assert baseline["features"]["assists_per_82"] == pytest.approx(24)
    assert retired["features"]["shots_per_82"] == baseline["features"]["shots_per_82"]
    assert retired["features"]["pim_per_82"] == baseline["features"]["pim_per_82"]
    assert retired["path"][-1]["cumulative_adjusted_points"] == pytest.approx(110)


def test_shootout_source_correction_and_separate_assist_adjustment_are_distinct():
    bundle = _bundle()
    player = bundle["players"][0]
    player["seasons"] = [_season(2005)]
    league = _league(bundle)
    # The saved baseline subtracted 145 shootout wins from the 7,443 player goals.
    league[20052006]["goals_per_team_game"] = (7443 - 145) / 2460
    bundle["era_environments"].append(
        {
            "season_id": 20052006,
            "goals_per_team_game": 7443 / 2460,
            "assists_per_team_game": 4.8,
        }
    )
    features = {
        method: EraProfiles(bundle, method)(player, league, 20252026, end_at_last_played=True)[
            "features"
        ]
        for method in ("baseline", "corrected_baseline", "separate_assists")
    }
    assert features["baseline"]["goals_per_82"] == pytest.approx(10 * 3 * 2460 / 7298)
    assert features["baseline"]["assists_per_82"] == pytest.approx(20 * 3 * 2460 / 7298)
    assert features["corrected_baseline"]["goals_per_82"] == pytest.approx(10 * 3 * 2460 / 7443)
    assert features["corrected_baseline"]["assists_per_82"] == pytest.approx(20 * 3 * 2460 / 7443)
    assert (
        features["separate_assists"]["goals_per_82"]
        == features["corrected_baseline"]["goals_per_82"]
    )
    assert features["separate_assists"]["assists_per_82"] == pytest.approx(20 * 5 / 4.8)
    assert league[20052006]["goals_per_team_game"] == 7298 / 2460


def test_peer_moments_weight_players_equally_and_include_non_avalanche_peers():
    bundle = _bundle()
    sid = 20252026
    bundle["era_peers"] = [
        _peer(800, _season(2025, goals=0, assists=0, shots=82, pim=0)),
        _peer(801, _season(2025, games=41, goals=41, assists=82, shots=123, pim=82)),
    ]
    context = peer_contexts(bundle)[(sid, "F")]
    assert context["valid"]
    assert context["qualified_players"] == 2
    assert context["means"] == {
        "goals": 0.5,
        "assists": 1,
        "shots": 2,
        "pim": 1,
        "points": 1.5,
    }
    assert context["standard_deviations"] == {
        "goals": 0.5,
        "assists": 1,
        "shots": 1,
        "pim": 1,
        "points": 1.5,
    }
    assert peer_contexts(bundle)[(sid, "D")]["failures"] == ["insufficient_peer_group"]


def test_short_schedule_uses_ceiling_of_equivalent_games_threshold():
    bundle = _bundle()
    bundle["era_config"]["peer_min_games_equivalent_82"] = 20
    _league(bundle)[20252026]["games_per_team"] = 45
    bundle["era_peers"] = [
        _peer(
            800 + games,
            _season(2025, games=games, goals=games, assists=games, shots=games, pim=games),
        )
        for games in (10, 11, 12)
    ]
    context = peer_contexts(bundle)[(20252026, "F")]
    assert context["minimum_games"] == 11
    assert context["qualified_players"] == 2


def test_season_relative_features_are_invariant_to_uniform_season_count_inflation():
    bundle = _bundle()
    original = EraProfiles(bundle, "season_relative")(
        bundle["players"][0], _league(bundle), 20252026, end_at_last_played=True
    )
    inflated = deepcopy(bundle)
    # Different inflation in each season leaves standing among contemporaries identical.
    factors = {_sid(year): year - 2019 for year in range(2021, 2026)}
    for player in inflated["players"]:
        for row in player["seasons"]:
            if row["season_id"] in factors:
                for key in ("goals", "assists", "shots", "pim"):
                    row[key] *= factors[row["season_id"]]
    for row in inflated["era_peers"]:
        if row["season_id"] in factors:
            for key in ("goals", "assists", "shots", "pim"):
                row[key] *= factors[row["season_id"]]
    actual = EraProfiles(inflated, "season_relative")(
        inflated["players"][0], _league(inflated), 20252026, end_at_last_played=True
    )
    assert actual["features"] == pytest.approx(original["features"])
    assert actual["nhl_games"] == original["nhl_games"]


def test_points_z_is_standardized_separately_instead_of_summing_goal_and_assist_z():
    bundle = _bundle()
    player = bundle["players"][0]
    player["seasons"] = [_season(2025, goals=10, assists=20)]
    bundle["era_peers"] = [
        _peer(1, player["seasons"][0]),
        _peer(800, _season(2025, goals=0, assists=40, shots=80, pim=10)),
        _peer(801, _season(2025, goals=20, assists=0, shots=120, pim=20)),
        _peer(802, _season(2025, goals=40, assists=10, shots=140, pim=40)),
    ]
    profile = EraProfiles(bundle, "season_relative")(
        player, _league(bundle), 20252026, end_at_last_played=True
    )
    assert profile["scoring_baseline_value"] == pytest.approx(-1 / sqrt(5))
    assert profile["path"][0]["season_z"]["points"] == pytest.approx(-1 / sqrt(5))
    summed_components = profile["features"]["goals_per_82"] + profile["features"]["assists_per_82"]
    assert profile["scoring_baseline_value"] != pytest.approx(summed_components)
    assert "cumulative_adjusted_points" not in profile["path"][0]
    assert "adjusted_points_per_game" not in profile["path"][0]


def test_below_threshold_seasons_are_retained_and_career_z_uses_games_weights():
    bundle = _bundle()
    player = bundle["players"][0]
    player["seasons"] = [
        _season(2021, games=1, goals=1, assists=2, shots=3, pim=4),
        _season(2025, games=82, goals=0, assists=0, shots=0, pim=0),
    ]
    bundle["era_peers"] = []
    for row in player["seasons"]:
        bundle["era_peers"].append(_peer(1, row))
        year = row["season_id"] // 10000
        # Qualified peer rates are 0 and 2 for every metric in each season.
        bundle["era_peers"].extend(
            [
                _peer(800, _season(year, goals=0, assists=0, shots=0, pim=0)),
                _peer(801, _season(year, goals=164, assists=164, shots=164, pim=164)),
            ]
        )
    # The 82-game zero-count subject is also a qualified peer, so its season moments differ.
    profile = EraProfiles(bundle, "season_relative")(
        player, _league(bundle), 20252026, end_at_last_played=True
    )
    assert profile["nhl_games"] == 83
    assert len(profile["path"]) == 2
    assert profile["below_peer_minimum_games"] == 1
    assert profile["below_peer_minimum_seasons"] == 1
    assert profile["below_peer_minimum_games_fraction"] == pytest.approx(1 / 83)
    # Old goal z=0. Last-season z=-1/sqrt(2); weight by 1 and 82 games.
    expected = -82 / (83 * sqrt(2))
    assert profile["features"]["goals_per_82"] == pytest.approx(expected)
    # The final-three-calendar-season window contains only 2025, not both appearances.
    recent_ppg_z = -1 / sqrt(2)
    old_ppg_z = (3 - 2) / 2
    career_ppg_z = (old_ppg_z + 82 * recent_ppg_z) / 83
    assert profile["features"]["scoring_trajectory"] == pytest.approx(recent_ppg_z - career_ppg_z)


def test_traded_stints_are_collapsed_once_before_exact_peer_agreement_and_rates():
    bundle = _bundle()
    player = bundle["players"][0]
    player["seasons"] = [
        _season(2025, games=20, goals=2, assists=4, shots=20, pim=6),
        _season(2025, games=62, goals=8, assists=16, shots=80, pim=24),
    ]
    original = deepcopy(bundle)
    relative = EraProfiles(bundle, "season_relative")(
        player, _league(bundle), 20252026, end_at_last_played=True
    )
    assert relative["nhl_games"] == 82
    assert len(relative["path"]) == 1
    assert relative["totals"]["raw_goals"] == 10
    assert relative["totals"]["raw_assists"] == 20
    assert bundle == original


def test_missing_or_zero_spread_context_is_not_imputed_as_zero_performance():
    bundle = _bundle()
    player = bundle["players"][0]
    player["seasons"] = [_season(2025)]
    bundle["era_peers"] = [_peer(1, player["seasons"][0])]
    builder = EraProfiles(bundle, "season_relative")
    with pytest.raises(ProfileError, match="unusable_peer_context"):
        builder(player, _league(bundle), 20252026, end_at_last_played=True)
    bundle["era_peers"].append(_peer(800, player["seasons"][0]))
    contexts = peer_contexts(bundle)
    assert "zero_peer_spread_goals" in contexts[(20252026, "F")]["failures"]
    with pytest.raises(ProfileError, match="unusable_peer_context"):
        EraProfiles(bundle, "season_relative", contexts)(
            player, _league(bundle), 20252026, end_at_last_played=True
        )
    bundle["era_environments"] = []
    with pytest.raises(ProfileError, match="missing_assist_environment"):
        EraProfiles(bundle, "separate_assists")(
            player, _league(bundle), 20252026, end_at_last_played=True
        )


def test_age_and_global_cutoffs_precede_source_agreement_checks():
    bundle = _bundle()
    historical = bundle["players"][1]
    historical["seasons"].append(_season(1996, goals=99))  # Beyond target age 25.
    builder = EraProfiles(bundle, "season_relative")
    age = builder(historical, _league(bundle), 20252026, max_age=25)
    assert age["nhl_games"] == 410
    assert age["last_age"] == 25
    with pytest.raises(ProfileError, match="missing_peer_player_season"):
        builder(historical, _league(bundle), 20252026, end_at_last_played=True)
    for player in bundle["players"]:
        player["seasons"].append(_season(2026, goals=999, shots=None))
    actual = EraProfiles(bundle, "season_relative")(
        historical, _league(bundle), 20252026, max_age=25
    )
    assert actual == age


@pytest.mark.parametrize("metric", ["games", "goals", "assists", "shots", "pim"])
def test_controlled_methods_use_identical_intersection_and_preserve_original_baseline(metric):
    bundle = _bundle()
    # A source disagreement in one old season invalidates the entire candidate window.
    row = next(r for r in bundle["era_peers"] if r["player_id"] == 2)
    row[metric] += 1
    before = deepcopy(bundle)
    result = analyze_era(bundle)
    assert bundle == before
    for window in ("age_aligned", "whole_career"):
        branches = result["windows"][window]
        assert branches["baseline"] == analyze(bundle, career_window=window)
        assert branches["baseline"]["results"][0]["candidate_count"] == 2
        for method in (
            "baseline_control",
            "corrected_baseline",
            "separate_assists",
            "season_relative",
        ):
            target = branches[method]["results"][0]
            assert target["candidate_ids"] == target["common_candidate_ids"] == [3]
            assert target["candidate_count"] == 1
            assert target["matches"][0]["player_id"] == 3
            assert target["feature_weights"] == SKATER_WEIGHTS
        relative = branches["season_relative"]
        assert relative["feature_units"]["goals_per_82"] == "GP-weighted season z-score"
        assert "z-score" in relative["feature_labels"]["goals_per_82"]
        assert "per 82" not in relative["feature_labels"]["goals_per_82"]
        failures = branches["coverage"]["season_relative"][0]["failures"]
        assert failures["peer_source_disagreement"] == 1
        for minimum in (10, 30):
            variant = relative["results"][0]["sensitivities"][
                f"peer_minimum_{minimum}_games_per_82"
            ]
            assert variant["same_candidate_pool"]
            assert variant["candidate_count"] == 1
            assert variant["player_id"] == 3


def test_unavailable_peer_target_does_not_fall_back_to_baseline_or_crash_controls():
    bundle = _bundle()
    bundle["era_peers"] = [r for r in bundle["era_peers"] if r["player_id"] != 1]
    result = analyze_era(bundle)
    for branches in result["windows"].values():
        assert branches["baseline"]["results"][0]["status"] == "matched"
        assert branches["season_relative"]["results"][0]["status"] == "insufficient_data"
        assert branches["season_relative"]["results"][0]["reason"] == "missing_peer_player_season"
        for method in (
            "baseline_control",
            "corrected_baseline",
            "separate_assists",
            "season_relative",
        ):
            assert branches[method]["results"][0]["common_candidate_ids"] == []


def test_unadjusted_sensitivity_uses_original_counts_without_requiring_peer_coverage():
    bundle = _bundle()
    player = bundle["players"][0]
    bundle["era_peers"] = []
    bundle["era_environments"] = []
    for method in ("corrected_baseline", "separate_assists", "season_relative"):
        result = EraProfiles(bundle, method)(
            player, _league(bundle), 20252026, adjusted=False, end_at_last_played=True
        )
        expected = build_profile(
            player, _league(bundle), 20252026, adjusted=False, end_at_last_played=True
        )
        assert result == expected


def test_goalies_keep_original_features_rankings_and_weights_in_both_new_methods():
    bundle = _bundle()
    for player in bundle["players"]:
        player["position"] = "G"
        player["seasons"] = [
            {
                "season_id": row["season_id"],
                "games": 50,
                "shots_against": 1500,
                "goals_against": 120 if player["player_id"] != 3 else 130,
                "shutouts": 3,
            }
            for row in player["seasons"]
        ]
    bundle["roster"][0]["position"] = "G"
    result = analyze_era(bundle)
    for branches in result["windows"].values():
        original = branches["baseline"]["results"][0]
        for method in (
            "baseline_control",
            "corrected_baseline",
            "separate_assists",
            "season_relative",
        ):
            actual = branches[method]["results"][0]
            assert actual["matches"] == original["matches"]
            assert actual["target_features"] == original["target_features"]
            assert actual["feature_weights"] == original["feature_weights"]


def test_peer_identity_duplicates_and_unregistered_weight_changes_are_rejected():
    bundle = _bundle()
    bundle["era_peers"].append(deepcopy(bundle["era_peers"][0]))
    with pytest.raises(ValueError, match="Duplicate peer player-season"):
        peer_contexts(bundle)
    bundle = _bundle()
    bundle["era_config"]["similarity_weights"]["log_games"] = 0.3
    with pytest.raises(ValueError, match="retain the original similarity weights"):
        analyze_era(bundle)
