"""Hand-auditable nearest-neighbour examples protect the common reference ruler."""

from math import sqrt

import pytest

from avalanche_career_comps.distinctiveness import neighbour_audit


def profile(pid, value):
    return {"player_id": pid, "name": str(pid), "features": {"x": value}}


def test_reference_self_exclusion_and_known_nearest_gap_ratio():
    reference = [profile(1, 0), profile(2, 2), profile(3, 4)]
    report = neighbour_audit(profile(7, 8), reference, {"x": 5})
    scale = sqrt(8 / 3)
    assert report["scales"]["x"] == pytest.approx(scale)
    assert report["closest_match"]["player_id"] == 3
    assert report["target_distance"] == pytest.approx(4 / scale)
    assert report["reference_median"] == pytest.approx(2 / scale)
    assert report["ratio_to_median"] == pytest.approx(2)
    assert all(row["neighbour"]["player_id"] != row["player_id"] for row in report["reference"])
    assert report["reference_gaps_below_target"] == 3


def test_extreme_target_cannot_change_historical_scales_or_reference_gaps():
    reference = [profile(1, 0), profile(2, 2), profile(3, 4)]
    ordinary = neighbour_audit(profile(7, 8), reference, {"x": 1})
    extreme = neighbour_audit(profile(7, 800), reference, {"x": 1})
    assert extreme["scales"] == ordinary["scales"]
    assert extreme["reference"] == ordinary["reference"]
    assert extreme["ratio_to_median"] > ordinary["ratio_to_median"]


def test_stat_units_do_not_change_fixed_standardized_gaps():
    values = [0, 2, 4]
    ordinary = neighbour_audit(
        profile(7, 8), [profile(i, x) for i, x in enumerate(values)], {"x": 1}
    )
    changed = neighbour_audit(
        profile(7, 17 * 8 + 100), [profile(i, 17 * x + 100) for i, x in enumerate(values)], {"x": 1}
    )
    assert changed["target_distance"] == pytest.approx(ordinary["target_distance"])
    assert changed["ratio_to_median"] == pytest.approx(ordinary["ratio_to_median"])


def test_second_neighbour_uses_the_same_order_for_target_and_reference():
    report = neighbour_audit(
        profile(7, 8), [profile(1, 0), profile(2, 2), profile(3, 4)], {"x": 1}, k=2
    )
    assert report["target_neighbour"]["player_id"] == 2
    assert report["ratio_to_median"] == pytest.approx(1.5)


def test_zero_reference_median_is_undefined_not_infinite_evidence():
    report = neighbour_audit(profile(7, 1), [profile(1, 0), profile(2, 0), profile(3, 0)], {"x": 1})
    assert report["reference_median"] == 0
    assert report["ratio_to_median"] is None


@pytest.mark.parametrize(
    "reference,k",
    [
        ([profile(7, 0), profile(1, 1)], 1),
        ([profile(1, 0), profile(1, 1)], 1),
        ([profile(1, 0), profile(2, 1)], 2),
    ],
)
def test_invalid_reference_identity_or_neighbour_order_is_rejected(reference, k):
    with pytest.raises(ValueError):
        neighbour_audit(profile(7, 3), reference, {"x": 1}, k=k)
