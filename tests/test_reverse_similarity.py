"""Keep current players eligible in the reverse search without weakening tenure rules."""

from copy import deepcopy

import pytest

from avalanche_career_comps.reverse_similarity import candidate_players, with_eligibility


@pytest.mark.parametrize("minimum, expected", [(82, [2, 3]), (100, [3])])
def test_reverse_cutoff_applies_without_mutating_the_frozen_inputs(minimum, expected):
    bundle = {
        "config": {"min_avs_skater_games": 100},
        "players": [
            {"player_id": 1, "position": "F", "avs_games": 500},
            {"player_id": 2, "position": "C", "avs_games": 82},
            {"player_id": 3, "position": "F", "avs_games": 100},
            {"player_id": 4, "position": "F", "avs_games": 81},
        ],
    }
    original = deepcopy(bundle)
    effective = with_eligibility(bundle, minimum)
    assert bundle == original
    assert [p["player_id"] for p in candidate_players(effective, 1)[1]] == expected


@pytest.mark.parametrize("minimum", [49, 0, -1, True, 82.5])
def test_reverse_cutoff_cannot_outrun_the_frozen_player_inventory(minimum):
    with pytest.raises(ValueError, match="at least 50"):
        with_eligibility({}, minimum)


def test_reverse_candidates_include_current_and_former_peers_and_exclude_self():
    def player(pid, **changes):
        return {
            "player_id": pid,
            "name": f"Player {pid}",
            "position": "F",
            "avs_games": 100,
            **changes,
        }

    target = player(1)
    bundle = {
        "config": {"min_avs_skater_games": 100},
        "roster": [{"player_id": 2}],
        "players": [
            target,
            player(2, position="C"),
            player(3),
            player(4, avs_games=99),
            player(5, position="D"),
            player(6, avs_games=0),
        ],
    }
    selected, candidates = candidate_players(bundle, 1)
    assert selected == target
    assert [p["player_id"] for p in candidates] == [2, 3]


def test_reverse_candidates_reject_duplicate_identity():
    player = {"player_id": 1, "position": "F", "avs_games": 100}
    with pytest.raises(ValueError, match="Duplicate"):
        candidate_players({"players": [player, player]}, 1)
