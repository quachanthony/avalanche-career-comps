"""Benchmark one player's nearest-match gap against a fixed historical peer cohort."""

from __future__ import annotations

from math import isfinite, sqrt
from statistics import mean, median, pstdev


def distance(left, right, weights, scales):
    """Use the same frozen ruler for the target and every historical pair."""
    contributions = {
        key: weight * ((left["features"][key] - right["features"][key]) / scales[key]) ** 2
        for key, weight in weights.items()
    }
    return sqrt(sum(contributions.values())), contributions


def neighbour_audit(target, reference, weights, *, k=1):
    """Compare a new profile with self-excluded historical neighbour distances.

    These are descriptive reference scores, not exchangeable conformal scores or
    p-values. Reference moments are held fixed, not re-estimated for each pair.
    The target has n possible matches; each reference player has n-1, which gives
    the target one extra opportunity to find a close match.
    """
    ids = [p["player_id"] for p in reference]
    if len(ids) != len(set(ids)) or target["player_id"] in ids:
        raise ValueError("Reference identities must be unique and exclude the target.")
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k < len(reference):
        raise ValueError("Neighbour order requires at least k+1 reference players.")
    if not weights or any(not isfinite(v) or v <= 0 for v in weights.values()):
        raise ValueError("Feature weights must be finite and positive.")
    total = sum(weights.values())
    weights = {key: value / total for key, value in weights.items()}
    for player in [target, *reference]:
        if any(not isfinite(player["features"][key]) for key in weights):
            raise ValueError("Nonfinite career feature.")
    scales = {key: pstdev(p["features"][key] for p in reference) or 1.0 for key in weights}

    def ordered(player, pool):
        scored = []
        for peer in pool:
            if peer["player_id"] == player["player_id"]:
                continue
            gap, contributions = distance(player, peer, weights, scales)
            scored.append(
                {
                    "player_id": peer["player_id"],
                    "name": peer["name"],
                    "distance": gap,
                    "contributions": contributions,
                }
            )
        return sorted(scored, key=lambda row: (row["distance"], row["player_id"]))

    target_ranked = ordered(target, reference)
    references = []
    for player in reference:
        ranked = ordered(player, reference)
        references.append(
            {
                "player_id": player["player_id"],
                "name": player["name"],
                "distance": ranked[k - 1]["distance"],
                "neighbour": ranked[k - 1],
            }
        )
    typical = median(p["distance"] for p in references)
    score = target_ranked[k - 1]["distance"]
    return {
        "k": k,
        "reference_count": len(reference),
        "weights": weights,
        "scales": scales,
        "candidate_means": {key: mean(p["features"][key] for p in reference) for key in weights},
        "target_distance": score,
        "target_neighbour": target_ranked[k - 1],
        "closest_match": target_ranked[0],
        "target_rankings": target_ranked,
        "reference_median": typical,
        "reference_max": max(p["distance"] for p in references),
        "ratio_to_median": score / typical if typical > 0 else None,
        "reference_gaps_below_target": sum(p["distance"] < score for p in references),
        "reference_gaps_tied_target": sum(p["distance"] == score for p in references),
        "reference": sorted(references, key=lambda row: (row["distance"], row["player_id"])),
        "target_features": {key: target["features"][key] for key in weights},
        "reference_features": {
            p["player_id"]: {key: p["features"][key] for key in weights} for p in reference
        },
        "interpretation": "Descriptive nearest-neighbour isolation within this historical franchise cohort; not a p-value, probability, or measure of overall player quality.",
    }
