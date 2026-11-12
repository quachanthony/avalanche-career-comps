"""Rerank saved skater comparisons using power-play points in place of debut age."""

from __future__ import annotations

from statistics import mean

from . import analysis

PP_FEATURE = "adjusted_pp_points_per_82"
PK_FEATURE = "pk_minutes_per_game"
PK_MINIMUM = 1.0
WEIGHTS = {
    PP_FEATURE if key == "debut_age" else key: weight
    for key, weight in analysis.SKATER_WEIGHTS.items()
}
WITHOUT_DEBUT = {
    key: weight for key, weight in analysis.SKATER_WEIGHTS.items() if key != "debut_age"
}
WITHOUT_LIFT = {key: weight for key, weight in WEIGHTS.items() if key != "scoring_trajectory"}
ERA_METHOD = "separate_assists"


def pp_profile(profile, history, scoring, factors):
    """Sum strength counts at matched player-season grain before dividing by games."""
    adjusted_points = 0
    for season in profile["path"]:
        sid = season["season_id"]
        row = scoring[profile["player_id"], sid]
        frozen = history[sid]
        if (row["gamesPlayed"], row["goals"], row["assists"]) != (
            frozen["games"],
            frozen["goals"],
            frozen["assists"],
        ):
            raise ValueError(
                f"Power-play source and frozen career disagree for {profile['name']} {sid}."
            )
        adjusted_points += row["ppPoints"] * factors[sid]
    return {
        **profile,
        "features": {
            **profile["features"],
            PP_FEATURE: 82 * adjusted_points / profile["nhl_games"],
        },
    }


def pk_context(profile, minutes):
    seconds, covered_games = 0, 0
    for row in profile["path"]:
        key = profile["player_id"], row["season_id"]
        if key in minutes:
            games, value = minutes[key]
            if games != row["games"]:
                raise ValueError(f"Ice-time games differ from career games at {key}.")
            seconds += value
            covered_games += games
    games = profile["nhl_games"]
    return {
        "minutes_per_game": seconds / 60 / games if covered_games == games else None,
        "covered_games": covered_games,
        "total_games": games,
    }


def rank_without_lift(target, pool, ice_time):
    """Use audited PK minutes for regular penalty killers and preserve pool controls."""
    matches, scales = analysis._rank(target, pool, WITHOUT_LIFT)
    status = "pk_below_minimum"
    pk = pk_context(target, ice_time)["minutes_per_game"]
    details = {"all_pool_without_pk_match": matches[0]["name"], "same_pool_without_pk_match": None}
    weights = WITHOUT_LIFT
    if pk is None:
        status = "target_pk_coverage_incomplete"
    elif pk >= PK_MINIMUM:
        covered = []
        for candidate in pool:
            value = pk_context(candidate, ice_time)["minutes_per_game"]
            if value is not None:
                covered.append(
                    {**candidate, "features": {**candidate["features"], PK_FEATURE: value}}
                )
        status = "insufficient_pk_candidates"
        if len(covered) >= 2:
            status = "pk_included"
            pool = covered
            weights = {**WITHOUT_LIFT, PK_FEATURE: WEIGHTS["scoring_trajectory"]}
            target = {**target, "features": {**target["features"], PK_FEATURE: pk}}
            control, _ = analysis._rank(target, pool, WITHOUT_LIFT)
            details["same_pool_without_pk_match"] = control[0]["name"]
            matches, scales = analysis._rank(target, pool, weights)
    total_weight = sum(weights.values())
    return (
        matches,
        scales,
        {
            **details,
            "pk_status": status,
            "ranked_candidate_ids": [p["player_id"] for p in pool],
            "weights": {key: weight / total_weight for key, weight in weights.items()},
            "candidate_means": {key: mean(p["features"][key] for p in pool) for key in weights},
            "target_features": {key: target["features"][key] for key in weights},
        },
    )
