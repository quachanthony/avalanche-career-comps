"""Hand-auditable official-row scope checks; never call the live NHL API."""

import pytest

from avalanche_career_comps.inputs import league_contexts, normalize_player


def player(rows):
    return {
        "playerId": 1,
        "firstName": {"default": "Test"},
        "lastName": {"default": "Player"},
        "position": "C",
        "birthDate": "1970-01-01",
        "isActive": False,
        "seasonTotals": rows,
    }


def row(season, team, gp, sequence=1):
    return {
        "leagueAbbrev": "NHL",
        "gameTypeId": 2,
        "season": season,
        "teamName": {"default": team},
        "gamesPlayed": gp,
        "sequence": sequence,
        "goals": 2,
        "assists": 3,
        "shots": 10,
        "pim": 4,
    }


def test_colorado_eligibility_excludes_quebec_but_career_keeps_it():
    rows = [
        row(19941995, "Quebec Nordiques", 40),
        row(19951996, "Colorado Avalanche", 50),
        row(20262027, "Colorado Avalanche", 12),
    ]
    result = normalize_player(player(rows), 50, 20252026)
    assert result["official_avs_games"] == 50
    assert len(result["seasons"]) == 2
    assert result["seasons"][0]["team"] == "Quebec Nordiques"


def test_return_to_same_team_has_distinct_stints():
    rows = [row(20052006, "Chicago Blackhawks", 14, 1), row(20052006, "Chicago Blackhawks", 15, 4)]
    result = normalize_player(player(rows), 0, 20252026)
    assert sum(r["games"] for r in result["seasons"]) == 29
    with pytest.raises(ValueError, match="Duplicate NHL"):
        normalize_player(player(rows + [rows[0]]), 0, 20252026)


def test_playoffs_minors_and_combined_totals_do_not_silently_enter():
    regular = row(20002001, "Colorado Avalanche", 82)
    playoff = {**regular, "gameTypeId": 3}
    minor = {**regular, "leagueAbbrev": "AHL"}
    assert len(normalize_player(player([regular, playoff, minor]), 82, 20252026)["seasons"]) == 1
    with pytest.raises(ValueError, match="combined"):
        normalize_player(player([row(20002001, "TOTAL", 82)]), 82, 20252026)


def test_missing_counts_stay_null():
    missing = row(20002001, "Colorado Avalanche", 82)
    missing.pop("shots")
    assert normalize_player(player([missing]), 82, 20252026)["seasons"][0]["shots"] is None


def test_stats_team_goals_already_exclude_shootout_decisions():
    rows = [
        {
            "seasonId": 20052006,
            "teamId": 1,
            "gamesPlayed": 2,
            "goalsFor": 10,
            "winsInShootout": 1,
            "shotsForPerGame": 30,
        },
        {
            "seasonId": 20052006,
            "teamId": 2,
            "gamesPlayed": 2,
            "goalsFor": 20,
            "winsInShootout": 1,
            "shotsForPerGame": 40,
        },
    ]
    context = league_contexts(rows)[0]
    assert context["goals_per_team_game"] == 30 / 4
    assert context["shots_per_team_game"] == 35
    assert context["games_per_team"] == 2
    # Changing shootout wins must never remove goals from this source field.
    rows[0]["winsInShootout"] = 0
    assert league_contexts(rows)[0] == context
    with pytest.raises(ValueError, match="Duplicate"):
        league_contexts(rows + rows[:1])
