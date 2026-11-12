"""Publish a career-only, five-player Makar comparison with one shared statistical ruler."""

from __future__ import annotations

from math import ceil, floor, isclose
from statistics import median

from . import distinctiveness, makar_deep_dive

TARGET = makar_deep_dive.TARGET
DISPLAY_IDS = (
    TARGET,
    makar_deep_dive.BOURQUE,
    makar_deep_dive.BARRIE,
    makar_deep_dive.OZOLINSH,
    makar_deep_dive.LILES,
)
FEATURE_LABELS = {
    "goals_per_82": "Goals / 82",
    "assists_per_82": "Assists / 82",
    "shots_per_82": "Shots / 82",
    "pim_per_82": "PIM / 82",
    "log_games": "Career games",
    "adjusted_pp_points_per_82": "PP points / 82",
}


def consolidate(source, article, *, strict_historical_benchmark=True):
    """Reuse complete careers and give all displayed players the same matching universe."""
    data = source["windows"]["whole_career"]
    case = data["cases"]["all_alumni_without_pk"]
    if case["k"] != 1:
        raise ValueError("The compact comparison requires the nearest other player.")
    selected = next(
        r for r in article["rows"] if r["window"] == "whole_career" and r["player_id"] == TARGET
    )
    features = {int(pid): dict(values) for pid, values in case["reference_features"].items()}
    if set(features) != set(selected["candidate_ids"]) or TARGET in features:
        raise ValueError("The shared-stat cohort differs from the selected full-career alumni.")
    features_without_games = set(FEATURE_LABELS) - {"log_games"}
    if set(case["weights"]) not in (set(FEATURE_LABELS), features_without_games):
        raise ValueError("The five-player comparison requires the shared production statistics.")
    if source["primary_tenure"] != article["config"]["min_avs_skater_games"]:
        raise ValueError("The diagnostic and article use different eligibility cutoffs.")
    names = {p["player_id"]: p["name"] for p in case["reference"]}
    names[TARGET] = "Cale Makar"
    all_features = {**features, TARGET: dict(case["target_features"])}
    scores = {}
    # Each profile has exactly n-1 opportunities, with self-matches excluded.
    # The normalizing ruler stays fitted to the historical alumni only.
    for pid, values in all_features.items():
        ranked = []
        for other, other_values in all_features.items():
            if other == pid:
                continue
            gap, contributions = distinctiveness.distance(
                {"features": values}, {"features": other_values}, case["weights"], case["scales"]
            )
            ranked.append((gap, other, contributions))
        gap, other, contributions = min(ranked, key=lambda p: (p[0], p[1]))
        scores[pid] = {
            "player_id": pid,
            "name": names[pid],
            "nearest_id": other,
            "nearest_name": names[other],
            "distance": gap,
            "contributions": contributions,
        }
    if not isclose(scores[TARGET]["distance"], case["target_distance"], rel_tol=1e-12):
        raise ValueError("Makar's career-only gap differs from its saved calculation.")
    changed_historical_neighbours = []
    for previous in case["reference"]:
        actual = scores[previous["player_id"]]
        if not isclose(actual["distance"], previous["distance"], rel_tol=1e-12, abs_tol=1e-12):
            changed_historical_neighbours.append(previous["player_id"])
            if strict_historical_benchmark:
                raise ValueError(
                    "Adding Makar changes a historical nearest match; review the benchmark."
                )
    typical = median(scores[pid]["distance"] for pid in features)
    if typical <= 0:
        raise ValueError("A positive historical median is needed for gap ratios.")
    if strict_historical_benchmark and not isclose(
        typical, case["reference_median"], rel_tol=1e-12
    ):
        raise ValueError("The common historical gap benchmark changed.")
    compared = {p["player_id"]: p for p in data["comparisons"]}
    profiles = []
    for pid in DISPLAY_IDS:
        if pid not in compared or pid not in all_features:
            raise ValueError("A requested player lacks a complete full-career profile.")
        values = all_features[pid]
        profiles.append(
            {
                "player_id": pid,
                "name": names[pid],
                "games": compared[pid]["games"],
                "features": values,
                "z_scores": {
                    key: (values[key] - case["candidate_means"][key]) / case["scales"][key]
                    for key in case["weights"]
                },
            }
        )
    coordinates = [z for p in profiles for z in p["z_scores"].values()]
    isolation_rows = [
        dict(scores[pid], ratio_to_median=scores[pid]["distance"] / typical) for pid in DISPLAY_IDS
    ]
    return {
        "question": "How do Makar's observed career profile and closest-match gap compare with Bourque, Barrie, Ozolinsh and Liles?",
        "window": "whole_career",
        "cutoff": source["cutoff"],
        "primary_tenure": source["primary_tenure"],
        "grain": "One complete observed NHL regular-season career per player, all NHL teams; no age truncation.",
        "comparison_basis": f"{len(case['weights'])} shared career statistics; PK omitted for every player because the full historical cohort lacks complete minutes.",
        "profiles": profiles,
        "feature_order": list(case["weights"]),
        "feature_labels": FEATURE_LABELS,
        "weights": case["weights"],
        "candidate_means": case["candidate_means"],
        "scales": case["scales"],
        "radial_bounds": [min(-2, floor(min(coordinates))), max(4, ceil(max(coordinates)))],
        "isolation": {
            "typical_gap": typical,
            "reference_count": len(features),
            "neighbour_universe_count": len(all_features),
            "rows": isolation_rows,
            "historical_reference": [scores[pid] for pid in sorted(features)],
            "ruler_fitted_to": "Eligible historical alumni only; the same means, spreads and weights apply to all five displayed profiles.",
            "self_matches": False,
            "possible_matches_per_player": len(features),
            "historical_gaps_changed_by_adding_target": bool(changed_historical_neighbours),
            "changed_historical_neighbours": changed_historical_neighbours,
            "historical_only_typical_gap": case["reference_median"],
        },
        "roster_card_context": {
            "match": selected["matches"][0]["name"],
            "ranked_alumni": len(selected["ranked_candidate_ids"]),
            "pk_policy_unchanged": True,
        },
        "roster_rankings_changed": False,
    }
