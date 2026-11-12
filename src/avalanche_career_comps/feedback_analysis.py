"""Revise the article without excluding historical players for missing PK minutes."""

from __future__ import annotations

import argparse
import csv
from functools import partial
from pathlib import Path
from statistics import mean

from . import (
    analysis,
    article_analysis,
    distinctiveness,
    era,
    goalie_revision,
    inputs,
    makar_compact,
    pipeline,
    reverse_similarity,
    special_teams,
)


def production_weights(include_career_games=True):
    """Retain declared production-weight proportions; make career length an explicit choice."""
    selected = {
        key: value
        for key, value in special_teams.WITHOUT_LIFT.items()
        if include_career_games or key != "log_games"
    }
    total = sum(selected.values())
    return {key: value / total for key, value in selected.items()}


def rank_preserving_pool(target, pool, ice_time, *, include_career_games=True):
    """Omit an unavailable feature rather than exclude an otherwise eligible historical player."""
    weights = production_weights(include_career_games)
    target_pk = special_teams.pk_context(target, ice_time)
    contexts = {p["player_id"]: special_teams.pk_context(p, ice_time) for p in pool}
    complete = [pid for pid, context in contexts.items() if context["minutes_per_game"] is not None]
    incomplete = [pid for pid in contexts if pid not in complete]
    base, _ = analysis._rank(target, pool, weights)
    status = "pk_below_minimum"
    if target_pk["minutes_per_game"] is None:
        status = "target_pk_coverage_incomplete"
    elif target_pk["minutes_per_game"] >= special_teams.PK_MINIMUM:
        if incomplete:
            status = "pk_omitted_to_preserve_pool"
        elif len(pool) < 2:
            status = "insufficient_pk_candidates"
        else:
            status = "pk_included"
            weights = {
                **{key: value * 0.9 for key, value in weights.items()},
                special_teams.PK_FEATURE: 0.1,
            }
            target = {
                **target,
                "features": {
                    **target["features"],
                    special_teams.PK_FEATURE: target_pk["minutes_per_game"],
                },
            }
            pool = [
                {
                    **p,
                    "features": {
                        **p["features"],
                        special_teams.PK_FEATURE: contexts[p["player_id"]]["minutes_per_game"],
                    },
                }
                for p in pool
            ]
    matches, scales = analysis._rank(target, pool, weights)
    return (
        matches,
        scales,
        {
            "all_pool_without_pk_match": base[0]["name"],
            "same_pool_without_pk_match": base[0]["name"] if status == "pk_included" else None,
            "pk_status": status,
            "pk_pool_policy": "Omit PK unless every otherwise eligible candidate and the target have complete audited minutes; never remove candidates for PK coverage.",
            "pk_complete_candidate_ids": complete,
            "pk_incomplete_candidate_ids": incomplete,
            "ranked_candidate_ids": [p["player_id"] for p in pool],
            "weights": weights,
            "candidate_means": {key: mean(p["features"][key] for p in pool) for key in weights},
            "target_features": {key: target["features"][key] for key in weights},
        },
    )


def common_defender_report(bundle, scoring, rates, article, *, include_career_games=True):
    """Use exactly the roster's complete eligible defenseman pool for the Cale comparison."""
    last = bundle["config"]["last_season"]
    league = {r["season_id"]: r for r in bundle["league"]}
    builder = era.EraProfiles(bundle, special_teams.ERA_METHOD)
    factors = {sid: rates[last] / value for sid, value in rates.items()}
    players = {p["player_id"]: p for p in bundle["players"]}
    selected = next(
        r
        for r in article["rows"]
        if r["window"] == "whole_career" and r["player_id"] == makar_compact.TARGET
    )

    def profile(pid):
        player = players[pid]
        base = builder(player, league, last, end_at_last_played=True)
        history = {r["season_id"]: r for r in analysis.collapse_seasons(player, last)}
        return special_teams.pp_profile(base, history, scoring, factors)

    target = profile(makar_compact.TARGET)
    pool = [profile(pid) for pid in selected["candidate_ids"]]
    case = distinctiveness.neighbour_audit(target, pool, production_weights(include_career_games))
    source = {
        "cutoff": f"{str(last)[:4]}–{str(last)[-2:]}",
        "primary_tenure": bundle["config"]["min_avs_skater_games"],
        "windows": {
            "whole_career": {
                "cases": {"all_alumni_without_pk": case},
                "comparisons": [
                    {"player_id": p["player_id"], "games": p["nhl_games"]} for p in [target, *pool]
                ],
            }
        },
    }
    result = makar_compact.consolidate(source, article, strict_historical_benchmark=False)
    if result["isolation"]["rows"][0]["nearest_id"] != selected["matches"][0]["player_id"]:
        raise ValueError("The Cale overlay and roster must name the same nearest match.")
    result["roster_card_context"]["pk_policy_unchanged"] = False
    result.pop("roster_rankings_changed", None)
    result["rendering_changes_roster_rankings"] = False
    result["matches_consistent_with_roster"] = True
    result["career_games_weighted"] = include_career_games
    return result


def analyze(*, include_career_games=True):
    """Keep source records and goalie method fixed while making the proposed skater revision explicit."""
    bundle, scoring, rates, ice, goalie, manifest = pipeline.load()
    bundle, policy = article_analysis.with_skater_eligibility(bundle, 82)
    ranker = partial(rank_preserving_pool, include_career_games=include_career_games)
    baseline = {
        **article_analysis.rerun(bundle, scoring, rates, ice, skater_ranker=ranker),
        "config": bundle["config"],
        "roster": bundle["roster"],
        "window_order": list(article_analysis.WINDOWS),
        "era_method": "separate_assists",
        "hits_included": False,
        "eligibility_policy": policy,
    }
    roster = goalie_revision.revise(
        baseline, bundle, goalie["goalie_saved"], goalie["goalie_quality"]
    )
    # The goalie helper's old revision history is not the baseline for this new comparison.
    roster.pop("changes", None)
    roster.pop("summary", None)
    for row in roster["rows"]:
        if row["position"] != "G" and set(row["candidate_ids"]) != set(row["ranked_candidate_ids"]):
            raise ValueError("PK coverage must not exclude an eligible comparison.")
    reports = {
        "roster": roster,
        "makar": common_defender_report(
            bundle, scoring, rates, roster, include_career_games=include_career_games
        ),
        "forsberg": reverse_similarity.compare(
            bundle, 8458520, scoring, rates, ice, skater_ranker=ranker
        ),
    }
    reports["method_revision"] = {
        "pk_policy": "Preserve all otherwise eligible alumni; omit PK if the full comparison pool lacks complete audited coverage.",
        "career_games_weighted": include_career_games,
        "career_window": "Full observed careers primary; through-age analysis separate.",
        "goalie_method_changed": False,
        "source_data_changed": False,
    }
    return reports, manifest


def run(out, *, include_career_games=True, figures=True):
    """Save a separate reviewed revision and its exact changes from the published baseline."""
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError(
            "Choose an empty output directory to preserve earlier figures and results."
        )
    previous, _ = pipeline.analyze()
    pipeline.check_expected(
        pipeline.numerical_summary(previous),
        inputs.read_json(pipeline.PROJECT / "research/expected-results.json"),
    )
    reports, source = analyze(include_career_games=include_career_games)
    alternative, _ = analyze(include_career_games=not include_career_games)
    with_games, without_games = (
        (reports, alternative) if include_career_games else (alternative, reports)
    )
    changes = article_analysis.compare_results(reports["roster"], previous["roster"])
    reports["roster"]["changes"] = changes
    reports["roster"]["summary"] = {
        window: {
            "changed_matches": sum(r["changed"] for r in changes if r["window"] == window),
            "baseline": "Original published model, including its PK pool restriction and career length",
        }
        for window in article_analysis.WINDOWS
    }
    out.mkdir(parents=True, exist_ok=True)
    for name, report in reports.items():
        inputs.write_json(out / f"{name}-results.json", report)
    inputs.write_json(out / "changes.json", changes)
    indices = [
        {(r["window"], r["player_id"]): r for r in model["roster"]["rows"]}
        for model in (previous, with_games, without_games)
    ]
    with (out / "career-length-sensitivity.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            (
                "window",
                "player",
                "old_restricted_match",
                "pool_preserved_with_GP",
                "pool_preserved_without_GP",
                "old_gap",
                "with_GP_gap",
                "without_GP_gap",
                "eligible_alumni",
                "old_ranked_alumni",
            )
        )
        for key, old in indices[0].items():
            candidates = [table[key] for table in indices]
            writer.writerow(
                (
                    key[0],
                    old["name"],
                    *(r["matches"][0]["name"] for r in candidates),
                    *(r["matches"][0]["distance"] for r in candidates),
                    len(old["candidate_ids"]),
                    len(old["ranked_candidate_ids"]),
                )
            )
    inputs.write_json(
        out / "sensitivity-summary.json",
        {
            "selected_career_games_weighted": include_career_games,
            "with_career_games": {
                "cale": with_games["makar"]["isolation"],
                "forsberg_first_three": with_games["forsberg"]["matches"][:3],
            },
            "without_career_games": {
                "cale": without_games["makar"]["isolation"],
                "forsberg_first_three": without_games["forsberg"]["matches"][:3],
            },
            "interpretation": "These controlled descriptive sensitivities are not a tuning search or predictive validation; source records, eligibility and goalie methods are fixed.",
        },
    )
    with (out / "changes.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(changes[0]))
        writer.writeheader()
        writer.writerows(changes)
    if figures:
        from . import feedback_graphics

        feedback_graphics.render(reports, out)
    from . import feedback_copy

    feedback_copy.write(reports, out)
    inputs.write_json(
        out / "manifest.json",
        {
            "input_sha256": source["sha256"],
            "method_revision": reports["method_revision"],
            "code_sha256": {
                p.name: inputs.digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))
            },
            "outputs_sha256": {
                str(p.relative_to(out)): inputs.digest(p)
                for p in sorted(out.rglob("*"))
                if p.is_file()
            },
            "warehouse_writes": False,
            "network_requests": False,
        },
    )
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--omit-career-games", action="store_true")
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args()
    reports = run(
        args.out, include_career_games=not args.omit_career_games, figures=not args.no_figures
    )
    print("Cale nearest match:", reports["makar"]["isolation"]["rows"][0])
    print("Saved revised article package under", args.out)


if __name__ == "__main__":
    main()
