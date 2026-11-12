"""Rebuild the published article and its age supplement from portable season-level inputs."""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import platform
from html import escape
from math import isclose
from pathlib import Path

from . import (
    article_analysis,
    article_radar,
    goalie_revision,
    inputs,
    lineup_radar,
    makar_compact,
    makar_compact_graphics,
    makar_deep_dive,
    reverse_similarity,
)

PROJECT = Path(__file__).resolve().parents[2]
DEFAULT_INPUTS = PROJECT / "research" / "article-inputs.json"


def index_rows(rows, keys):
    """Restore JSON rows to keyed observations, rejecting ambiguous duplicate identities."""
    indexed = {}
    for row in rows:
        key = tuple(row[k] for k in keys)
        key = key[0] if len(key) == 1 else key
        if key in indexed:
            raise ValueError(f"Duplicate input grain {keys}: {key}.")
        indexed[key] = row
    return indexed


def load(path=DEFAULT_INPUTS):
    """Verify the published snapshot before restoring explicit player/season grains."""
    path = Path(path)
    manifest = inputs.read_json(path.with_name("input-manifest.json"))
    if inputs.digest(path) != manifest["sha256"]:
        raise ValueError("Article inputs differ from the published checksum.")
    data = inputs.read_json(path)
    scoring = index_rows(data["scoring"], ("player_id", "season_id"))
    rates = {sid: row["rate"] for sid, row in index_rows(data["pp_rates"], ("season_id",)).items()}
    ice = {
        key: (row["games"], row["seconds"])
        for key, row in index_rows(data["ice_time"], ("player_id", "season_id")).items()
    }
    goalie = {}
    for label in ("goalie_saved", "goalie_quality"):
        goalie[label] = {
            **data[label],
            "player_seasons": index_rows(data[label]["player_seasons"], ("player_id", "season_id")),
            "league_seasons": index_rows(data[label]["league_seasons"], ("season_id",)),
        }
    return data["bundle"], scoring, rates, ice, goalie, manifest


def analyze(path=DEFAULT_INPUTS):
    """Recompute era features, both roster windows, goalie rates and both special analyses."""
    bundle, scoring, rates, ice, goalie, manifest = load(path)
    bundle, policy = article_analysis.with_skater_eligibility(bundle, 82)
    baseline = {
        **article_analysis.rerun(bundle, scoring, rates, ice),
        "config": bundle["config"],
        "roster": bundle["roster"],
        "window_order": list(article_analysis.WINDOWS),
        "era_method": "separate_assists",
        "hits_included": False,
        "eligibility_policy": policy,
    }
    roster = goalie_revision.revise(
        baseline, bundle, goalie["goalie_saved"], goalie["goalie_quality"]
    )
    makar = makar_compact.consolidate(
        makar_deep_dive.analyze(bundle, scoring, rates, ice, baseline), baseline
    )
    forsberg = reverse_similarity.compare(bundle, 8458520, scoring, rates, ice)
    return {"roster": roster, "makar": makar, "forsberg": forsberg}, manifest


def numerical_summary(reports):
    """Keep a small, reviewable regression record of the published numerical conclusions."""
    return {
        "roster": [
            {
                "window": row["window"],
                "player_id": row["player_id"],
                "name": row["name"],
                "candidate_ids": row["candidate_ids"],
                "ranked_candidate_ids": row["ranked_candidate_ids"],
                "target_features": row["target_features"],
                "weights": row["weights"],
                "matches": [
                    {key: match[key] for key in ("player_id", "name", "distance", "features")}
                    for match in row["matches"]
                ],
            }
            for row in reports["roster"]["rows"]
        ],
        "unranked": reports["roster"]["unranked"],
        "makar": {
            "profiles": reports["makar"]["profiles"],
            "typical_gap": reports["makar"]["isolation"]["typical_gap"],
            "rows": reports["makar"]["isolation"]["rows"],
        },
        "forsberg": {
            "candidate_ids": reports["forsberg"]["candidate_ids"],
            "matches": reports["forsberg"]["matches"],
        },
    }


def check_expected(actual, expected):
    """Require identical identities and definitions, allowing only floating-point roundoff."""

    def compare(a, b, trail):
        if isinstance(a, dict) and isinstance(b, dict):
            if a.keys() != b.keys():
                raise ValueError(f"Published result keys changed at {trail}.")
            for key in a:
                compare(a[key], b[key], f"{trail}.{key}")
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                raise ValueError(f"Published result count changed at {trail}.")
            for i, (left, right) in enumerate(zip(a, b, strict=True)):
                compare(left, right, f"{trail}[{i}]")
        elif (
            isinstance(a, (int, float)) and not isinstance(a, bool) and isinstance(b, (int, float))
        ):
            if not isclose(a, b, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError(f"Published numerical result changed at {trail}: {a} != {b}.")
        elif a != b:
            raise ValueError(f"Published result changed at {trail}: {a!r} != {b!r}.")

    compare(actual, expected, "results")


def gallery(directory, title, images):
    """Write an offline image gallery with portable links, without repeating image captions."""
    figures = "".join(
        f'<figure><a href="{stem}.png"><img src="{stem}.png" alt="{escape(alt)}"></a>'
        f'<p><a href="{stem}.png">PNG</a> · <a href="{stem}.svg">SVG</a></p></figure>'
        for stem, alt in images
    )
    (directory / "index.html").write_text(
        f'<!doctype html><html lang="en"><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>'
        "<style>body{max-width:900px;margin:25px auto;padding:0 14px;font:16px/1.5 system-ui;"
        "background:#eff5f8;color:#182d3c}img{width:100%;display:block}figure{margin:25px 0}"
        "a{color:#236192}</style>"
        f'<h1>{title}</h1><p><a href="../index.html">All results and methods</a></p>{figures}</html>',
        encoding="utf-8",
    )


def publish(reports, out):
    """Draw the article's ten figures and eight separate age-adjusted row images."""
    charts = article_radar.chart_data(reports["roster"])
    for window, (directory, title) in article_radar.WINDOWS.items():
        destination = out / directory
        destination.mkdir()
        rows = lineup_radar.select_rows(charts, reports["roster"]["unranked"], window)
        for row in rows:
            lineup_radar.draw_row(row, window, destination)
        images = [(row["stem"], " / ".join(p["current"] for p in row["members"])) for row in rows]
        if window == "whole_career":
            makar_compact_graphics.draw_radar(reports["makar"], destination)
            reverse_similarity.draw(reports["forsberg"], destination)
            images.extend(
                [
                    ("five-player-radar", "All Hail Cale: five career profiles"),
                    (
                        "reverse-career-webs",
                        "Loosely, the Moose: Peter Forsberg's three closest matches",
                    ),
                ]
            )
        gallery(destination, title, images)
    (out / "article-note.txt").write_text(
        lineup_radar.article_note(reports["roster"]), encoding="utf-8"
    )
    (out / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Avalanche career comparisons</title>'
        "<style>body{max-width:800px;margin:40px auto;font:18px/1.6 system-ui;padding:15px}</style>"
        "<h1>Avalanche career comparisons</h1><ul>"
        '<li><a href="full-career/index.html">Article figures: full observed careers</a></li>'
        '<li><a href="age-adjusted/index.html">Optional supplement: through the same season-age</a></li>'
        '<li><a href="matches.csv">Roster match table</a></li>'
        '<li><a href="article-note.txt">One-time chart explanation</a></li>'
        '<li><a href="roster-results.json">Roster calculations</a></li>'
        '<li><a href="makar-results.json">Cale comparison and nearest-match gaps</a></li>'
        '<li><a href="forsberg-results.json">Forsberg reverse comparison</a></li>'
        '<li><a href="manifest.json">Reproduction manifest</a></li></ul></html>',
        encoding="utf-8",
    )


def run(out, path=DEFAULT_INPUTS, *, figures=True):
    """Run offline and save inputs, code, environment and output fingerprints."""
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Choose an empty output directory to preserve previous results.")
    reports, source_manifest = analyze(path)
    expected = inputs.read_json(PROJECT / "research" / "expected-results.json")
    check_expected(numerical_summary(reports), expected)
    out.mkdir(parents=True, exist_ok=True)
    for name, report in reports.items():
        inputs.write_json(out / f"{name}-results.json", report)
    with (out / "matches.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ("window", "player", "position", "closest_match", "distance", "eligible", "ranked")
        )
        for row in reports["roster"]["rows"]:
            writer.writerow(
                (
                    row["window"],
                    row["name"],
                    row["position"],
                    row["matches"][0]["name"],
                    row["matches"][0]["distance"],
                    len(row["candidate_ids"]),
                    len(row["ranked_candidate_ids"]),
                )
            )
    if figures:
        publish(reports, out)
    if inputs.digest(path) != source_manifest["sha256"]:
        raise ValueError("Article inputs changed during reproduction; use a stable snapshot.")
    inputs.write_json(
        out / "manifest.json",
        {
            "input_sha256": inputs.digest(path),
            "source_manifest_sha256": inputs.digest(Path(path).with_name("input-manifest.json")),
            "core_input_fingerprint": source_manifest["article_reference"][
                "verified_warehouse_fingerprint"
            ],
            "python": platform.python_version(),
            "packages": {p: importlib.metadata.version(p) for p in ("matplotlib", "numpy")},
            "code_sha256": {
                p.name: inputs.digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))
            },
            "outputs_sha256": {
                str(p.relative_to(out)): inputs.digest(p)
                for p in sorted(out.rglob("*"))
                if p.is_file()
            },
            "network_requests": False,
            "warehouse_writes": False,
            "randomness": False,
        },
    )
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=DEFAULT_INPUTS)
    parser.add_argument(
        "--out", type=Path, default=Path("local/projects/avalanche-career-comps/article")
    )
    parser.add_argument(
        "--no-figures", action="store_true", help="Check and export numerical results only."
    )
    args = parser.parse_args()
    run(args.out, args.inputs, figures=not args.no_figures)
    print(f"Verified article results saved under {args.out}.")


if __name__ == "__main__":
    main()
