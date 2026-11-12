"""Controlled era-method comparisons over immutable career and league inputs.

Peer observations are combined-team NHL regular-season player-seasons. Their
moments are fitted before any target matching and use no Avalanche eligibility
filter. Seasonal normalization and career-candidate scaling are separate steps.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
from math import ceil, isfinite
from statistics import fmean, pstdev

from .analysis import (
    FEATURE_LABELS,
    SKATER_WEIGHTS,
    ProfileError,
    analyze,
    build_profile,
    collapse_seasons,
    position_group,
    season_age,
)

COUNT_KEYS = ("goals", "assists", "shots", "pim")
FEATURE_KEYS = dict(
    zip(COUNT_KEYS, ("goals_per_82", "assists_per_82", "shots_per_82", "pim_per_82"))
)
SEASON_LABELS = {
    **FEATURE_LABELS,
    "goals_per_82": "Career mean season-relative goals/game z-score",
    "assists_per_82": "Career mean season-relative assists/game z-score",
    "shots_per_82": "Career mean season-relative shots/game z-score",
    "pim_per_82": "Career mean season-relative penalty minutes/game z-score",
    "scoring_trajectory": "Recent minus career season-relative points/game z-score",
}


def _count(row, key, *, positive=False):
    value = row.get(key)
    if value is None or isinstance(value, bool):
        raise ProfileError(f"missing_or_invalid_peer_{key}")
    value = float(value)
    if not isfinite(value) or value < 0 or (positive and value <= 0):
        raise ProfileError(f"missing_or_invalid_peer_{key}")
    return value


def peer_contexts(bundle):
    """Fit equal-player season/position moments; retain unusable groups explicitly."""
    config = bundle["era_config"]
    league = {r["season_id"]: r for r in bundle["league"]}
    groups = defaultdict(list)
    seen = set()
    for row in bundle["era_peers"]:
        key = (row["player_id"], row["season_id"])
        if key in seen:
            raise ValueError("Duplicate peer player-season.")
        seen.add(key)
        sid = row["season_id"]
        if sid not in league:
            raise ValueError("Peer season is outside the frozen league calendar.")
        position = position_group(row["position"])
        if position not in {"F", "D"}:
            raise ValueError("Goalie in skater peer observations.")
        gp = _count(row, "games", positive=True)
        for metric in COUNT_KEYS:
            _count(row, metric)
        minimum = ceil(config["peer_min_games_equivalent_82"] * league[sid]["games_per_team"] / 82)
        if gp >= minimum:
            groups[(sid, position)].append(row)
    contexts = {}
    for sid, season in sorted(league.items()):
        for position in ("F", "D"):
            rows = groups[(sid, position)]
            minimum = ceil(config["peer_min_games_equivalent_82"] * season["games_per_team"] / 82)
            context = {
                "season_id": sid,
                "position": position,
                "qualified_players": len(rows),
                "minimum_games": minimum,
                "means": {},
                "standard_deviations": {},
                "valid": True,
                "failures": [],
            }
            if len(rows) < config["minimum_peer_group_size"]:
                context["valid"] = False
                context["failures"].append("insufficient_peer_group")
            else:
                for metric in (*COUNT_KEYS, "points"):
                    rates = [
                        (r["goals"] + r["assists"] if metric == "points" else r[metric])
                        / r["games"]
                        for r in rows
                    ]
                    context["means"][metric] = fmean(rates)
                    context["standard_deviations"][metric] = pstdev(rates)
                    if context["standard_deviations"][metric] == 0:
                        context["valid"] = False
                        context["failures"].append(f"zero_peer_spread_{metric}")
            contexts[(sid, position)] = context
    return contexts


def _window_end_year(player, last_season, max_age, end_at_last_played, profile):
    if end_at_last_played:
        return profile["path"][-1]["season_id"] // 10000
    year = last_season // 10000
    if max_age is not None:
        birthday = date.fromisoformat(player["birth_date"])
        age_end = birthday.year + max_age + ((birthday.month, birthday.day) > (2, 1))
        year = min(year, age_end - 1)
    return year


class EraProfiles:
    """Produce one declared representation without altering baseline source inputs."""

    def __init__(self, bundle, method, contexts=None):
        if method not in {"baseline", "corrected_baseline", "separate_assists", "season_relative"}:
            raise ValueError("Unknown era method.")
        self.method = method
        self.config = bundle["era_config"]
        self.contexts = (
            (contexts if contexts is not None else peer_contexts(bundle))
            if method == "season_relative"
            else {}
        )
        self.peers = (
            {(r["player_id"], r["season_id"]): r for r in bundle.get("era_peers", [])}
            if method == "season_relative"
            else {}
        )
        self.environments = {r["season_id"]: r for r in bundle["era_environments"]}
        if method == "season_relative" and len(self.peers) != len(bundle["era_peers"]):
            raise ValueError("Duplicate peer player-season.")
        if len(self.environments) != len(bundle["era_environments"]):
            raise ValueError("Duplicate era environment season.")
        self.cache = {}

    def __call__(
        self, player, league, last_season, *, max_age=None, adjusted=True, end_at_last_played=False
    ):
        key = (player["player_id"], last_season, max_age, adjusted, end_at_last_played)
        if key not in self.cache:
            self.cache[key] = self._build(
                player, league, last_season, max_age, adjusted, end_at_last_played
            )
        return self.cache[key]

    def _build(self, player, league, last_season, max_age, adjusted, end_at_last_played):
        original = build_profile(
            player,
            league,
            last_season,
            max_age=max_age,
            adjusted=adjusted,
            end_at_last_played=end_at_last_played,
        )
        if self.method == "baseline" or original["position"] == "G" or not adjusted:
            return original
        profile = deepcopy(original)
        selected = {p["season_id"] for p in profile["path"]}
        seasons = [r for r in collapse_seasons(player, last_season) if r["season_id"] in selected]
        last_year = _window_end_year(player, last_season, max_age, end_at_last_played, profile)
        recent_games = sum(r["games"] for r in seasons if r["season_id"] // 10000 >= last_year - 2)
        totals, recent_points, career_points = Counter(), 0.0, 0.0
        below_games, below_seasons = 0, 0
        for row, point in zip(seasons, profile["path"], strict=True):
            sid, gp = row["season_id"], row["games"]
            if self.method in {"corrected_baseline", "separate_assists"}:
                env = self.environments.get(sid)
                if env is None:
                    raise ProfileError("missing_assist_environment")
                assist_rate = _count(env, "assists_per_team_game", positive=True)
                goal_factor = self.config["reference_goals_per_team_game"] / _count(
                    env, "goals_per_team_game", positive=True
                )
                goals = row["goals"] * goal_factor
                assists = row["assists"] * (
                    goal_factor
                    if self.method == "corrected_baseline"
                    else self.config["reference_assists_per_team_game"] / assist_rate
                )
                totals["goals"] += goals
                totals["assists"] += assists
                points = goals + assists
                career_points += points
                point["adjusted_points_per_game"] = points / gp
                point["cumulative_adjusted_points"] = career_points
            else:
                peer = self.peers.get((player["player_id"], sid))
                if peer is None:
                    raise ProfileError("missing_peer_player_season")
                if any(peer.get(k) != row.get(k) for k in ("games", *COUNT_KEYS)):
                    raise ProfileError("peer_source_disagreement")
                context = self.contexts.get((sid, position_group(peer["position"])))
                if context is None or not context["valid"]:
                    raise ProfileError("unusable_peer_context")
                rates = {k: row[k] / gp for k in COUNT_KEYS}
                rates["points"] = (row["goals"] + row["assists"]) / gp
                z = {
                    k: (value - context["means"][k]) / context["standard_deviations"][k]
                    for k, value in rates.items()
                }
                for metric in COUNT_KEYS:
                    totals[metric] += gp * z[metric]
                points = gp * z["points"]
                career_points += points
                point.pop("adjusted_points_per_game")
                point.pop("cumulative_adjusted_points")
                point.update(
                    season_z=z,
                    peer_position=context["position"],
                    qualified_peers=context["qualified_players"],
                    peer_minimum_games=context["minimum_games"],
                    below_peer_minimum=gp < context["minimum_games"],
                )
                if gp < context["minimum_games"]:
                    below_games += gp
                    below_seasons += 1
            if sid // 10000 >= last_year - 2:
                recent_points += points
        games = profile["nhl_games"]
        if self.method in {"corrected_baseline", "separate_assists"}:
            for metric in ("goals", "assists"):
                profile["totals"][metric] = totals[metric]
                profile["features"][FEATURE_KEYS[metric]] = 82 * totals[metric] / games
        else:
            for metric in COUNT_KEYS:
                profile["features"][FEATURE_KEYS[metric]] = totals[metric] / games
            profile["totals"] = {f"raw_{k}": sum(r[k] for r in seasons) for k in COUNT_KEYS}
            profile["scoring_baseline_value"] = career_points / games
            profile["scoring_baseline_label"] = "career_season_relative_points_z"
            profile["below_peer_minimum_games"] = below_games
            profile["below_peer_minimum_seasons"] = below_seasons
            profile["below_peer_minimum_games_fraction"] = below_games / games
        profile["features"]["scoring_trajectory"] = (
            recent_points / recent_games - career_points / games
        )
        profile["era_method"] = self.method
        return profile


def _available(bundle, builder, window):
    league = {r["season_id"]: r for r in bundle["league"]}
    players = {r["player_id"]: r for r in bundle["players"]}
    current = {r["player_id"] for r in bundle["roster"]}
    last = bundle["config"]["last_season"]
    whole = window == "whole_career"
    pools, ledger = {}, []
    for target in bundle["roster"]:
        pid = target["player_id"]
        pool, failures = [], Counter()
        entry = {"player_id": pid, "name": target["name"], "target_status": "available"}
        try:
            source = players[pid]
            group = position_group(source["position"])
            age = season_age(source["birth_date"], last)
            minimum = 25 if group == "G" else 50
            target_profile = builder(source, league, last, end_at_last_played=whole)
            if target_profile["nhl_games"] < minimum:
                raise ProfileError("insufficient_nhl_games")
        except (KeyError, ProfileError) as exc:
            pools[pid] = []
            ledger.append({**entry, "target_status": str(exc), "candidate_ids": [], "failures": {}})
            continue
        for player in players.values():
            if player["player_id"] in current or position_group(player["position"]) != group:
                continue
            if player["avs_games"] < (25 if group == "G" else 50):
                continue
            try:
                p = builder(
                    player,
                    league,
                    last,
                    max_age=None if whole else age,
                    end_at_last_played=whole,
                )
                if p["nhl_games"] < minimum:
                    raise ProfileError("insufficient_nhl_games")
                pool.append(player["player_id"])
            except ProfileError as exc:
                failures[str(exc)] += 1
        pools[pid] = sorted(pool)
        ledger.append({**entry, "candidate_ids": sorted(pool), "failures": dict(failures)})
    return pools, ledger


def _decorate(report, method):
    report["era_method"] = method
    report["feature_units"] = {
        "goals_per_82": "goals per 82 games",
        "assists_per_82": "assists per 82 games",
        "shots_per_82": "shots per 82 games",
        "pim_per_82": "penalty minutes per 82 games",
        "log_games": "log(1 + NHL games)",
        "debut_age": "February-1 season-age",
        "scoring_trajectory": "points per game",
        "relative_save_percentage": "save-percentage difference",
        "adjusted_shots_per_game": "era-adjusted shots faced per game",
        "schedule_adjusted_games_per_season": "appearances per 82-game career season",
    }
    if method == "season_relative":
        report["feature_labels"] = SEASON_LABELS
        report["feature_units"].update(
            {
                key: "GP-weighted season z-score"
                for key in (*FEATURE_KEYS.values(), "scoring_trajectory")
            }
        )
    report["notes"] = [
        "Same declared feature weights; no tuning to preferred player matches.",
        "Every controlled branch uses identical eligible candidate IDs for each target/window.",
        "Feature scales are recalculated within each branch; distances are not comparable between branches or targets.",
        "Goalie profiles use their original method unchanged; new era variants apply to skaters.",
        "Unadjusted sensitivity turns off the method's normalization on the same controlled pool.",
        "The distant-analogue threshold is a descriptive screen, not a calibrated similarity boundary.",
    ]
    return report


def analyze_era(bundle):
    """Preserve original results and isolate era-method changes on shared coverage."""
    config = bundle["era_config"]
    if config["similarity_weights"] != SKATER_WEIGHTS:
        raise ValueError("Era supplement must retain the original similarity weights.")
    if config["last_season"] != bundle["config"]["last_season"]:
        raise ValueError("Era and parent statistical cutoffs differ.")
    contexts = peer_contexts(bundle)
    methods = list(dict.fromkeys([*config["methods"], "corrected_baseline"]))
    builders = {method: EraProfiles(bundle, method, contexts) for method in methods}
    cohort_builders = {}
    for minimum in config.get("peer_min_games_sensitivities", []):
        alternative = {
            **bundle,
            "era_config": {**config, "peer_min_games_equivalent_82": minimum},
        }
        cohort_builders[minimum] = EraProfiles(alternative, "season_relative")
    windows = {}
    for window in config["career_windows"]:
        original = analyze(bundle, career_window=window)
        availability = {
            method: _available(bundle, builder, window) for method, builder in builders.items()
        }
        common = {
            p["player_id"]: sorted(
                set.intersection(*(set(v[0][p["player_id"]]) for v in availability.values()))
            )
            for p in bundle["roster"]
        }
        results = {"baseline": original}
        for method, builder in builders.items():
            key = "baseline_control" if method == "baseline" else method
            report = analyze(
                bundle,
                career_window=window,
                profile_builder=builder,
                candidate_ids_by_target=common,
            )
            for row in report["results"]:
                group = position_group(row["position"])
                threshold = bundle["config"][
                    "min_avs_goalie_games" if group == "G" else "min_avs_skater_games"
                ]
                avs = {p["player_id"]: p["avs_games"] for p in bundle["players"]}
                row["candidate_ids"] = [
                    pid for pid in common[row["player_id"]] if avs[pid] >= threshold
                ]
                row["common_candidate_ids"] = row["candidate_ids"]
            results[key] = _decorate(report, method)
        for minimum, builder in cohort_builders.items():
            variant = analyze(
                bundle,
                career_window=window,
                profile_builder=builder,
                candidate_ids_by_target=common,
            )
            variants = {r["player_id"]: r for r in variant["results"]}
            for row in results["season_relative"]["results"]:
                if row["status"] != "matched" or row["position"] == "G":
                    continue
                other = variants[row["player_id"]]
                same_pool = other["candidate_count"] == row["candidate_count"]
                key = f"peer_minimum_{minimum}_games_per_82"
                row["sensitivities"][key] = (
                    {
                        "player_id": other["matches"][0]["player_id"],
                        "name": other["matches"][0]["name"],
                        "distance": other["matches"][0]["distance"],
                        "candidate_count": other["candidate_count"],
                        "changed": other["matches"][0]["player_id"]
                        != row["matches"][0]["player_id"],
                        "same_candidate_pool": True,
                    }
                    if other["status"] == "matched" and same_pool
                    else None
                )
                if not same_pool:
                    row.setdefault("unavailable_sensitivities", {})[key] = (
                        "different_candidate_coverage"
                    )
        for row in results["season_relative"]["results"]:
            if row["status"] == "matched":
                available = [s for s in row["sensitivities"].values() if s is not None]
                row["stability"] = {
                    "same_best": sum(not s["changed"] for s in available),
                    "variants": len(available),
                    "not_a_probability": True,
                }
        results["coverage"] = {method: ledger for method, (_, ledger) in availability.items()}
        windows[window] = results
    affected = [r for r in bundle["era_environments"] if r.get("baseline_goal_difference")]
    baseline_issue = {}
    if affected:
        baseline_issue = {
            "issue": "The frozen baseline subtracted shootout wins from NHL Stats team goalsFor. The original team totals agree with the sum of all player goals.",
            "affected_seasons": [r["season_id"] for r in affected],
            "example": affected[0],
            "evidence": "All-season player and team goal reconciliation is saved in peer_audit.league_environments.",
        }
    return {
        "config": config,
        "windows": windows,
        "peer_audit": {
            "player_seasons": len(bundle["era_peers"]),
            "contexts": list(contexts.values()),
            "valid_contexts": sum(c["valid"] for c in contexts.values()),
            "invalid_contexts": sum(not c["valid"] for c in contexts.values()),
            "cohort": "All qualified NHL player-seasons, separately forwards/defensemen; never Avalanche alumni only.",
            "source_agreement": config["source_agreement"],
            "league_environments": bundle["era_environments"],
        },
        "baseline_issue": baseline_issue,
    }
