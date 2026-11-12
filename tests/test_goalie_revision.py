"""Keep the goalie feature revision isolated from skaters, pools and retained inputs."""

from copy import deepcopy
from math import log1p

import pytest

from avalanche_career_comps import analysis, goalie_performance, goalie_revision


def revision_fixture(monkeypatch):
    ids = (101, 201, 202, 203)
    names = ("Current Goalie", "First Alumnus", "Second Alumnus", "Third Alumnus")
    seasons = (20232024, 20242025)
    players = [
        {"player_id": pid, "name": name, "position": "G", "avs_games": 60}
        for pid, name in zip(ids, names, strict=True)
    ]
    bundle = {
        "config": {"last_season": 20252026, "min_avs_goalie_games": 50},
        "players": players,
        "league": [{"season_id": sid} for sid in seasons],
    }
    profiles = {}
    for index, player in enumerate(players):
        for limited in (False, True):
            path = [{"season_id": sid, "games": 50} for sid in seasons[: 1 if limited else 2]]
            games = sum(p["games"] for p in path)
            profiles[player["player_id"], limited] = {
                "player_id": player["player_id"],
                "name": player["name"],
                "position": "G",
                "avs_games": 60,
                "nhl_games": games,
                "last_age": 27 if limited else 31,
                "path": path,
                "features": {
                    "relative_save_percentage": (0.01, 0.0, 0.02, -0.01)[index],
                    "adjusted_shots_per_game": (30.0, 28.0, 32.0, 30.0)[index],
                    "schedule_adjusted_games_per_season": (50.0, 45.0, 55.0, 52.0)[index],
                    "log_games": log1p(games),
                },
            }
    calls = []

    class FrozenProfiles:
        def __init__(self, *_args):
            pass

        def __call__(self, player, league, last, *, max_age=None, end_at_last_played=False):
            calls.append((player["player_id"], max_age, end_at_last_played, last))
            result = deepcopy(profiles[player["player_id"], max_age is not None])
            result["avs_games"] = player["avs_games"]
            return result

    monkeypatch.setattr(goalie_revision.era, "EraProfiles", FrozenProfiles)
    saved = {
        "player_seasons": {},
        "league_seasons": {sid: {"shutout_rate": 0.05} for sid in seasons},
    }
    quality = {
        "player_seasons": {},
        "league_seasons": {sid: {"starts": 100, "quality_starts": 50} for sid in seasons},
    }
    shutouts = ((4, 3), (1, 2), (4, 4), (2, 3))
    quality_starts = ((30, 30), (15, 20), (30, 34), (27, 28))
    for index, pid in enumerate(ids):
        for offset, sid in enumerate(seasons):
            starts = (40, 45)[offset]
            saved["player_seasons"][pid, sid] = {
                "games": 50,
                "starts": starts,
                "shutouts": shutouts[index][offset],
                "seconds": 150000,
            }
            quality["player_seasons"][pid, sid] = {
                "games": 50,
                "starts": starts,
                "quality_starts": quality_starts[index][offset],
            }
    rows = []
    for window in ("whole_career", "age_aligned"):
        target = profiles[101, False]
        pool = [profiles[pid, window == "age_aligned"] for pid in ids[1:]]
        ranked, scales = analysis._rank(target, pool, analysis.GOALIE_WEIGHTS)
        rows.append(
            {
                "window": window,
                "player_id": 101,
                "name": target["name"],
                "position": "G",
                "age": 27,
                "games": target["nhl_games"],
                "candidate_ids": list(ids[1:]),
                "ranked_candidate_ids": list(ids[1:]),
                "weights": dict(analysis.GOALIE_WEIGHTS),
                "scales": scales,
                "target_features": deepcopy(target["features"]),
                "matches": [
                    {
                        "player_id": p["player_id"],
                        "name": p["name"],
                        "games": p["nhl_games"],
                        "distance": p["distance"],
                        "features": deepcopy(p["features"]),
                    }
                    for p in ranked
                ],
            }
        )
    rows.append(
        {
            "window": "whole_career",
            "player_id": 301,
            "name": "Unchanged Skater",
            "position": "F",
            "candidate_ids": [401],
            "ranked_candidate_ids": [401],
            "weights": {"goals_per_82": 1},
            "target_features": {"goals_per_82": 1},
            "scales": {"goals_per_82": 1},
            "matches": [{"player_id": 401, "name": "Skater Alumnus", "distance": 0.5}],
            "skater_audit": {"keep_every_field": [1, 2, 3]},
        }
    )
    baseline = {
        "config": {"last_season": 20252026, "min_avs_goalie_games": 50, "min_avs_skater_games": 82},
        "rows": rows,
        "unranked": [{"player_id": 999, "window": "whole_career", "reason": "insufficient_data"}],
    }
    return baseline, bundle, saved, quality, profiles, calls


def test_goalie_revision_changes_only_two_features_and_leaves_skater_results_untouched(monkeypatch):
    baseline, bundle, saved, quality, _, calls = revision_fixture(monkeypatch)
    original = deepcopy((baseline, bundle, saved, quality))
    report = goalie_revision.revise(baseline, bundle, saved, quality)
    assert (baseline, bundle, saved, quality) == original
    assert report["rows"][-1] == baseline["rows"][-1]
    assert report["unranked"] == baseline["unranked"]
    expected = {
        "relative_save_percentage",
        "adjusted_shots_per_game",
        goalie_performance.QUALITY_FEATURE,
        goalie_performance.SHUTOUT_FEATURE,
    }
    for old, row in zip(baseline["rows"][:2], report["rows"][:2], strict=True):
        assert set(row["weights"]) == expected
        assert set(row["target_features"]) == expected
        assert set(row["weights"].values()) == {0.25}
        assert row["candidate_ids"] == old["candidate_ids"]
        assert row["ranked_candidate_ids"] == old["ranked_candidate_ids"]
        assert row["games"] == old["games"]
        for key in ("relative_save_percentage", "adjusted_shots_per_game"):
            assert row["target_features"][key] == old["target_features"][key]
        assert row["goalie_context"]["starts"] == 85
        assert row["goalie_context"]["quality_starts"] == 60
        assert row["target_features"][goalie_performance.QUALITY_FEATURE] == pytest.approx(
            100 * (60 - 42.5) / 85
        )
    assert any(pid == 201 and age == 27 and not whole for pid, age, whole, _ in calls)
    assert any(pid == 201 and age is None and whole for pid, age, whole, _ in calls)


@pytest.mark.parametrize("missing", ["target", "candidate", "all_quality"])
def test_goalie_revision_rejects_partial_quality_coverage_instead_of_shrinking_the_pool(
    monkeypatch, missing
):
    baseline, bundle, saved, quality, _, _ = revision_fixture(monkeypatch)
    if missing == "all_quality":
        quality = None
    else:
        del quality["player_seasons"][101 if missing == "target" else 201, 20232024]
    with pytest.raises((ValueError, analysis.ProfileError)):
        goalie_revision.revise(baseline, bundle, saved, quality)


@pytest.mark.parametrize(
    "change", ["target_sv", "candidate_sv", "target_games", "cutoff", "tenure"]
)
def test_goalie_revision_rejects_unrelated_retained_profile_or_scope_changes(monkeypatch, change):
    baseline, bundle, saved, quality, profiles, _ = revision_fixture(monkeypatch)
    if change == "target_sv":
        profiles[101, False]["features"]["relative_save_percentage"] += 0.01
    elif change == "candidate_sv":
        profiles[201, False]["features"]["relative_save_percentage"] += 0.01
    elif change == "target_games":
        baseline["rows"][0]["games"] += 1
    elif change == "cutoff":
        bundle["config"]["last_season"] = 20262027
    else:
        bundle["players"][1]["avs_games"] = 49
    with pytest.raises(ValueError):
        goalie_revision.revise(baseline, bundle, saved, quality)
