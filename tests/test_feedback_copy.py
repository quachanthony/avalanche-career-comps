"""Keep article explanations consistent with the revised figures and method."""

from avalanche_career_comps import feedback_analysis, feedback_copy


def test_production_only_copy_cannot_repeat_the_old_multiplier_or_career_weight():
    reports, _ = feedback_analysis.analyze(include_career_games=False)
    copy = feedback_copy.explanations(reports)
    assert "5.1 times" in copy["cale"]
    assert "4.6" not in copy["cale"]
    assert "Ray Bourque" in copy["cale"]
    assert "do not affect the match" in copy["short_method"]
    assert "log-transformed" not in copy["weights"]
    assert "25.0%" in copy["weights"]
    assert "1997–98" in copy["pk"] and "1995" not in copy["pk"]
    assert "no NHL regular-season" in copy["hughes"]
    assert "1.140" in copy["forsberg"] and "1.144" in copy["forsberg"]
    assert "almost tied" in copy["forsberg"]


def test_gp_sensitivity_has_its_own_cale_ratio_and_explanation():
    reports, _ = feedback_analysis.analyze(include_career_games=True)
    copy = feedback_copy.explanations(reports)
    assert "4.6 times" in copy["cale"]
    assert "log(1 + games)" in copy["short_method"]
    assert "Mikko Rantanen" in copy["forsberg"]
