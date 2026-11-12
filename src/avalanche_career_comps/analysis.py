"""Explainable career analogies; no fitting of outcomes or career forecasting.

Input seasons are NHL regular-season *team* totals, excluding combined totals.
Repeated player/team/season source records must be removed by the loader. This
module intentionally combines legitimate traded-player team rows before deriving
rates. Career profiles include all NHL teams; Avalanche games establish eligibility
only. The default analysis ends historical profiles at the target's season-age.
The separate whole-career branch includes every observed season before the cutoff.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from math import isfinite, log1p, sqrt
from statistics import pstdev

SKATER_WEIGHTS = {
    "goals_per_82": 0.175,
    "assists_per_82": 0.175,
    "shots_per_82": 0.15,
    "pim_per_82": 0.10,
    "log_games": 0.20,
    "debut_age": 0.10,
    "scoring_trajectory": 0.10,
}
GOALIE_WEIGHTS = {
    "relative_save_percentage": 0.25,
    "adjusted_shots_per_game": 0.25,
    "schedule_adjusted_games_per_season": 0.25,
    "log_games": 0.25,
}
FEATURE_LABELS = {
    "goals_per_82": "Goals per 82 games, era adjusted",
    "assists_per_82": "Assists per 82 games, era adjusted",
    "shots_per_82": "Shots per 82 games, era adjusted",
    "pim_per_82": "Penalty minutes per 82 games",
    "log_games": "Career games (log scale)",
    "debut_age": "Age in first NHL regular-season appearance season",
    "scoring_trajectory": "Recent minus career points per game",
    "relative_save_percentage": "Save percentage above the season's league rate",
    "adjusted_shots_per_game": "Shots faced per game, era adjusted",
    "schedule_adjusted_games_per_season": "Appearances per career season, 82-game schedule",
}


class ProfileError(ValueError):
    """A profile cannot be compared without making up missing information."""


def position_group(position):
    """Use broad roles rather than forcing centers and wingers into tiny pools."""
    value = str(position).upper()
    if value in {"G", "GOALIE"}:
        return "G"
    if value in {"D", "DEFENSE", "DEFENCEMAN", "DEFENSEMAN"}:
        return "D"
    if value in {"F", "C", "L", "R", "LW", "RW", "FORWARD"}:
        return "F"
    raise ProfileError("unknown_position")


def season_age(birth_date, season_id):
    """Age on February 1 of the season's ending calendar year."""
    try:
        birthday = date.fromisoformat(str(birth_date))
    except (TypeError, ValueError) as exc:
        raise ProfileError("missing_birth_date") from exc
    year = int(season_id) % 10000
    return year - birthday.year - ((birthday.month, birthday.day) > (2, 1))


def _number(row, key, *, positive=False):
    value = row.get(key)
    if value is None:
        raise ProfileError(f"missing_{key}")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ProfileError(f"invalid_{key}") from exc
    if not isfinite(result) or result < 0 or (positive and result <= 0):
        raise ProfileError(f"invalid_{key}")
    return result


def collapse_seasons(player, last_season):
    """Combine NHL team stints, retaining nulls rather than partial-count totals."""
    goalie = position_group(player["position"]) == "G"
    fields = (
        ["games", "shots_against", "goals_against", "shutouts"]
        if goalie
        else ["games", "goals", "assists", "shots", "pim"]
    )
    grouped = defaultdict(list)
    for row in player.get("seasons", []):
        if int(row["season_id"]) <= int(last_season):
            grouped[int(row["season_id"])].append(row)
    result = []
    for season_id, rows in sorted(grouped.items()):
        combined = {"season_id": season_id}
        for field in fields:
            # Shutouts are preserved for inspection; they do not affect distance.
            values = [row.get(field) for row in rows]
            combined[field] = None if any(v is None for v in values) else sum(values)
        result.append(combined)
    return result


def build_profile(
    player, league, last_season, *, max_age=None, adjusted=True, end_at_last_played=False
):
    """Describe observed NHL career through a fixed age and completed-season cutoff."""
    group = position_group(player["position"])
    rows = collapse_seasons(player, last_season)
    if max_age is not None:
        rows = [r for r in rows if season_age(player.get("birth_date"), r["season_id"]) <= max_age]
    rows = [r for r in rows if _number(r, "games") > 0]
    if not rows:
        raise ProfileError("no_seasons_before_cutoff")
    ages = [season_age(player.get("birth_date"), r["season_id"]) for r in rows]
    if max_age is not None and ages[-1] < max_age - 1:
        raise ProfileError("career_ended_before_comparable_age")
    games = sum(_number(r, "games", positive=True) for r in rows)
    first_year = rows[0]["season_id"] // 10000
    last_year = int(last_season) // 10000
    if end_at_last_played:
        if max_age is not None:
            raise ValueError("Whole-career calendar end cannot be combined with an age cap.")
        last_year = rows[-1]["season_id"] // 10000
    if max_age is not None:
        birthday = date.fromisoformat(str(player["birth_date"]))
        stage_end = birthday.year + max_age + ((birthday.month, birthday.day) > (2, 1))
        last_year = min(int(last_season) // 10000, stage_end - 1)
    # Count canceled NHL seasons as unavailable, not a zero-workload player year.
    career_seasons = sum(
        1
        for sid, row in league.items()
        if first_year <= int(sid) // 10000 <= last_year
        and _number(row, "games_per_team", positive=True) > 0
    )
    if career_seasons == 0:
        raise ProfileError("missing_career_calendar")
    path = []
    cumulative_games = 0
    cumulative_points = 0.0
    totals = Counter()
    for row, age in zip(rows, ages, strict=True):
        sid = row["season_id"]
        context = league.get(sid)
        if context is None:
            raise ProfileError("missing_league_season")
        gp = _number(row, "games", positive=True)
        league_goals = _number(context, "goals_per_team_game", positive=True)
        league_shots = _number(context, "shots_per_team_game", positive=True)
        schedule = _number(context, "games_per_team", positive=True)
        goalie_goal_rate = (
            _number(context, "goalie_goal_rate", positive=True)
            if context.get("goalie_goal_rate") is not None
            else league_goals / league_shots
        )
        cumulative_games += gp
        point = {"season_id": sid, "age": age, "games": gp, "cumulative_games": cumulative_games}
        if group == "G":
            shots = _number(row, "shots_against")
            goals = _number(row, "goals_against")
            if goals > shots:
                raise ProfileError("goals_exceed_shots")
            totals["shots_against"] += shots
            totals["goals_against"] += goals
            totals["expected_goals"] += shots * goalie_goal_rate
            totals["adjusted_shots"] += shots * (30 / league_shots if adjusted else 1)
            totals["adjusted_games"] += gp * (82 / schedule if adjusted else 1)
            point["relative_save_percentage"] = (
                None
                if not shots
                else (goalie_goal_rate - goals / shots if adjusted else 1 - goals / shots)
            )
        else:
            factor = 3 / league_goals if adjusted else 1
            goals = _number(row, "goals") * factor
            assists = _number(row, "assists") * factor
            shots = _number(row, "shots") * (30 / league_shots if adjusted else 1)
            totals["goals"] += goals
            totals["assists"] += assists
            totals["shots"] += shots
            totals["pim"] += _number(row, "pim")
            cumulative_points += goals + assists
            point.update(
                {
                    "adjusted_points_per_game": (goals + assists) / gp,
                    "cumulative_adjusted_points": cumulative_points,
                }
            )
        path.append(point)
    if group == "G":
        if not totals["shots_against"]:
            raise ProfileError("no_shots_faced")
        relative = (totals["expected_goals"] - totals["goals_against"]) / totals["shots_against"]
        features = {
            "relative_save_percentage": relative
            if adjusted
            else (1 - totals["goals_against"] / totals["shots_against"]),
            "adjusted_shots_per_game": totals["adjusted_shots"] / games,
            "schedule_adjusted_games_per_season": totals["adjusted_games"] / career_seasons,
            "log_games": log1p(games),
        }
    else:
        recent_first_year = last_year - 2
        recent = [p for p in path if p["season_id"] // 10000 >= recent_first_year]
        recent_games = sum(p["games"] for p in recent)
        if not recent_games:
            raise ProfileError("no_recent_seasons")
        recent_ppg = sum(p["adjusted_points_per_game"] * p["games"] for p in recent) / recent_games
        career_ppg = (totals["goals"] + totals["assists"]) / games
        features = {
            "goals_per_82": 82 * totals["goals"] / games,
            "assists_per_82": 82 * totals["assists"] / games,
            "shots_per_82": 82 * totals["shots"] / games,
            "pim_per_82": 82 * totals["pim"] / games,
            "log_games": log1p(games),
            "debut_age": ages[0],
            "scoring_trajectory": recent_ppg - career_ppg,
        }
    profile = {
        "player_id": player["player_id"],
        "name": player["name"],
        "position": group,
        "nhl_games": games,
        "avs_games": player.get("avs_games", 0),
        "first_age": ages[0],
        "last_age": ages[-1],
        "career_seasons": career_seasons,
        "features": features,
        "path": path,
        "totals": dict(totals),
    }
    if end_at_last_played:
        profile.update(
            first_season=rows[0]["season_id"],
            last_season=rows[-1]["season_id"],
            window_end_season=rows[-1]["season_id"],
            is_active=player.get("is_active"),
        )
    return profile


def _rank(target, candidates, weights):
    if not candidates:
        return [], {}
    total_weight = sum(weights.values())
    weights = {key: value / total_weight for key, value in weights.items()}
    scales = {key: pstdev(c["features"][key] for c in candidates) or 1.0 for key in weights}
    matches = []
    for candidate in candidates:
        contributions = {
            key: weights[key]
            * ((target["features"][key] - candidate["features"][key]) / scales[key]) ** 2
            for key in weights
        }
        matches.append(
            {
                **candidate,
                "distance": sqrt(sum(contributions.values())),
                "contributions": contributions,
            }
        )
    matches.sort(key=lambda row: (row["distance"], row["player_id"]))
    return matches, scales


def analyze(
    bundle, *, career_window="age_aligned", profile_builder=None, candidate_ids_by_target=None
):
    """Rank former Avalanche players and expose sensitivity to declared choices."""
    if career_window not in {"age_aligned", "whole_career"}:
        raise ValueError("Unknown career window.")
    whole_career = career_window == "whole_career"
    make_profile = profile_builder or build_profile
    config = {
        "last_season": 20252026,
        "min_avs_skater_games": 100,
        "min_avs_goalie_games": 50,
        **bundle.get("config", {}),
    }
    last_season = int(config["last_season"])
    league = {int(row["season_id"]): row for row in bundle["league"]}
    players = {row["player_id"]: row for row in bundle["players"]}
    if len(players) != len(bundle["players"]):
        raise ValueError("duplicate player_id in players")
    roster_ids = {row["player_id"] for row in bundle["roster"]}
    if len(roster_ids) != len(bundle["roster"]):
        raise ValueError("duplicate player_id in roster")
    results = []
    for roster_player in bundle["roster"]:
        base = {
            "player_id": roster_player["player_id"],
            "name": roster_player["name"],
            "position": roster_player["position"],
            "matches": [],
            "sensitivities": {},
        }
        try:
            player = players.get(roster_player["player_id"])
            if player is None:
                raise ProfileError("missing_player_history")
            group = position_group(player["position"])
            age = season_age(player.get("birth_date"), last_season)
            target = make_profile(player, league, last_season, end_at_last_played=whole_career)
            minimum_current = 25 if group == "G" else 50
            if target["nhl_games"] < minimum_current:
                raise ProfileError("insufficient_nhl_games")
        except ProfileError as exc:
            results.append(
                {**base, "status": "insufficient_data", "reason": str(exc), "candidate_count": 0}
            )
            continue
        weights = GOALIE_WEIGHTS.copy() if group == "G" else SKATER_WEIGHTS.copy()
        threshold = (
            config["min_avs_goalie_games"] if group == "G" else config["min_avs_skater_games"]
        )
        low, high = (25, 75) if group == "G" else (50, 150)
        excluded = Counter()
        profiles = []
        unadjusted_profiles = []
        age_control_profiles = {}
        allowed = None
        if candidate_ids_by_target is not None:
            if roster_player["player_id"] not in candidate_ids_by_target:
                raise ValueError("Missing target in candidate-pool control.")
            allowed = set(candidate_ids_by_target[roster_player["player_id"]])
        for historical in players.values():
            if historical["player_id"] in roster_ids:
                continue
            if allowed is not None and historical["player_id"] not in allowed:
                continue
            try:
                if position_group(historical["position"]) != group:
                    continue
                if _number(historical, "avs_games") < min(low, threshold):
                    excluded["below_lowest_avalanche_threshold"] += 1
                    continue
                profile = make_profile(
                    historical,
                    league,
                    last_season,
                    max_age=None if whole_career else age,
                    end_at_last_played=whole_career,
                )
                if not whole_career and profile["last_age"] < age - 1:
                    raise ProfileError("career_ended_before_comparable_age")
                minimum_candidate = 25 if group == "G" else 50
                if profile["nhl_games"] < minimum_candidate:
                    raise ProfileError(
                        "insufficient_nhl_games"
                        if whole_career
                        else "insufficient_nhl_games_at_age"
                    )
                profiles.append(profile)
                unadjusted_profiles.append(
                    make_profile(
                        historical,
                        league,
                        last_season,
                        max_age=None if whole_career else age,
                        adjusted=False,
                        end_at_last_played=whole_career,
                    )
                )
                if whole_career:
                    # Control the pool when inspecting the change in career window.
                    # Missing full-career measurements may still remove an age-valid player.
                    try:
                        age_profile = make_profile(historical, league, last_season, max_age=age)
                        if age_profile["nhl_games"] >= minimum_candidate:
                            age_control_profiles[historical["player_id"]] = age_profile
                    except ProfileError:
                        pass
            except ProfileError as exc:
                excluded[str(exc)] += 1
        eligible = [p for p in profiles if p["avs_games"] >= threshold]
        ranked, scales = _rank(target, eligible, weights)
        result = {
            **base,
            "status": "matched" if ranked else "no_eligible_comparison",
            "position": group,
            "age": age,
            "nhl_games": target["nhl_games"],
            "target_features": target["features"],
            "feature_weights": weights,
            "target": target,
            "path": target["path"],
            "candidate_count": len(eligible),
            "scales": scales,
            "matches": ranked[:3],
            "excluded_reasons": dict(excluded),
        }
        if whole_career:
            try:
                age_control_target = make_profile(player, league, last_season)
            except ProfileError:
                age_control_target = None
            control_pool = [
                p
                for p in eligible
                if age_control_target is not None and p["player_id"] in age_control_profiles
            ]
            control_matches, control_scales = _rank(target, control_pool, weights)
            paired_age_matches, paired_age_scales = _rank(
                age_control_target,
                [age_control_profiles[p["player_id"]] for p in control_pool],
                weights,
            )
            result["eligible_candidate_ids"] = sorted(p["player_id"] for p in eligible)
            result["age_pool_control"] = {
                "candidate_count": len(control_pool),
                "candidate_ids": sorted(p["player_id"] for p in control_pool),
                "matches": control_matches[:3],
                "scales": control_scales,
                "age_aligned_matches": paired_age_matches[:3],
                "age_aligned_scales": paired_age_scales,
                "age_aligned_quality_flags": [
                    flag
                    for condition, flag in [
                        (len(control_pool) < 5, "small_comparison_pool"),
                        (
                            bool(paired_age_matches) and paired_age_matches[0]["distance"] > 1.5,
                            "distant_analogue",
                        ),
                    ]
                    if condition
                ],
                "quality_flags": [
                    flag
                    for condition, flag in [
                        (len(control_pool) < 5, "small_comparison_pool"),
                        (
                            bool(control_matches) and control_matches[0]["distance"] > 1.5,
                            "distant_analogue",
                        ),
                    ]
                    if condition
                ],
            }
        if not ranked:
            results.append(result)
            continue
        best_id = ranked[0]["player_id"]
        sensitivities = {}

        def sensitivity(
            name,
            adjusted_target,
            pool,
            selected_weights,
            *,
            output=sensitivities,
            primary_id=best_id,
        ):
            ordered, _ = _rank(adjusted_target, pool, selected_weights)
            best = ordered[0] if ordered else None
            output[name] = (
                None
                if best is None
                else {
                    "player_id": best["player_id"],
                    "name": best["name"],
                    "distance": best["distance"],
                    "candidate_count": len(pool),
                    "changed": best["player_id"] != primary_id,
                }
            )

        sensitivity(
            "threshold_low", target, [p for p in profiles if p["avs_games"] >= low], weights
        )
        sensitivity(
            "threshold_high", target, [p for p in profiles if p["avs_games"] >= high], weights
        )
        sensitivity("equal_weights", target, eligible, dict.fromkeys(weights, 1))
        if group != "G":
            sensitivity(
                "no_pim", target, eligible, {k: v for k, v in weights.items() if k != "pim_per_82"}
            )
        for key in weights:
            if key == "pim_per_82":
                # This exact omission is already reported as the named no_pim variant.
                continue
            sensitivity(
                f"without_{key}", target, eligible, {k: v for k, v in weights.items() if k != key}
            )
        raw_target = make_profile(
            player,
            league,
            last_season,
            adjusted=False,
            end_at_last_played=whole_career,
        )
        sensitivity(
            "unadjusted",
            raw_target,
            [p for p in unadjusted_profiles if p["avs_games"] >= threshold],
            weights,
        )
        baseline_key = (
            "relative_save_percentage"
            if group == "G"
            else target.get("scoring_baseline_label", "points_per_game")
        )

        def baseline_value(profile, position=group):
            if position == "G":
                return profile["features"]["relative_save_percentage"]
            if "scoring_baseline_value" in profile:
                return profile["scoring_baseline_value"]
            return (
                profile["features"]["goals_per_82"] + profile["features"]["assists_per_82"]
            ) / 82

        baseline = min(
            eligible,
            key=lambda c: (abs(baseline_value(target) - baseline_value(c)), c["player_id"]),
        )
        result["baseline"] = {
            "player_id": baseline["player_id"],
            "name": baseline["name"],
            "feature": baseline_key,
            "absolute_gap": abs(baseline_value(target) - baseline_value(baseline)),
        }
        result["sensitivities"] = sensitivities
        available = [s for s in sensitivities.values() if s is not None]
        result["stability"] = {
            "same_best": sum(not s["changed"] for s in available),
            "variants": len(available),
            "not_a_probability": True,
        }
        result["distance_margin"] = (
            ranked[1]["distance"] - ranked[0]["distance"] if len(ranked) > 1 else None
        )
        result["quality_flags"] = [
            flag
            for condition, flag in [
                (len(eligible) < 5, "small_comparison_pool"),
                (ranked[0]["distance"] > 1.5, "distant_analogue"),
                (
                    not whole_career and ranked[0]["last_age"] < age,
                    "comparison_ends_one_age_year_earlier",
                ),
                (
                    whole_career and ranked[0].get("is_active") is True,
                    "alumnus_active_at_source_snapshot",
                ),
            ]
            if condition
        ]
        results.append(result)
    report = {
        "method": (
            "whole-observed-career weighted standardized distance"
            if whole_career
            else "age-aligned weighted standardized career distance"
        ),
        "config": config,
        "feature_labels": FEATURE_LABELS,
        "results": results,
        "notes": [
            "Descriptive analogy, not a forecast, probability, or causal claim.",
            "Eligibility counts Colorado games only; profiles include every NHL team.",
            "Historical careers are truncated at the current player's February-1 season-age.",
            "Scales use the eligible age-truncated former-player pool, separately for each target.",
            "Distances from different targets use different scales and are not comparable across players.",
            "Debut age means first NHL regular season; a playoff-only debut is not included.",
            "The distant-analogue flag at distance greater than 1.5 is a descriptive screen, not a calibrated cutoff.",
            "Era scaling addresses league scoring and shot environment, not every rule or role change.",
            "Alumni eligibility uses eventual Colorado tenure, a hindsight descriptive restriction.",
        ],
    }
    if whole_career:
        report["career_window"] = career_window
        report["question"] = (
            "Which eligible former Avalanche player has the most similar entire observed NHL career?"
        )
        report["notes"][2:4] = [
            "Both profiles include their entire observed NHL regular-season history through the cutoff; no age cap.",
            "Recent scoring and calendar-season exposure end at each player's last positive-games season, retaining interior missed seasons and excluding 2004–05.",
            "Scales use the eligible full-career former-player pool, separately by position; distances cannot be compared to the age-aligned branch.",
            "The age-pool control reranks full-career profiles on the intersection with age-eligible candidates; its candidate IDs and scales are saved.",
            "Active status is the saved source-snapshot status, not a verified retirement date or status at an earlier cutoff.",
            "Rates, log career games and weights are unchanged; this is not a raw cumulative-points ranking.",
            "Full-career averages mix different career stages and are not projections of unfinished careers.",
        ]
    return report
