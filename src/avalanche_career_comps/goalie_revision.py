"""Replace goalie career-volume features with complete, season-relative performance rates."""

from __future__ import annotations

from copy import deepcopy
from math import isclose
from statistics import mean

from . import analysis, article_analysis, era, goalie_performance, special_teams

WEIGHTS = {
    "relative_save_percentage": 0.25,
    "adjusted_shots_per_game": 0.25,
    goalie_performance.QUALITY_FEATURE: 0.25,
    goalie_performance.SHUTOUT_FEATURE: 0.25,
}


def revise(baseline, bundle, saved, quality):
    """Hold the eligible pools, skaters and source cutoff fixed while changing goalie features."""
    report = deepcopy(baseline)
    players = {p["player_id"]: p for p in bundle["players"]}
    last = bundle["config"]["last_season"]
    if last != baseline["config"]["last_season"]:
        raise ValueError(
            "The goalie revision and baseline have different completed-season cutoffs."
        )
    league = {r["season_id"]: r for r in bundle["league"]}
    builder = era.EraProfiles(bundle, special_teams.ERA_METHOD)
    for row in report["rows"]:
        if row["position"] != "G":
            continue
        whole = row["window"] == "whole_career"

        def profile(pid, *, target=False, whole=whole, age=row["age"]):
            result = builder(
                players[pid],
                league,
                last,
                max_age=None if whole or target else age,
                end_at_last_played=whole,
            )
            if result["nhl_games"] < 25:
                raise analysis.ProfileError("insufficient_goalie_appearances")
            addition = goalie_performance.features(result, saved, quality)
            if set(addition["features"]) != {
                goalie_performance.QUALITY_FEATURE,
                goalie_performance.SHUTOUT_FEATURE,
            }:
                raise ValueError("A goalie is missing a complete performance feature.")
            return {
                **result,
                "features": {**result["features"], **addition["features"]},
                "goalie_context": addition["context"],
            }

        target = profile(row["player_id"], target=True)
        if target["nhl_games"] != row["games"]:
            raise ValueError("The goalie revision changed the target's observed career exposure.")
        for key in ("relative_save_percentage", "adjusted_shots_per_game"):
            if not isclose(target["features"][key], row["target_features"][key], abs_tol=1e-12):
                raise ValueError("A retained goalie feature changed unexpectedly.")
        pool = [profile(pid) for pid in row["candidate_ids"]]
        for candidate in pool:
            if candidate["avs_games"] < baseline["config"]["min_avs_goalie_games"]:
                raise ValueError("A goalie candidate fails the unchanged Colorado tenure screen.")
        by_id = {p["player_id"]: p for p in pool}
        for old in row["matches"]:
            candidate = by_id[old["player_id"]]
            if candidate["nhl_games"] != old["games"] or any(
                not isclose(candidate["features"][key], old["features"][key], abs_tol=1e-12)
                for key in ("relative_save_percentage", "adjusted_shots_per_game")
            ):
                raise ValueError("A retained historical goalie profile changed unexpectedly.")
        ranked, scales = analysis._rank(target, pool, WEIGHTS)
        flags = []
        if len(pool) < 5:
            flags.append("small_comparison_pool")
        if ranked[0]["distance"] > 1.5:
            flags.append("distant_analogue")
        if not whole and ranked[0]["last_age"] < row["age"]:
            flags.append("comparison_ends_one_age_year_earlier")
        row.update(
            weights=dict(WEIGHTS),
            scales=scales,
            target_features={k: target["features"][k] for k in WEIGHTS},
            candidate_means={k: mean(p["features"][k] for p in pool) for k in WEIGHTS},
            ranked_candidate_ids=[p["player_id"] for p in pool],
            goalie_context=target["goalie_context"],
            quality_flags=flags,
            matches=[
                {
                    **{
                        k: p[k]
                        for k in ("name", "player_id", "distance", "contributions", "last_age")
                    },
                    "games": p["nhl_games"],
                    "avs_games": p["avs_games"],
                    "features": {k: p["features"][k] for k in WEIGHTS},
                    "goalie_context": p["goalie_context"],
                    "pk": None,
                }
                for p in ranked[:3]
            ],
        )
    report["goalie_method"] = {
        "name": "season-relative performance rates v1",
        "weights": dict(WEIGHTS),
        "replacement": {
            "schedule_adjusted_games_per_season": goalie_performance.QUALITY_FEATURE,
            "log_games": goalie_performance.SHUTOUT_FEATURE,
        },
        "quality_start_definition": "Official NHL goalie/advanced qualityStart count, based on its .900 save-percentage threshold; compared with that season's league frequency.",
        "quality_formula": "100 * (career QS - sum(season starts * league season QS / league season starts)) / career starts",
        "shutout_formula": "100 * (career SO - sum(season starts * league season SO / league season starts)) / career starts",
        "rate_units": "Excess events per 100 starts relative to each season's league; signed percentage-point differences.",
        "career_volume": "Appearances and starts retained as sample-size context, not weighted matching features.",
        "retained_features": "Save percentage above league and era-adjusted shots faced per appearance are unchanged.",
        "weight_policy": "Retain the baseline's 25% per feature to isolate the substitutions; no weights were tuned to get a preferred match.",
        "limitations": "Goalie/team defense and shot quality remain entangled; these are descriptive similarities, not GSAx or a pure ability model. The performance features are correlated.",
    }
    report["changes"] = article_analysis.compare_results(report, baseline)
    report["summary"] = {
        window: {
            "ranked_players": sum(r["window"] == window for r in report["rows"]),
            "unranked_players": sum(r["window"] == window for r in report["unranked"]),
            "changed_matches": sum(
                r["window"] == window and r["changed"] for r in report["changes"]
            ),
        }
        for window in article_analysis.WINDOWS
    }
    return report
