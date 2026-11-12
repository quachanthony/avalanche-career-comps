"""Strict saved-source goalie starts and shutout inputs for performance comparisons.

Player records have one NHL player/season after intentionally adding legitimate
team stints. League records have one combined-team player/season before the
league aggregation. Missing values never become zero. This module performs no
network requests or warehouse writes and never changes a source snapshot.
"""

from __future__ import annotations

from pathlib import Path

from . import analysis, inputs
from .inputs import _integer

SHUTOUT_FEATURE = "era_relative_shutouts_per_100_starts"
QUALITY_FEATURE = "quality_starts_above_league_per_100_starts"
COUNT_FIELDS = ("games", "starts", "shutouts", "seconds", "shots_against", "goals_against")


def clock_seconds(value):
    """Parse the source's exact minutes:seconds duration without using rounded GAA."""
    if not isinstance(value, str):
        raise TypeError("Missing or invalid goalie timeOnIce clock.")
    parts = value.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError("Missing or invalid goalie timeOnIce clock.")
    minutes, seconds = map(int, parts)
    if seconds >= 60:
        raise ValueError("Invalid goalie timeOnIce seconds.")
    return 60 * minutes + seconds


def check_counts(row):
    """Protect count/exposure relationships while preserving true recorded zeroes."""
    for key in COUNT_FIELDS:
        _integer(row.get(key), key)
    if row["starts"] > row["games"] or row["shutouts"] > row["starts"]:
        raise ValueError("Goalie starts/shutouts exceed their exposures.")
    if row["goals_against"] > row["shots_against"]:
        raise ValueError("Goalie goals against exceed shots against.")
    if row["games"] > 0 and row["seconds"] <= 0:
        raise ValueError("Played goalie games have no recorded ice time.")


def landing_seasons(payload, last_season):
    """Collapse real team stints and reject combined rows or duplicate source identities."""
    pid = _integer(payload.get("playerId"), "playerId", positive=True)
    if payload.get("position") != "G":
        raise ValueError("The saved player landing is not a goalie.")
    totals, seen = {}, set()
    for raw in payload.get("seasonTotals", []):
        if raw.get("leagueAbbrev") != "NHL" or raw.get("gameTypeId") != 2:
            continue
        sid = _integer(raw.get("season"), "season", positive=True)
        if sid > last_season:
            continue
        team = raw.get("teamName", {}).get("default")
        if not team or "total" in team.lower() or team in {"TOT", "NHL"}:
            raise ValueError("Unexpected combined or missing goalie team scope.")
        identity = sid, team, raw.get("sequence")
        if identity in seen:
            raise ValueError("Duplicate goalie landing team-season identity.")
        seen.add(identity)
        row = {
            "games": _integer(raw.get("gamesPlayed"), "gamesPlayed"),
            "starts": _integer(raw.get("gamesStarted"), "gamesStarted"),
            "shutouts": _integer(raw.get("shutouts"), "shutouts"),
            "seconds": clock_seconds(raw.get("timeOnIce")),
            "shots_against": _integer(raw.get("shotsAgainst"), "shotsAgainst"),
            "goals_against": _integer(raw.get("goalsAgainst"), "goalsAgainst"),
        }
        check_counts(row)
        key = pid, sid
        target = totals.setdefault(key, {field: 0 for field in COUNT_FIELDS})
        for field in COUNT_FIELDS:
            target[field] += row[field]
    return totals


def league_seasons(rows, first_season, last_season):
    """Aggregate one all-team goalie-season row per player, never duplicate traded rows."""
    players, totals = {}, {}
    for raw in rows:
        pid = _integer(raw.get("playerId"), "playerId", positive=True)
        sid = _integer(raw.get("seasonId"), "seasonId", positive=True)
        if not first_season <= sid <= last_season:
            raise ValueError("A saved league goalie row is outside the requested cutoff.")
        key = pid, sid
        if key in players:
            raise ValueError("Duplicate combined-team goalie player-season in league reports.")
        row = {
            "games": _integer(raw.get("gamesPlayed"), "gamesPlayed"),
            "starts": _integer(raw.get("gamesStarted"), "gamesStarted"),
            "shutouts": _integer(raw.get("shutouts"), "shutouts"),
            "seconds": _integer(raw.get("timeOnIce"), "timeOnIce"),
            "shots_against": _integer(raw.get("shotsAgainst"), "shotsAgainst"),
            "goals_against": _integer(raw.get("goalsAgainst"), "goalsAgainst"),
        }
        check_counts(row)
        players[key] = row
        season = totals.setdefault(sid, {field: 0 for field in COUNT_FIELDS})
        for field in COUNT_FIELDS:
            season[field] += row[field]
    for row in totals.values():
        if row["starts"] <= 0:
            raise ValueError("A league season has no starts for a shutout reference rate.")
        row["shutout_rate"] = row["shutouts"] / row["starts"]
    return players, totals


def load_saved(bundle, original_snapshot, goalie_ids=None):
    """Read checked original landings/reports and reconcile them with frozen career totals."""
    root = Path(original_snapshot)
    manifest = inputs.read_json(root / "inputs.manifest.json")
    if inputs.digest(root / "inputs.json") != manifest["sha256"]:
        raise ValueError("The original career snapshot differs from its manifest.")
    source_index = {record["file"]: record for record in manifest["sources"]}
    if len(source_index) != len(manifest["sources"]):
        raise ValueError("The original source manifest has duplicate filenames.")
    last = bundle["config"]["last_season"]
    first = min(row["season_id"] for row in bundle["league"])
    current = {p["player_id"] for p in bundle["roster"]}
    players = {
        p["player_id"]: p
        for p in bundle["players"]
        if analysis.position_group(p["position"]) == "G"
    }
    if goalie_ids is None:
        goalie_ids = {
            pid
            for pid, p in players.items()
            if pid in current or p["avs_games"] >= bundle["config"]["min_avs_goalie_games"]
        }
    goalie_ids = set(goalie_ids)
    if not goalie_ids or not goalie_ids <= players.keys():
        raise ValueError("Requested goalie identities are absent from the frozen careers.")
    records = []

    def checked(name):
        if name not in source_index:
            raise ValueError(f"Missing source provenance for {name}.")
        record = source_index[name]
        path = root / "sources" / name
        if inputs.digest(path) != record["sha256"]:
            raise ValueError(f"Saved goalie source checksum differs for {name}.")
        records.append(dict(record))
        return inputs.read_json(path)

    player_seasons = {}
    for pid in sorted(goalie_ids):
        payload = checked(f"player-{pid}.json")
        if payload.get("playerId") != pid:
            raise ValueError("The saved goalie landing has a different NHL ID.")
        normalized = landing_seasons(payload, last)
        frozen = {(pid, r["season_id"]): r for r in analysis.collapse_seasons(players[pid], last)}
        if normalized.keys() != frozen.keys():
            raise ValueError("Goalie landing seasons differ from the frozen career window.")
        for key, row in normalized.items():
            if any(
                row[field] != frozen[key][field]
                for field in ("games", "shutouts", "shots_against", "goals_against")
            ):
                raise ValueError(f"Goalie landing counts differ from frozen career totals: {key}.")
        player_seasons.update(normalized)
    league_rows = []
    for name in sorted(source_index):
        if name.startswith("goalie-league-"):
            payload = checked(name)
            league_rows.extend(payload["data"])
    combined, league = league_seasons(league_rows, first, last)
    if set(league) != {r["season_id"] for r in bundle["league"]}:
        raise ValueError("League shutout references do not cover the frozen career calendar.")
    seconds_differences = []
    for key, landing in player_seasons.items():
        if key not in combined:
            raise ValueError(f"Missing combined goalie-season source: {key}.")
        summary = combined[key]
        if any(landing[field] != summary[field] for field in COUNT_FIELDS if field != "seconds"):
            raise ValueError(f"Landing and league goalie-season counts disagree: {key}.")
        if landing["seconds"] != summary["seconds"]:
            seconds_differences.append(
                {
                    "player_id": key[0],
                    "season_id": key[1],
                    "landing_seconds": landing["seconds"],
                    "summary_seconds": summary["seconds"],
                }
            )
    return {
        "player_seasons": player_seasons,
        "league_seasons": league,
        "sources": records,
        "source_snapshot_sha256": manifest["sha256"],
        "goalie_ids": sorted(goalie_ids),
        "league_player_season_count": len(combined),
        "cross_source_seconds_differences": seconds_differences,
        "seconds_source": "NHL Web landing timeOnIce; exact source disagreements are retained in the audit, not averaged.",
    }


def features(profile, saved, quality=None):
    """Calculate complete-window shutout and optional quality-start excess per 100 starts."""
    starts = shutouts = games = seconds = quality_starts = 0
    expected = 0.0
    expected_quality = 0.0
    for row in profile["path"]:
        key = profile["player_id"], row["season_id"]
        if key not in saved["player_seasons"]:
            raise analysis.ProfileError(f"missing_goalie_performance_season:{key}")
        known = saved["player_seasons"][key]
        if known["games"] != row["games"]:
            raise ValueError(f"Goalie performance games differ from the profile: {key}.")
        if row["season_id"] not in saved["league_seasons"]:
            raise analysis.ProfileError(f"missing_league_shutout_season:{key}")
        starts += known["starts"]
        shutouts += known["shutouts"]
        games += known["games"]
        seconds += known["seconds"]
        expected += known["starts"] * saved["league_seasons"][row["season_id"]]["shutout_rate"]
        if quality is not None:
            if key not in quality["player_seasons"]:
                raise analysis.ProfileError(f"missing_quality_start_season:{key}")
            q = quality["player_seasons"][key]
            if q["games"] != known["games"] or q["starts"] != known["starts"]:
                raise ValueError(f"Quality-start exposure differs from the goalie source: {key}.")
            count = _integer(q.get("quality_starts"), "quality_starts")
            if count > q["starts"]:
                raise ValueError("Quality starts exceed goalie starts.")
            quality_starts += count
            if row["season_id"] not in quality["league_seasons"]:
                raise analysis.ProfileError(f"missing_league_quality_start_season:{key}")
            reference = quality["league_seasons"][row["season_id"]]
            league_starts = _integer(reference.get("starts"), "league starts", positive=True)
            league_quality = _integer(reference.get("quality_starts"), "league quality starts")
            if league_quality > league_starts:
                raise ValueError("League quality starts exceed league starts.")
            expected_quality += known["starts"] * league_quality / league_starts
    if games != profile["nhl_games"] or starts <= 0:
        raise analysis.ProfileError("incomplete_goalie_performance_exposure")
    result = {SHUTOUT_FEATURE: 100 * (shutouts - expected) / starts}
    if quality is not None:
        result[QUALITY_FEATURE] = 100 * (quality_starts - expected_quality) / starts
    return {
        "features": result,
        "context": {
            "games": games,
            "starts": starts,
            "shutouts": shutouts,
            "seconds": seconds,
            "raw_shutouts_per_100_starts": 100 * shutouts / starts,
            "expected_shutouts_at_season_league_rates": expected,
            "quality_starts": quality_starts if quality is not None else None,
            "raw_quality_start_fraction": quality_starts / starts if quality is not None else None,
            "raw_quality_start_percentage": 100 * quality_starts / starts
            if quality is not None
            else None,
            "expected_quality_starts_at_season_league_rates": expected_quality
            if quality is not None
            else None,
            "quality_start_coverage_complete": quality is not None,
        },
    }
