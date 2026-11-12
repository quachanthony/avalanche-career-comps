"""Protect the public reproduction boundary and the article's selected results."""

import socket

import pytest

from avalanche_career_comps import inputs, pipeline


def test_portable_article_reproduces_published_results_without_network(monkeypatch, tmp_path):
    def deny_network(*args, **kwargs):
        raise AssertionError("Article reproduction must not contact a data provider or database.")

    monkeypatch.setattr(socket, "create_connection", deny_network)
    before = inputs.digest(pipeline.DEFAULT_INPUTS)
    reports = pipeline.run(tmp_path / "article", figures=False)
    assert inputs.digest(pipeline.DEFAULT_INPUTS) == before
    assert len(reports["roster"]["rows"]) == 42
    assert {row["window"] for row in reports["roster"]["rows"]} == {"whole_career", "age_aligned"}
    assert reports["makar"]["isolation"]["reference_count"] == 45
    assert len(reports["forsberg"]["candidate_ids"]) == 97
    manifest = inputs.read_json(tmp_path / "article" / "manifest.json")
    assert manifest["network_requests"] is False
    assert manifest["warehouse_writes"] is False
    for name, digest in manifest["outputs_sha256"].items():
        assert inputs.digest(tmp_path / "article" / name) == digest


def test_changed_inputs_fail_before_analysis(tmp_path):
    (tmp_path / "article-inputs.json").write_text("{}\n")
    manifest = pipeline.DEFAULT_INPUTS.with_name("input-manifest.json")
    (tmp_path / manifest.name).write_bytes(manifest.read_bytes())
    with pytest.raises(ValueError, match="checksum"):
        pipeline.load(tmp_path / "article-inputs.json")


def test_duplicate_observations_and_changed_result_identities_are_rejected():
    with pytest.raises(ValueError, match="Duplicate input grain"):
        pipeline.index_rows(
            [{"player_id": 1, "season_id": 20252026}] * 2, ("player_id", "season_id")
        )
    with pytest.raises(ValueError, match="Published result changed"):
        pipeline.check_expected({"match": "Player B"}, {"match": "Player A"})


def test_rerun_does_not_overwrite_existing_artifacts(tmp_path):
    existing = tmp_path / "results.json"
    existing.write_text("preserved")
    with pytest.raises(ValueError, match="empty output directory"):
        pipeline.run(tmp_path)
    assert existing.read_text() == "preserved"
