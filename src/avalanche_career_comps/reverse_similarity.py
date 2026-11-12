"""Compare one selected skater with eligible past and present Avalanche players."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy

from . import analysis, article_radar, era, inputs, lineup_radar, radar, special_teams
from .publication import BLUE, BURGUNDY, ICE, INK, _save, _style, plt

LABELS = article_radar.LABELS


def with_eligibility(bundle, minimum=82):
    """Apply the chosen tenure cutoff without changing the preserved source snapshot."""
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 50:
        raise ValueError("The Colorado minimum must be an integer of at least 50 games.")
    effective = deepcopy(bundle)
    effective["config"]["min_avs_skater_games"] = minimum
    return effective


def candidate_players(bundle, target_id):
    """Use the same Colorado tenure rule for both current and former candidates."""
    players = {p["player_id"]: p for p in bundle["players"]}
    if len(players) != len(bundle["players"]):
        raise ValueError("Duplicate frozen player ID.")
    target = players[target_id]
    group = analysis.position_group(target["position"])
    if group not in {"F", "D"}:
        raise ValueError("The reverse special-teams comparison supports skaters only.")
    return target, [
        p
        for p in bundle["players"]
        if p["player_id"] != target_id
        and analysis.position_group(p["position"]) == group
        and p["avs_games"] >= bundle["config"]["min_avs_skater_games"]
    ]


def compare(bundle, target_id, scoring, rates, ice_time):
    """Keep full observed careers, the existing era adjustment, and the PK rule."""
    last = bundle["config"]["last_season"]
    league = {r["season_id"]: r for r in bundle["league"]}
    builder = era.EraProfiles(bundle, special_teams.ERA_METHOD)
    factors = {sid: rates[last] / rate for sid, rate in rates.items()}

    def profile(player):
        base = builder(player, league, last, end_at_last_played=True)
        if base["nhl_games"] < 50:
            raise analysis.ProfileError("insufficient_nhl_games")
        history = {r["season_id"]: r for r in analysis.collapse_seasons(player, last)}
        return special_teams.pp_profile(base, history, scoring, factors)

    target_player, candidates = candidate_players(bundle, target_id)
    target = profile(target_player)
    pool, excluded = [], Counter()
    for player in candidates:
        try:
            pool.append(profile(player))
        except analysis.ProfileError as exc:
            excluded[str(exc)] += 1
    if len(pool) < 2:
        raise ValueError("The reverse comparison requires at least two eligible candidates.")
    matches, scales, details = special_teams.rank_without_lift(target, pool, ice_time)
    current_ids = {p["player_id"] for p in bundle["roster"]}
    return {
        "question": f"Which eligible past or present Avalanche skaters have observed NHL careers most similar to {target['name']}?",
        "window": "whole_career",
        "last_season": last,
        "target_id": target_id,
        "target_name": target["name"],
        "target_games": target["nhl_games"],
        "target_last_age": target["last_age"],
        "min_avs_skater_games": bundle["config"]["min_avs_skater_games"],
        "target_pk": special_teams.pk_context(target, ice_time),
        "candidate_ids": [p["player_id"] for p in pool],
        "excluded": dict(excluded),
        **details,
        "scales": scales,
        "matches": [
            {
                **{
                    k: p[k]
                    for k in (
                        "player_id",
                        "name",
                        "distance",
                        "contributions",
                        "nhl_games",
                        "last_age",
                        "avs_games",
                        "features",
                    )
                },
                "current_av": p["player_id"] in current_ids,
            }
            for p in matches
        ],
    }


def draw(report, out):
    """Use the compact article-row style, with explanatory text outside the image."""
    data = []
    for match in report["matches"][:3]:
        axes, distance = radar.axes_from_stats(
            report["target_features"],
            match,
            report["candidate_means"],
            report["scales"],
            report["weights"],
            LABELS,
        )
        data.append(
            {
                "current": report["target_name"],
                "historical": match["name"],
                "current_games": report["target_games"],
                "historical_games": match["nhl_games"],
                "axes": axes,
                "distance": distance,
            }
        )
    bounds = radar.radial_bounds([axis for row in data for axis in row["axes"]])
    _style()
    fig = plt.figure(figsize=(12, 5.0), facecolor=ICE)
    title = "Loosely, the Moose" if report["target_id"] == 8458520 else report["target_name"]
    fig.text(0.035, 0.91, title, fontsize=25, weight="bold", color=INK)
    fig.add_artist(
        plt.Line2D(
            [0.76, 0.795],
            [0.932, 0.932],
            color=BURGUNDY,
            lw=2.5,
            marker="o",
            markevery=[1],
            markersize=4,
            transform=fig.transFigure,
        )
    )
    fig.text(0.805, 0.918, report["target_name"], fontsize=11, weight="bold", color=BURGUNDY)
    for index, row in enumerate(data):
        left = 0.02 + index * 0.32
        fig.text(
            left + 0.16,
            0.80,
            f"{index + 1}. {row['historical']}",
            fontsize=17,
            weight="bold",
            color=BLUE,
            ha="center",
        )
        ax = fig.add_axes([left + 0.004, 0.035, 0.312, 0.69])
        lineup_radar.draw_radar(ax, {**row, "bounds": bounds}, font_size=15)
        if index:
            fig.add_artist(
                plt.Line2D(
                    [left, left], [0.04, 0.83], color="#D5E1E8", lw=0.8, transform=fig.transFigure
                )
            )
    _save(fig, out, "reverse-career-webs")


def checked_snapshot(path):
    manifest = inputs.read_json(path / "inputs.manifest.json")
    if inputs.digest(path / "inputs.json") != manifest["sha256"]:
        raise ValueError("Frozen snapshot checksum differs from its manifest.")
    return inputs.read_json(path / "inputs.json"), manifest
