"""Validate preserved official NHL quality-start counts and their league context."""

from __future__ import annotations

from math import isclose
from pathlib import Path

from . import inputs


def _count(row, field):
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Missing or invalid goalie quality-start count: {field}.")
    return value


def _pages(directory, records):
    """Require complete pages, unique player-season keys and coherent QS fractions."""
    output = {}
    for record in records:
        path = directory / record["file"]
        if inputs.digest(path) != record["sha256"]:
            raise ValueError("An official quality-start source differs from its recorded hash.")
        payload = inputs.read_json(path)
        rows = payload["data"]
        for ordinal, row in enumerate(rows):
            key = row["playerId"], row["seasonId"]
            if key in output:
                raise ValueError("Duplicate goalie quality-start player-season.")
            games = _count(row, "gamesPlayed")
            starts = _count(row, "gamesStarted")
            quality_starts = _count(row, "qualityStart")
            if starts > games or quality_starts > starts:
                raise ValueError("Quality starts must not exceed starts or appearances.")
            ratio = row.get("qualityStartsPct")
            if starts and (
                ratio is None or not isclose(ratio, quality_starts / starts, abs_tol=1.01e-6)
            ):
                raise ValueError("Official quality-start count and percentage disagree.")
            if not starts and (quality_starts or ratio not in (None, 0)):
                raise ValueError("A zero-start season cannot contain quality starts.")
            output[key] = {
                "games": games,
                "starts": starts,
                "quality_starts": quality_starts,
                "source_file": record["file"],
                "source_ordinal": ordinal,
                "source_sha256": record["sha256"],
            }
    return output


def load_quality(directory, expected, expected_league=None):
    """Return checked player counts and contemporaneous start-weighted league rates.

    NHL's reported quality start uses a fixed .900 save-percentage threshold, rather
    than Hockey-Reference's season-relative rule. Its raw fraction is not era-neutral;
    the caller should compare each season with this same-provider league fraction.
    """
    directory = Path(directory)
    manifest = inputs.read_json(directory / "manifest.json")
    for name, sha in manifest["outputs_sha256"].items():
        if inputs.digest(directory / name) != sha:
            raise ValueError("A preserved quality-start file differs from its manifest.")
    audit = inputs.read_json(directory / "coverage-audit.json")
    if not audit.get("quality_start_coverage_complete") or audit.get("quality_start_count_issues"):
        raise ValueError("The full-career quality-start count audit is incomplete.")
    players = _pages(directory, audit["records"])
    league_players = _pages(directory, audit["league_records"])
    if len(league_players) != audit["league_coverage"]["expected_player_seasons"]:
        raise ValueError("The quality-start league population is incomplete.")
    if set(players) != set(expected):
        raise ValueError("Quality-start seasons differ from the required goalie careers.")
    for key, row in players.items():
        if (row["games"], row["starts"]) != (expected[key]["games"], expected[key]["starts"]):
            raise ValueError(
                f"Quality-start appearances/starts differ from saved career totals: {key}."
            )
        league = league_players.get(key)
        if league is None or any(
            row[field] != league[field] for field in ("games", "starts", "quality_starts")
        ):
            raise ValueError(
                "Selected goalie counts differ from the contemporaneous league source."
            )
    seasons = {}
    for (_, season), row in league_players.items():
        total = seasons.setdefault(season, {"games": 0, "starts": 0, "quality_starts": 0})
        for field in total:
            total[field] += row[field]
    for season, total in seasons.items():
        if total["starts"] <= 0 or not 0 < total["quality_starts"] < total["starts"]:
            raise ValueError("League quality-start season has no valid exposure or variation.")
        total["quality_start_rate"] = total["quality_starts"] / total["starts"]
        if expected_league is not None and (
            season not in expected_league
            or total["games"] != expected_league[season]["games"]
            or total["starts"] != expected_league[season]["starts"]
        ):
            raise ValueError("League quality-start exposure differs from the saved league summary.")
    if expected_league is not None and set(seasons) != set(expected_league):
        raise ValueError("Quality-start league seasons differ from the requested season range.")
    return {
        "player_seasons": players,
        "league_seasons": seasons,
        "sources": [*audit["records"], *audit["league_records"]],
        "coverage": {
            "players": len({pid for pid, _ in players}),
            "player_seasons": len(players),
            "league_player_seasons": len(league_players),
            "league_seasons": len(seasons),
            "definition": audit.get("quality_definition"),
            "other_metric_disagreements": audit.get("issues", []),
        },
    }
