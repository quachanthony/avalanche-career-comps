"""Recompute the selected article model against a verified warehouse publication."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from math import isclose
from statistics import mean

from . import analysis, era, inputs, special_teams

WINDOWS = ("whole_career", "age_aligned")
DEFAULT_SKATER_TENURE = 82


def with_skater_eligibility(bundle, minimum=DEFAULT_SKATER_TENURE):
    """Apply the article's tenure choice without rewriting the frozen source snapshot."""
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum <= 0:
        raise ValueError("The Colorado skater minimum must be a positive integer.")
    effective = deepcopy(bundle)
    effective["config"]["min_avs_skater_games"] = minimum
    effective["config"]["question"] = (
        "For each current Colorado player, which eligible former Avalanche player has the "
        "most similar full observed NHL career, with a separate through-age comparison?"
    )
    policy = {
        "base_config": deepcopy(bundle["config"]),
        "effective_config": deepcopy(effective["config"]),
        "reason": (
            "User-selected Colorado regular-season skater tenure screen; 82 games is one "
            "full standard season. The goalie tenure screen and other model settings are unchanged; "
            "the question label explicitly names the two independent career windows."
        ),
        "frozen_source_modified": False,
    }
    return effective, policy


def check_warehouse_audit(audit, input_sha):
    """Do not publish a rerun while the new warehouse disagrees with career inputs."""
    if audit["provenance"]["input_sha256"] != input_sha:
        raise ValueError("The warehouse audit used a different frozen career snapshot.")
    if not audit["core_state"]["input_fingerprint"] or audit.get("scope_issues"):
        raise ValueError("The warehouse audit has no publication fingerprint or has scope issues.")
    for key in (
        "all_league_skater_summary",
        "project_skater_careers",
        "project_goalie_careers",
        "special_teams_points",
    ):
        item = audit[key]
        if (
            item["expected"] <= 0
            or item["counts"].get("agree", 0) != item["expected"]
            or item.get("issues")
        ):
            raise ValueError(f"Warehouse reconciliation is incomplete or disagrees: {key}.")
    if not audit["league_environments"] or not all(
        r["agrees"] for r in audit["league_environments"]
    ):
        raise ValueError("The warehouse and frozen league environments disagree.")


def rerun(bundle, scoring, rates, ice_time, *, skater_ranker=None):
    """Use the selected PP/PK method directly, with independent career windows."""
    last = bundle["config"]["last_season"]
    players = {p["player_id"]: p for p in bundle["players"]}
    if len(players) != len(bundle["players"]):
        raise ValueError("Duplicate player identity in the frozen careers.")
    league = {r["season_id"]: r for r in bundle["league"]}
    builder = era.EraProfiles(bundle, special_teams.ERA_METHOD)
    factors = {sid: rates[last] / value for sid, value in rates.items()}
    histories = {
        pid: {r["season_id"]: r for r in analysis.collapse_seasons(player, last)}
        for pid, player in players.items()
    }
    current = {p["player_id"] for p in bundle["roster"]}

    def profile(player, *, whole, age=None):
        result = builder(player, league, last, max_age=age, end_at_last_played=whole)
        minimum = 25 if result["position"] == "G" else 50
        if result["nhl_games"] < minimum:
            raise analysis.ProfileError("insufficient_nhl_games")
        if result["position"] != "G":
            result = special_teams.pp_profile(
                result, histories[player["player_id"]], scoring, factors
            )
        return result

    rows, unranked = [], []
    for window in WINDOWS:
        whole = window == "whole_career"
        for roster in bundle["roster"]:
            pid = roster["player_id"]
            try:
                player = players[pid]
                age = analysis.season_age(player["birth_date"], last)
                target = profile(player, whole=whole)
            except (KeyError, analysis.ProfileError) as exc:
                unranked.append(
                    {"window": window, **roster, "status": "insufficient_data", "reason": str(exc)}
                )
                continue
            group = target["position"]
            tenure = bundle["config"][
                "min_avs_goalie_games" if group == "G" else "min_avs_skater_games"
            ]
            pool, excluded = [], Counter()
            for candidate in bundle["players"]:
                if (
                    candidate["player_id"] in current
                    or analysis.position_group(candidate["position"]) != group
                    or candidate["avs_games"] < tenure
                ):
                    continue
                try:
                    pool.append(profile(candidate, whole=whole, age=None if whole else age))
                except analysis.ProfileError as exc:
                    excluded[str(exc)] += 1
            if not pool:
                unranked.append(
                    {
                        "window": window,
                        **roster,
                        "status": "no_eligible_comparison",
                        "reason": "No available eligible career profiles.",
                    }
                )
                continue
            if group == "G":
                weights = analysis.GOALIE_WEIGHTS
                ranked, scales = analysis._rank(target, pool, weights)
                details = {
                    "pk_status": "not_applicable_goalie",
                    "weights": weights,
                    "target_features": {key: target["features"][key] for key in weights},
                    "candidate_means": {
                        key: mean(p["features"][key] for p in pool) for key in weights
                    },
                    "ranked_candidate_ids": [p["player_id"] for p in pool],
                }
                target_pk = None
            else:
                ranker = skater_ranker or special_teams.rank_without_lift
                ranked, scales, details = ranker(target, pool, ice_time)
                target_pk = special_teams.pk_context(target, ice_time)
            best = ranked[0]
            flags = []
            if len(details["ranked_candidate_ids"]) < 5:
                flags.append("small_comparison_pool")
            if best["distance"] > 1.5:
                flags.append("distant_analogue")
            if not whole and best["last_age"] < age:
                flags.append("comparison_ends_one_age_year_earlier")
            rows.append(
                {
                    "window": window,
                    "player_id": pid,
                    "name": target["name"],
                    "position": group,
                    "age": age,
                    "games": target["nhl_games"],
                    "candidate_ids": [p["player_id"] for p in pool],
                    "excluded_reasons": dict(excluded),
                    "scales": scales,
                    "pk": target_pk,
                    "quality_flags": flags,
                    **details,
                    "matches": [
                        {
                            **{
                                key: match[key]
                                for key in (
                                    "name",
                                    "player_id",
                                    "distance",
                                    "contributions",
                                    "last_age",
                                )
                            },
                            "games": match["nhl_games"],
                            "avs_games": match["avs_games"],
                            "features": {key: match["features"][key] for key in details["weights"]},
                            "pk": None
                            if group == "G"
                            else special_teams.pk_context(match, ice_time),
                        }
                        for match in ranked[:3]
                    ],
                }
            )
    return {"rows": rows, "unranked": unranked}


def compare_prior(report, previous_skaters, previous_era):
    """Separate actual result changes from a new database audit and presentation."""
    prior = {(r["window"], r["player_id"]): r for r in previous_skaters["rows"]}
    for window in WINDOWS:
        for row in previous_era["windows"][window][special_teams.ERA_METHOD]["results"]:
            if row["position"] == "G" and row["matches"]:
                prior[window, row["player_id"]] = {
                    **row,
                    "window": window,
                    "weights": row["feature_weights"],
                    "ranked_candidate_ids": row["candidate_ids"],
                }
    return compare_results(report, {"rows": list(prior.values())})


def compare_results(report, previous_report):
    """Compare an eligibility rerun directly with the selected article baseline."""
    prior = {(r["window"], r["player_id"]): r for r in previous_report["rows"]}
    changes = []
    for row in report["rows"]:
        key = row["window"], row["player_id"]
        if key not in prior:
            raise ValueError(f"The baseline lacks a ranked player/window: {key}.")
        old = prior[key]
        top = row["matches"][0]
        previous = old["matches"][0]
        changes.append(
            {
                "window": row["window"],
                "player_id": row["player_id"],
                "name": row["name"],
                "previous_match": previous["name"],
                "updated_match": top["name"],
                "previous_match_id": previous["player_id"],
                "updated_match_id": top["player_id"],
                "previous_distance": previous["distance"],
                "updated_distance": top["distance"],
                "changed": previous["player_id"] != top["player_id"],
                "previous_eligible_candidates": len(old["candidate_ids"]),
                "updated_eligible_candidates": len(row["candidate_ids"]),
                "previous_ranked_candidates": len(old["ranked_candidate_ids"]),
                "updated_ranked_candidates": len(row["ranked_candidate_ids"]),
                "eligible_candidates_added": sorted(
                    set(row["candidate_ids"]) - set(old["candidate_ids"])
                ),
                "eligible_candidates_removed": sorted(
                    set(old["candidate_ids"]) - set(row["candidate_ids"])
                ),
                "ranked_candidates_added": sorted(
                    set(row["ranked_candidate_ids"]) - set(old["ranked_candidate_ids"])
                ),
                "ranked_candidates_removed": sorted(
                    set(old["ranked_candidate_ids"]) - set(row["ranked_candidate_ids"])
                ),
                "candidate_pool_changed": set(old["ranked_candidate_ids"])
                != set(row["ranked_candidate_ids"]),
                "weights_changed": old["weights"] != row["weights"],
                "score_changed": not isclose(
                    previous["distance"], top["distance"], rel_tol=1e-12, abs_tol=1e-12
                ),
            }
        )
    return changes


def checked_snapshot(directory):
    manifest = inputs.read_json(directory / "inputs.manifest.json")
    if inputs.digest(directory / "inputs.json") != manifest["sha256"]:
        raise ValueError("Input snapshot checksum differs from its manifest.")
    return inputs.read_json(directory / "inputs.json"), manifest
