"""Publish a career-only, five-player Makar comparison with one shared statistical ruler."""

from __future__ import annotations

from html import escape
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


def consolidate(source, article):
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
    if set(case["weights"]) != set(FEATURE_LABELS):
        raise ValueError("The five-player comparison requires exactly the six shared career stats.")
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
    for previous in case["reference"]:
        actual = scores[previous["player_id"]]
        if not isclose(actual["distance"], previous["distance"], rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError(
                "Adding Makar changes a historical nearest match; review the benchmark."
            )
    typical = median(scores[pid]["distance"] for pid in features)
    if typical <= 0:
        raise ValueError("A positive historical median is needed for gap ratios.")
    if not isclose(typical, case["reference_median"], rel_tol=1e-12):
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
        "comparison_basis": "Six shared career statistics; PK omitted for every player because Bourque and Ozolinsh lack complete historical minutes.",
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
            "historical_gaps_changed_by_adding_target": False,
        },
        "roster_card_context": {
            "match": selected["matches"][0]["name"],
            "ranked_alumni": len(selected["ranked_candidate_ids"]),
            "pk_policy_unchanged": True,
        },
        "roster_rankings_changed": False,
    }


def article_copy(report):
    """Supply one concise explanation for both graphics, outside the images."""
    rows = report["isolation"]["rows"]
    current = rows[0]
    career_share = 100 * current["contributions"]["log_games"] / current["distance"] ** 2
    return (
        f"These charts compare full observed NHL regular-season careers through {report['cutoff']}. "
        "Makar is the bold burgundy line; all five players use the same statistical scales. "
        "Goals, assists, shots and power-play points are era-adjusted per 82 games; penalty minutes "
        "are unadjusted per 82, and career games enter the comparison on a logarithmic scale. "
        "PK minutes are omitted for everyone here because Bourque and Ozolinsh lack complete records. "
        f"Each player's closest counterpart is searched across the full {report['isolation']['neighbour_universe_count']}-player group, "
        f"which contains Makar and {report['isolation']['reference_count']} qualifying former Avs defensemen, excluding self-matches. "
        f"Makar's nearest counterpart is {current['nearest_name']}, but his gap is {current['ratio_to_median']:.1f} times "
        "the historical median. A bigger gap means a more unusual profile, not a better player. "
        f"These careers differ in length; career games account for {career_share:.0f}% of Makar's squared gap from {current['nearest_name'].split()[-1]}."
    )


def write_page(report, out):
    """Show exactly two figures and collapse supporting tables to reduce scrolling."""
    copy = article_copy(report)
    method = (
        "Using the same six stats, we found each player's closest statistical match. "
        "We divided that gap by the median closest-match gap among the "
        f"{report['isolation']['reference_count']} former Avs defensemen. "
        f"Makar's {report['isolation']['rows'][0]['ratio_to_median']:.1f}× means his nearest-match "
        "gap is that many times the typical gap. It measures how unusual his profile is, "
        "rather than how much better he is."
    )
    (out / "method-note.txt").write_text(method + "\n", encoding="utf-8")
    table_rows = "".join(
        f"<tr><th>{escape(report['feature_labels'][key])}</th>"
        + "".join(
            f"<td>{p['games']:,.0f}</td>"
            if key == "log_games"
            else f"<td>{p['features'][key]:.1f}</td>"
            for p in report["profiles"]
        )
        + "</tr>"
        for key in report["feature_order"]
    )
    headers = "".join(f"<th>{escape(p['name'])}</th>" for p in report["profiles"])
    gap_rows = "".join(
        f"<tr><th>{escape(p['name'])}</th><td>{escape(p['nearest_name'])}</td><td>{p['distance']:.3f}</td><td>{p['ratio_to_median']:.2f}×</td></tr>"
        for p in report["isolation"]["rows"]
    )
    (out / "article-copy.txt").write_text(copy + "\n", encoding="utf-8")
    (out / "index.html").write_text(
        f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cale and four career counterparts</title><style>body{{margin:0;background:#eff5f8;color:#182d3c;font:16px/1.5 system-ui}}main{{max-width:900px;margin:auto;padding:20px 14px}}h1{{font-size:30px;line-height:1.15;margin:0 0 12px}}img{{width:100%;display:block}}figure{{margin:18px 0}}figcaption{{font-size:14px;margin:6px 0 12px}}a{{color:#236192}}details{{margin:15px 0}}table{{border-collapse:collapse;font-size:14px;width:100%}}th,td{{border-bottom:1px solid #c7d9e4;padding:8px;text-align:left}}.scroll{{overflow:auto}}.copy{{background:white;padding:14px}}</style><main><h1>Cale and four career counterparts</h1>
<p>Full observed NHL careers through {report["cutoff"]}. Six shared stats, one scale for everyone. PK is omitted from these comparisons because Bourque and Ozolinsh have incomplete minutes.</p>
<figure><a href="five-player-radar.png"><img src="five-player-radar.png" alt="Five career profiles on one radar with Cale Makar highlighted in burgundy"></a><figcaption><a href="five-player-radar.png">Radar PNG</a> · <a href="five-player-radar.svg">SVG</a></figcaption></figure>
<figure><a href="five-player-isolation.png"><img src="five-player-isolation.png" alt="Nearest-match gap distribution for all 46 profiles, with Makar and four alumni highlighted"></a><figcaption><a href="five-player-isolation.png">Hard-to-match PNG</a> · <a href="five-player-isolation.svg">SVG</a></figcaption></figure>
<details><summary>Values, method and the roster-card distinction</summary><p>Alumni qualify with at least {report["primary_tenure"]} Colorado regular-season games. Their NHL careers across all teams count. All five use the same six-stat weights, historical alumni means and standard deviations, and common radar limits. The radar is a profile, not a percentage similarity.</p><p>For each player, find the nearest other profile among Makar and all {report["isolation"]["reference_count"]} eligible alumni, not just the five highlighted. Every player has {report["isolation"]["possible_matches_per_player"]} possible matches. Typical is the median historical nearest-match gap, {report["isolation"]["typical_gap"]:.3f}. Adding Makar to the historical players' search leaves their nearest-match gaps unchanged.</p><p>Under these shared-stat rules, Bourque is Makar's nearest counterpart. The separate roster card still uses PK minutes where coverage permits and selects {escape(report["roster_card_context"]["match"])}; the roster model has not been changed. A player's isolation does not establish overall quality, defensive value or NHL-wide uniqueness. Career length and late-career decline affect a full observed-career comparison.</p><div class="scroll"><table><tr><th>Stat</th>{headers}</tr>{table_rows}</table></div><div class="scroll"><table><tr><th>Player</th><th>Nearest other profile</th><th>Gap</th><th>Gap / typical</th></tr>{gap_rows}</table></div><p><a href="results.json">All calculated values</a> · <a href="manifest.json">Provenance and checksums</a></p></details>
<details><summary>One-time explanation for the article</summary><p class="copy">{escape(copy)}</p><p><a href="article-copy.txt">Copy-ready text</a></p><p class="copy">{escape(method)}</p><p><a href="method-note.txt">Short method explanation</a></p></details></main></html>""",
        encoding="utf-8",
    )
