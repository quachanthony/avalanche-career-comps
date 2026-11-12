"""Keep official quality-start counts complete, traceable and distinct from missing data."""

import pytest

from avalanche_career_comps import goalie_quality, inputs


def raw(pid, season, games, starts, quality, percentage):
    return {
        "playerId": pid,
        "seasonId": season,
        "gamesPlayed": games,
        "gamesStarted": starts,
        "qualityStart": quality,
        "qualityStartsPct": percentage,
    }


def quality_fixture(tmp_path, change=None):
    selected = [raw(9, 20202021, 12, 10, 6, 0.6), raw(9, 20212022, 1, 0, 0, None)]
    league = [*selected, raw(8, 20202021, 12, 10, 5, 0.5), raw(8, 20212022, 10, 10, 5, 0.5)]
    if change == "missing_count":
        selected[0]["qualityStart"] = None
    elif change == "too_many":
        selected[0]["qualityStart"] = 11
    elif change == "wrong_fraction":
        selected[0]["qualityStartsPct"] = 0.8
    elif change == "missing_season":
        selected.pop()
    elif change == "duplicate":
        selected.append(dict(selected[0]))
    elif change == "league_disagrees":
        league = [dict(r) for r in league]
        league[0]["qualityStart"] = 5
        league[0]["qualityStartsPct"] = 0.5
    records = []
    for name, rows in (("player.json", selected), ("league.json", league)):
        path = tmp_path / name
        inputs.write_json(path, {"data": rows, "total": len(rows)})
        records.append({"file": name, "sha256": inputs.digest(path)})
    inputs.write_json(
        tmp_path / "coverage-audit.json",
        {
            "quality_start_coverage_complete": True,
            "quality_start_count_issues": [],
            "records": records[:1],
            "league_records": records[1:],
            "league_coverage": {"expected_player_seasons": len(league)},
            "quality_definition": {"provider": "NHL fixed .900 rule"},
            "issues": [{"key": "timeOnIce", "expected": 100, "actual": 105}],
        },
    )
    inputs.write_json(
        tmp_path / "manifest.json",
        {"outputs_sha256": {p.name: inputs.digest(p) for p in tmp_path.iterdir()}},
    )
    expected = {
        (9, 20202021): {"games": 12, "starts": 10},
        (9, 20212022): {"games": 1, "starts": 0},
    }
    league_expected = {20202021: {"games": 24, "starts": 20}, 20212022: {"games": 11, "starts": 10}}
    return expected, league_expected


def test_quality_counts_preserve_zero_start_seasons_and_weight_league_rates_by_starts(tmp_path):
    expected, league = quality_fixture(tmp_path)
    result = goalie_quality.load_quality(tmp_path, expected, league)
    assert result["player_seasons"][9, 20212022]["quality_starts"] == 0
    assert result["league_seasons"][20202021]["quality_start_rate"] == 11 / 20
    assert result["league_seasons"][20212022]["quality_start_rate"] == 0.5
    assert result["coverage"]["other_metric_disagreements"][0]["key"] == "timeOnIce"
    assert result["player_seasons"][9, 20202021]["source_ordinal"] == 0


@pytest.mark.parametrize(
    "change",
    [
        "missing_count",
        "too_many",
        "wrong_fraction",
        "missing_season",
        "duplicate",
        "league_disagrees",
    ],
)
def test_quality_loader_rejects_missing_or_inconsistent_counts_instead_of_using_zero(
    tmp_path, change
):
    expected, league = quality_fixture(tmp_path, change)
    with pytest.raises(ValueError):
        goalie_quality.load_quality(tmp_path, expected, league)


def test_quality_loader_rejects_changed_source_bytes(tmp_path):
    expected, league = quality_fixture(tmp_path)
    (tmp_path / "player.json").write_text("{}")
    with pytest.raises(ValueError, match="manifest"):
        goalie_quality.load_quality(tmp_path, expected, league)


def test_quality_loader_reconciles_player_and_league_exposures_to_saved_inputs(tmp_path):
    expected, league = quality_fixture(tmp_path)
    expected[9, 20202021]["starts"] = 9
    with pytest.raises(ValueError, match="career totals"):
        goalie_quality.load_quality(tmp_path, expected, league)
    expected[9, 20202021]["starts"] = 10
    league[20202021]["starts"] = 19
    with pytest.raises(ValueError, match="league summary"):
        goalie_quality.load_quality(tmp_path, expected, league)
