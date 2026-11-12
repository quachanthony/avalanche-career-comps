"""Immutable research input files and validation of official NHL source grains."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n")


def _integer(value, field, *, positive=False):
    """Reject missing source counts instead of converting them into recorded zeroes."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Missing or noninteger {field}.")
    if value < 0 or (positive and value == 0):
        raise ValueError(f"Invalid {field}.")
    return value


def league_contexts(team_rows):
    """Aggregate NHL Stats team goals, which already exclude shootout decisions.

    Reconciliation with all skater plus goalie goals verified this source contract
    in every saved season from 1979–80 through 2025–26. Do not subtract shootout
    wins again. Earlier frozen snapshots retain their original preparation error.
    """
    if len({(r["seasonId"], r["teamId"]) for r in team_rows}) != len(team_rows):
        raise ValueError("Duplicate team-season rows in league source.")
    league = []
    for season in sorted({r["seasonId"] for r in team_rows}):
        rows = [r for r in team_rows if r["seasonId"] == season]
        games = sum(r["gamesPlayed"] for r in rows)
        goals = sum(r["goalsFor"] for r in rows)
        shots = sum(r["shotsForPerGame"] * r["gamesPlayed"] for r in rows)
        league.append(
            {
                "season_id": season,
                "goals_per_team_game": goals / games,
                "shots_per_team_game": shots / games,
                "games_per_team": games / len(rows),
            }
        )
    return league


def normalize_player(payload, avs_games, last_season):
    """Keep team splits; reject duplicate source rows instead of doubling traded seasons."""
    rows = []
    seen = set()
    avs_api_games = 0
    for r in payload.get("seasonTotals", []):
        if r.get("leagueAbbrev") != "NHL" or r.get("gameTypeId") != 2:
            continue
        season = r["season"]
        if season > last_season:
            continue
        team = r.get("teamName", {}).get("default")
        if not team or "total" in team.lower() or team in ("TOT", "NHL"):
            raise ValueError(f"Unexpected combined NHL row for {payload['playerId']}: {team}")
        key = (season, team, r.get("sequence"))
        if key in seen:
            raise ValueError(f"Duplicate NHL team-season: {payload['playerId']}, {key}")
        seen.add(key)
        if team == "Colorado Avalanche" and season >= 19951996:
            avs_api_games += r["gamesPlayed"]
        row = {"season_id": season, "team": team, "games": r["gamesPlayed"]}
        if payload["position"] == "G":
            row.update(
                shots_against=r.get("shotsAgainst"),
                goals_against=r.get("goalsAgainst"),
                shutouts=r.get("shutouts"),
            )
        else:
            row.update(
                goals=r.get("goals"),
                assists=r.get("assists"),
                shots=r.get("shots"),
                pim=r.get("pim"),
            )
        rows.append(row)
    return {
        "player_id": payload["playerId"],
        "name": payload["firstName"]["default"] + " " + payload["lastName"]["default"],
        "position": payload["position"],
        "birth_date": payload.get("birthDate"),
        "is_active": payload.get("isActive"),
        "avs_games": avs_games,
        "official_avs_games": avs_api_games,
        "seasons": rows,
    }
