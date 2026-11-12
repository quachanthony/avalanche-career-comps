"""Explain Makar's scoring gaps while keeping the article and coverage controls separate."""

from __future__ import annotations

from math import isclose

from . import (
    analysis,
    article_radar,
    distinctiveness,
    era,
    radar,
    special_teams,
)

TARGET = 8480069
BARRIE = 8475197
OZOLINSH = 8458544
BOURQUE = 8445621
LILES = 8468639
SCORING = ("goals_per_82", "assists_per_82", "adjusted_pp_points_per_82")
DISPLAY_RATES = (*SCORING, "shots_per_82")
LABELS = {
    "goals_per_82": "Goals / 82",
    "assists_per_82": "Assists / 82",
    "adjusted_pp_points_per_82": "PP points / 82",
    "shots_per_82": "Shots / 82",
}


def primary_pool(available, article):
    """Use the selected article's effective tenure rule without editing frozen inputs."""
    tenure = article["config"]["min_avs_skater_games"]
    if isinstance(tenure, bool) or not isinstance(tenure, int) or tenure <= 0:
        raise ValueError("The article's Colorado skater-game threshold must be a positive integer.")
    return tenure, [p for p in available if p["avs_games"] >= tenure]


def compare_rates(target, reference):
    """Rank actual adjusted rates and retain the strongest historical comparator."""
    result = {}
    for key in DISPLAY_RATES:
        ranked = sorted(reference, key=lambda p: (-p["features"][key], p["player_id"]))
        value = target["features"][key]
        leader = ranked[0]
        result[key] = {
            "target": value,
            "historical_max": leader["features"][key],
            "historical_leader": leader["name"],
            "target_rank": 1 + sum(p["features"][key] > value for p in reference),
            "historical_profiles_below": sum(p["features"][key] < value for p in reference),
            "historical_profiles_tied": sum(p["features"][key] == value for p in reference),
        }
    return result


def gap_shares(case):
    """Explain squared distance, without treating overlapping scoring stats as independent."""
    contributions = case["closest_match"]["contributions"]
    total = sum(contributions.values())
    return {key: value / total if total else 0.0 for key, value in contributions.items()}


def reconcile_article(case, target, reference, selected):
    """Require the new diagnostic to reproduce the actual card's pool and ruler."""
    if {p["player_id"] for p in reference} != set(selected["ranked_candidate_ids"]):
        raise ValueError("The diagnostic's article pool differs from the saved card.")
    if case["closest_match"]["player_id"] != selected["matches"][0]["player_id"]:
        raise ValueError("The diagnostic's match differs from the saved card.")
    if not isclose(case["target_distance"], selected["matches"][0]["distance"], rel_tol=1e-12):
        raise ValueError("The diagnostic's distance differs from the saved card.")
    for key, weight in selected["weights"].items():
        checks = (
            (case["weights"][key], weight),
            (case["scales"][key], selected["scales"][key]),
            (target["features"][key], selected["target_features"][key]),
        )
        if any(not isclose(a, b, rel_tol=1e-12, abs_tol=1e-12) for a, b in checks):
            raise ValueError(f"The diagnostic's article feature/ruler differs for {key}.")


def comparison_radars(data):
    """Compare Barrie and Liles with the identical article ruler and radial bounds."""
    case = data["cases"]["article"]
    players = {p["player_id"]: p for p in data["comparisons"]}
    ranked = {p["player_id"]: p for p in case["target_rankings"]}
    charts = []
    for pid in dict.fromkeys((case["closest_match"]["player_id"], LILES)):
        if pid not in ranked:
            raise ValueError("A requested radar comparator lacks complete article-model features.")
        features = case["reference_features"]
        historical = features[pid] if pid in features else features[str(pid)]
        axes, distance = radar.axes_from_stats(
            case["target_features"],
            {"features": historical, "distance": ranked[pid]["distance"]},
            case["candidate_means"],
            case["scales"],
            case["weights"],
            article_radar.LABELS,
        )
        charts.append(
            {
                "player_id": TARGET,
                "window": data["window"],
                "current": data["target_name"],
                "historical": players[pid]["name"],
                "current_age": data["age"],
                "current_games": players[TARGET]["games"],
                "historical_games": players[pid]["games"],
                "historical_id": pid,
                "article_rank": players[pid]["article_rank"],
                "axes": axes,
                "distance": distance,
            }
        )
    bounds = radar.radial_bounds([axis for chart in charts for axis in chart["axes"]])
    for chart in charts:
        chart["bounds"] = bounds
    return charts


def analyze(bundle, scoring, rates, ice_time, article):
    """Rebuild two independent career windows, with three explicitly distinct controls."""
    last = bundle["config"]["last_season"]
    players = {p["player_id"]: p for p in bundle["players"]}
    league = {r["season_id"]: r for r in bundle["league"]}
    current = {p["player_id"] for p in bundle["roster"]}
    builder = era.EraProfiles(bundle, special_teams.ERA_METHOD)
    age = analysis.season_age(players[TARGET]["birth_date"], last)
    factors = {sid: rates[last] / rate for sid, rate in rates.items()}
    histories = {
        pid: {r["season_id"]: r for r in analysis.collapse_seasons(player, last)}
        for pid, player in players.items()
    }
    saved = {r["window"]: r for r in article["rows"] if r["player_id"] == TARGET}
    windows = {}
    for window in ("whole_career", "age_aligned"):
        whole = window == "whole_career"

        def profile(player, *, whole=whole):
            result = builder(
                player, league, last, max_age=None if whole else age, end_at_last_played=whole
            )
            if result["nhl_games"] < 50:
                raise analysis.ProfileError("insufficient_nhl_games")
            return special_teams.pp_profile(
                result, histories[player["player_id"]], scoring, factors
            )

        target = profile(players[TARGET])
        available = []
        for player in bundle["players"]:
            if (
                player["player_id"] in current
                or analysis.position_group(player["position"]) != "D"
                or player["avs_games"] < 50
            ):
                continue
            try:
                available.append(profile(player))
            except analysis.ProfileError:
                continue
        tenure, pool = primary_pool(available, article)
        if {p["player_id"] for p in pool} != set(saved[window]["candidate_ids"]):
            raise ValueError("The full historical diagnostic pool differs from the saved article.")
        ranked, _, details = special_teams.rank_without_lift(target, pool, ice_time)
        if details["pk_status"] != "pk_included":
            raise ValueError("Makar's selected article model should include audited PK minutes.")
        article_target = {**target, "features": details["target_features"]}
        by_id = {p["player_id"]: p for p in ranked}
        covered = [by_id[pid] for pid in details["ranked_candidate_ids"]]
        cases = {
            "article": distinctiveness.neighbour_audit(article_target, covered, details["weights"]),
            "all_alumni_without_pk": distinctiveness.neighbour_audit(
                target, pool, special_teams.WITHOUT_LIFT
            ),
            "covered_alumni_without_pk": distinctiveness.neighbour_audit(
                target, covered, special_teams.WITHOUT_LIFT
            ),
        }
        reconcile_article(cases["article"], article_target, covered, saved[window])
        full_by_id = {p["player_id"]: p for p in [target, *pool]}
        comparisons = []
        comparison_ids = dict.fromkeys(
            (
                TARGET,
                cases["article"]["closest_match"]["player_id"],
                cases["all_alumni_without_pk"]["closest_match"]["player_id"],
                BOURQUE,
                BARRIE,
                OZOLINSH,
                LILES,
            )
        )
        for pid in comparison_ids:
            if pid not in full_by_id:
                continue
            player = full_by_id[pid]
            roles = []
            if pid == TARGET:
                roles.append("Current player")
            if pid == cases["article"]["closest_match"]["player_id"]:
                roles.append("Article match")
            if pid == cases["all_alumni_without_pk"]["closest_match"]["player_id"]:
                roles.append("Closest without PK")
            if pid == LILES:
                roles.append("Additional comparison")
            ranks = {}
            for label, case_key in (("article", "article"), ("broader", "all_alumni_without_pk")):
                ranked_comparators = cases[case_key]["target_rankings"]
                rank = next(
                    (i + 1 for i, p in enumerate(ranked_comparators) if p["player_id"] == pid),
                    None,
                )
                ranks[label + "_rank"] = rank
                ranks[label + "_distance"] = (
                    ranked_comparators[rank - 1]["distance"] if rank is not None else None
                )
            comparisons.append(
                {
                    "player_id": pid,
                    "name": player["name"],
                    "games": player["nhl_games"],
                    "avs_games": player["avs_games"],
                    "role": " · ".join(roles) if roles else "Historical context",
                    "features": {
                        key: player["features"][key] for key in special_teams.WITHOUT_LIFT
                    },
                    "pk_coverage": special_teams.pk_context(player, ice_time),
                    "in_article_pool": pid in details["ranked_candidate_ids"],
                    **ranks,
                }
            )
        sensitivity = {}
        for alternative in sorted({50, tenure, 100, 150}):
            peers = [p for p in available if p["avs_games"] >= alternative]
            sensitivity[f"tenure_{alternative}"] = distinctiveness.neighbour_audit(
                target, peers, special_teams.WITHOUT_LIFT
            )
        sensitivity[f"equal_weights_{tenure}"] = distinctiveness.neighbour_audit(
            target, pool, dict.fromkeys(special_teams.WITHOUT_LIFT, 1)
        )
        sensitivity[f"third_neighbour_{tenure}"] = distinctiveness.neighbour_audit(
            target, pool, special_teams.WITHOUT_LIFT, k=3
        )
        windows[window] = {
            "window": window,
            "age": age,
            "primary_tenure": tenure,
            "target_name": target["name"],
            "cases": cases,
            "comparisons": comparisons,
            "rate_leaders": compare_rates(target, pool),
            "article_squared_distance_shares": gap_shares(cases["article"]),
            "sensitivity": sensitivity,
        }
        windows[window]["radar_comparisons"] = comparison_radars(windows[window])
        windows[window]["radar_stem"] = "makar-barrie-liles-" + (
            "full-career" if whole else "age-adjusted"
        )
    return {
        "question": "What makes Makar hard to match, and why do the article card and wider historical check name different players?",
        "cutoff": f"{str(last)[:4]}–{str(last)[-2:]}",
        "primary_tenure": article["config"]["min_avs_skater_games"],
        "grain": f"One player's NHL regular-season career profile, all NHL teams; independent observed-career and through-age-{age} windows.",
        "windows": windows,
        "interpretation": "Descriptive offensive production and nearest-neighbour isolation within qualifying former Colorado defensemen; not overall player value, NHL-wide uniqueness, a probability, or a forecast.",
    }


def rate_comparison_text(value, baseline):
    """Describe actual relative rates without assuming the target is always higher."""
    if baseline <= 0:
        return f"{value:.1f} versus {baseline:.1f}"
    gap = 100 * (value / baseline - 1)
    if abs(gap) < 0.05:
        return "the same rate"
    return f"{abs(gap):.0f}% {'higher' if gap > 0 else 'lower'}"


def narrative(report):
    """Derive article language from the selected threshold, cohorts and winners."""
    data = report["windows"]["age_aligned"]
    article = data["cases"]["article"]
    broad = data["cases"]["all_alumni_without_pk"]
    covered = data["cases"]["covered_alumni_without_pk"]
    players = {p["player_id"]: p for p in data["comparisons"]}
    target = players[TARGET]
    match = players[article["closest_match"]["player_id"]]
    phrases = [
        f"{rate_comparison_text(target['features'][key], match['features'][key])} {LABELS[key].lower()}"
        for key in SCORING
    ]
    pool_explanation = (
        f"Removing PK from that same covered pool still selects {covered['closest_match']['name']}. "
        "This separates the effect of the coverage restriction from the effect of PK's weight."
    )
    return (
        f"Through age {data['age']}, Cale Makar's era-adjusted offensive production remains unusual "
        f"among the {broad['reference_count']} eligible former Avalanche defensemen under the "
        f"{report['primary_tenure']}-Colorado-game rule. Compared with {match['name']} at the same age, "
        f"his closest match under the article's PK-inclusive model, he recorded {', '.join(phrases)}. "
        f"His nearest-match gap was {article['ratio_to_median']:.1f} times the typical gap among the "
        f"{article['reference_count']} alumni with complete audited PK records. A broader check using "
        f"all {broad['reference_count']} eligible alumni and omitting PK minutes selected "
        f"{broad['closest_match']['name']}, with Makar's gap {broad['ratio_to_median']:.1f} times typical. "
        f"{pool_explanation} These are descriptive comparisons within this franchise's eligible "
        "alumni, rather than a measure of overall player value or proof of NHL-wide uniqueness."
    )
