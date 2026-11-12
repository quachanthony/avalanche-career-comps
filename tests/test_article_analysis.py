"""Keep the article's two windows separate and preserve historical audit requirements."""

from copy import deepcopy

import pytest

from avalanche_career_comps.article_analysis import (
    check_warehouse_audit,
    compare_results,
    rerun,
    with_skater_eligibility,
)


def fixture():
    def season(year, *, goals=20, assists=30, shots=200):
        return {
            "season_id": year * 10000 + year + 1,
            "games": 82,
            "goals": goals,
            "assists": assists,
            "shots": shots,
            "pim": 30,
        }

    def player(pid, birth, seasons, *, position="F"):
        return {
            "player_id": pid,
            "name": f"Player {pid}",
            "birth_date": birth,
            "position": position,
            "avs_games": 164,
            "seasons": seasons,
        }

    players = [
        player(1, "2000-01-01", [season(2024), season(2025)]),
        player(
            2,
            "1970-01-01",
            [
                season(1995),
                season(1996, goals=2, assists=3, shots=20),
                season(1997, goals=2, assists=3, shots=20),
            ],
        ),
        player(
            3,
            "1970-01-01",
            [
                season(1995, goals=10, assists=15, shots=100),
                season(1996, goals=25, assists=37, shots=250),
                season(1997, goals=25, assists=37, shots=250),
            ],
        ),
        player(7, "2000-01-01", []),
    ]
    sids = sorted({s["season_id"] for p in players for s in p["seasons"]})
    bundle = {
        "config": {
            "last_season": 20252026,
            "min_avs_skater_games": 100,
            "min_avs_goalie_games": 50,
        },
        "players": players,
        "roster": [
            {k: p[k] for k in ("player_id", "name", "position")} for p in (players[0], players[3])
        ],
        "league": [
            {
                "season_id": sid,
                "goals_per_team_game": 3,
                "shots_per_team_game": 30,
                "games_per_team": 82,
            }
            for sid in sids
        ],
        "era_environments": [
            {"season_id": sid, "goals_per_team_game": 3, "assists_per_team_game": 5} for sid in sids
        ],
        "era_peers": [],
        "era_config": {
            "peer_min_games_equivalent_82": 20,
            "minimum_peer_group_size": 2,
            "reference_goals_per_team_game": 3,
            "reference_assists_per_team_game": 5,
        },
    }
    scoring = {
        (p["player_id"], s["season_id"]): {
            "gamesPlayed": s["games"],
            "goals": s["goals"],
            "assists": s["assists"],
            "ppPoints": s["goals"] / 2,
        }
        for p in players
        for s in p["seasons"]
    }
    return bundle, scoring, dict.fromkeys(sids, 1.0)


def test_full_career_is_primary_and_age_adjustment_is_an_independent_comparison():
    bundle, scoring, rates = fixture()
    report = rerun(bundle, scoring, rates, {})
    assert [r["window"] for r in report["rows"]] == ["whole_career", "age_aligned"]
    full, age = report["rows"]
    assert full["matches"][0]["player_id"] == 3
    assert age["matches"][0]["player_id"] == 2
    assert full["matches"][0]["games"] == 246
    assert age["matches"][0]["games"] == 82
    assert len(report["unranked"]) == 2
    for row in report["rows"]:
        assert not {"debut_age", "scoring_trajectory", "hits_per_game"} & row["weights"].keys()
        assert row["pk_status"] == "target_pk_coverage_incomplete"


def test_rerun_cannot_use_the_next_seasons_counts():
    bundle, scoring, rates = fixture()
    expected = rerun(bundle, scoring, rates, {})
    for player in bundle["players"][:3]:
        player["seasons"].append(
            {
                "season_id": 20262027,
                "games": 82,
                "goals": 999,
                "assists": 999,
                "shots": 999,
                "pim": 999,
            }
        )
    assert rerun(bundle, scoring, rates, {}) == expected


def test_warehouse_audit_requires_matching_features_scopes_and_source_snapshot():
    item = {"expected": 2, "counts": {"agree": 2}, "issues": []}
    audit = {
        "provenance": {"input_sha256": "known"},
        "core_state": {"input_fingerprint": "published"},
        "scope_issues": [],
        "league_environments": [{"agrees": True}],
        **{
            key: deepcopy(item)
            for key in (
                "all_league_skater_summary",
                "project_skater_careers",
                "project_goalie_careers",
                "special_teams_points",
            )
        },
    }
    check_warehouse_audit(audit, "known")
    with pytest.raises(ValueError, match="different"):
        check_warehouse_audit(audit, "other")
    audit["special_teams_points"]["counts"] = {"agree": 1, "disagree": 1}
    with pytest.raises(ValueError, match="incomplete or disagrees"):
        check_warehouse_audit(audit, "known")


def test_one_season_screen_is_inclusive_and_does_not_rewrite_source_inputs():
    bundle, scoring, rates = fixture()
    bundle["players"][1]["avs_games"] = 81
    bundle["players"][2]["avs_games"] = 82
    bourque = deepcopy(bundle["players"][1])
    bourque.update(player_id=4, name="Ray Bourque fixture", avs_games=94)
    bundle["players"].append(bourque)
    for season in bourque["seasons"]:
        scoring[4, season["season_id"]] = deepcopy(scoring[2, season["season_id"]])
    original = deepcopy(bundle)
    effective, policy = with_skater_eligibility(bundle)
    report = rerun(effective, scoring, rates, {})
    assert bundle == original
    assert policy["base_config"]["min_avs_skater_games"] == 100
    assert policy["effective_config"]["min_avs_skater_games"] == 82
    assert policy["effective_config"]["min_avs_goalie_games"] == 50
    assert not policy["frozen_source_modified"]
    for row in report["rows"]:
        assert set(row["candidate_ids"]) == {3, 4}
    original_again, _ = with_skater_eligibility(bundle, 100)
    assert original_again["config"]["min_avs_skater_games"] == 100
    assert bundle == original


def test_skater_eligibility_change_keeps_goalie_fifty_appearance_boundary():
    bundle, scoring, rates = fixture()
    target = {
        "player_id": 10,
        "name": "Current Goalie",
        "birth_date": "2000-01-01",
        "position": "G",
        "avs_games": 82,
        "seasons": [
            {
                "season_id": sid,
                "games": 41,
                "shots_against": 1000,
                "goals_against": 90,
                "shutouts": 2,
            }
            for sid in (20242025, 20252026)
        ],
    }
    bundle["players"].append(target)
    bundle["roster"].append({k: target[k] for k in ("player_id", "name", "position")})
    for pid, games in ((11, 49), (12, 50), (13, 82)):
        peer = deepcopy(target)
        peer.update(player_id=pid, name=f"Goalie {pid}", avs_games=games)
        bundle["players"].append(peer)
    effective, _ = with_skater_eligibility(bundle)
    goalies = [r for r in rerun(effective, scoring, rates, {})["rows"] if r["position"] == "G"]
    assert len(goalies) == 2
    assert all(set(row["candidate_ids"]) == {12, 13} for row in goalies)


@pytest.mark.parametrize("minimum", [0, -1, True, 82.5])
def test_eligibility_screen_requires_positive_whole_games(minimum):
    bundle, _, _ = fixture()
    with pytest.raises(ValueError, match="positive integer"):
        with_skater_eligibility(bundle, minimum)


def test_baseline_comparison_exposes_pool_changes_even_if_the_match_stays_the_same():
    bundle, scoring, rates = fixture()
    baseline = rerun(bundle, scoring, rates, {})
    updated = deepcopy(baseline)
    for row in updated["rows"]:
        row["candidate_ids"].append(94)
        row["ranked_candidate_ids"].append(94)
        row["matches"][0]["distance"] += 0.1
    changes = compare_results(updated, baseline)
    assert len(changes) == 2
    for change in changes:
        assert not change["changed"]
        assert not change["weights_changed"]
        assert change["candidate_pool_changed"]
        assert change["score_changed"]
        assert change["eligible_candidates_added"] == [94]
        assert change["ranked_candidates_added"] == [94]
        assert change["previous_eligible_candidates"] == 2
        assert change["updated_eligible_candidates"] == 3
