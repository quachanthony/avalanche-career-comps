"""Export separate full-career and age-adjusted article charts without repeated captions."""

from __future__ import annotations

import os
import re
import unicodedata
from copy import deepcopy
from html import escape
from pathlib import Path

from . import inputs, radar, special_teams
from .publication import BLUE, BURGUNDY, ICE, MUTED, _save, _style, plt

WINDOWS = {
    "whole_career": ("full-career", "Full career"),
    "age_aligned": ("age-adjusted", "Age adjusted"),
}
LABELS = {
    "goals_per_82": "GOALS",
    "assists_per_82": "ASSISTS",
    "shots_per_82": "SHOTS",
    "pim_per_82": "PENALTY MINUTES / 82",
    "log_games": "CAREER GAMES",
    special_teams.PP_FEATURE: "POWER-PLAY POINTS",
    special_teams.PK_FEATURE: "PK MINUTES / GAME",
    "relative_save_percentage": "SAVE % VS LEAGUE",
    "adjusted_shots_per_game": "SHOTS FACED / GAME",
    "schedule_adjusted_games_per_season": "APPEARANCES / SEASON",
    "quality_starts_above_league_per_100_starts": "QUALITY START RATE\nVS LEAGUE",
    "era_relative_shutouts_per_100_starts": "SHUTOUT RATE\nVS LEAGUE",
}
GOALIE_PERFORMANCE_FEATURES = {
    "quality_starts_above_league_per_100_starts",
    "era_relative_shutouts_per_100_starts",
}
LEGACY_GOALIE_NOTE = (
    "Goalies show save percentage above league in percentage points, era-adjusted shots faced "
    "per game, and appearances per 82-game season."
)
PERFORMANCE_GOALIE_NOTE = (
    "Goalies show SV+ (save percentage above league in percentage points), SA/G "
    "(era-adjusted shots faced per game), QS+ and SO+. QS+ and SO+ are excess quality "
    "starts and shutouts per 100 starts relative to each season's league rates. "
    "The NHL counts a quality start using its fixed .900 save-percentage threshold; "
    "the league comparison adjusts that frequency for era. Appearances are background "
    "sample sizes and do not carry similarity weight."
)

ARTICLE_NOTE = """Burgundy identifies the current Avalanche player and blue identifies the matched alumnus, including the numbers. Closer markers on a spoke mean more similar values for that stat. The filled shapes show profiles; weighted statistical gaps determine the match. The dark ring is the alumni average. Each chart has its own comparison pool and scales.

Skater goals, assists, shots and power-play points are era-adjusted rates per 82 games. Penalty minutes are unadjusted per 82; PK usage is minutes:seconds per game where included. Career games are totals, log-scaled in the model. Goalies show save percentage above league in percentage points, era-adjusted shots faced per game, and appearances per 82-game season. Full-career charts use all observed NHL seasons through 2025–26. The separate age-adjusted charts stop alumni at the current player's season-age, allowing a one-year-short profile.
"""


def eligibility_note(report):
    """Describe the effective tenure rule without changing frozen source snapshots."""
    config = report.get("config", {})
    if not {"min_avs_skater_games", "min_avs_goalie_games"} <= config.keys():
        return ""
    return (
        f"Alumni need at least {config['min_avs_skater_games']} Colorado regular-season games "
        f"for skaters or {config['min_avs_goalie_games']} for goalies, counted from 1995–96 onward. "
        "Once eligible, their NHL careers across all teams are compared. "
        "PK-inclusive comparisons additionally require complete audited PK minutes.\n"
    )


def article_note(report):
    """Explain the selected goalie method while preserving archived model wording."""
    note = ARTICLE_NOTE
    if report.get("goalie_method"):
        note = note.replace(LEGACY_GOALIE_NOTE, PERFORMANCE_GOALIE_NOTE)
    return note + "\n" + eligibility_note(report)


def image_stem(player_id, name):
    """Use stable IDs in filenames while keeping them easy to recognize."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return f"{player_id}-{slug}"


def value_formatter(axis, field, data):
    """Keep model values intact while displaying a save-rate gap in percentage points."""
    if axis["key"] == "relative_save_percentage":
        return f"{100 * axis[field + '_raw']:+.2f}"
    if axis["key"] in GOALIE_PERFORMANCE_FEATURES:
        return f"{axis[field + '_raw']:+.2f}"
    return radar._value(axis, field, data)


def chart_data(report):
    """Reconcile plotted coordinates to every saved ranking before drawing."""
    charts, seen = [], set()
    for row in report["rows"]:
        if not row.get("matches"):
            continue
        window = row["window"]
        if window not in WINDOWS:
            raise ValueError(f"Unknown article career window: {window}.")
        key = row["player_id"], window
        if key in seen:
            raise ValueError(f"Duplicate article player-window: {key}.")
        seen.add(key)
        if "hits_per_game" in row["weights"]:
            raise ValueError("The selected article model excludes hits.")
        unknown = set(row["weights"]) - LABELS.keys()
        if unknown:
            raise ValueError(f"Unknown article features: {sorted(unknown)}.")
        match = row["matches"][0]
        axes, distance = radar.axes_from_stats(
            row["target_features"],
            match,
            row["candidate_means"],
            row["scales"],
            row["weights"],
            LABELS,
        )
        charts.append(
            {
                "player_id": row["player_id"],
                "window": window,
                "position": row.get("position", "F"),
                "current": row["name"],
                "historical": match["name"],
                "current_age": row["age"],
                "historical_age": match["last_age"],
                "current_games": row["games"],
                "historical_games": match["games"],
                "candidate_count": len(row["ranked_candidate_ids"]),
                "eligible_count": len(row["candidate_ids"]),
                "pk_status": row["pk_status"],
                "quality_flags": row.get("quality_flags", []),
                "distance": distance,
                "all_pool_without_pk_match": row.get("all_pool_without_pk_match"),
                "same_pool_without_pk_match": row.get("same_pool_without_pk_match"),
                "axes": axes,
                "bounds": radar.radial_bounds(axes),
                "stem": image_stem(row["player_id"], row["name"]),
            }
        )
        if GOALIE_PERFORMANCE_FEATURES <= row["weights"].keys():
            charts[-1].update(
                goalie_performance=True,
                goalie_context=deepcopy(row.get("goalie_context")),
                historical_goalie_context=deepcopy(match.get("goalie_context")),
            )
    return charts


def draw_goalie_appearances(fig, x, y, data, *, fontsize=12, centered=False):
    """Show color-matched sample sizes outside the weighted radar spokes."""
    from matplotlib.offsetbox import AnnotationBbox, HPacker, TextArea

    children = [
        TextArea(text, textprops={"fontsize": fontsize, "color": color})
        for text, color in (
            (f"{data['current_games']:,.0f} appearances", BURGUNDY),
            (" / ", MUTED),
            (f"{data['historical_games']:,.0f} appearances", BLUE),
        )
    ]
    fig.add_artist(
        AnnotationBbox(
            HPacker(children=children, align="baseline", pad=0, sep=3),
            (x, y),
            xycoords="figure fraction",
            box_alignment=(0.5 if centered else 0, 0.5),
            frameon=False,
            annotation_clip=False,
            pad=0,
        )
    )


def draw(data, out):
    """Show identities and profiles without a repeated career-window header."""
    _style()
    fig = plt.figure(figsize=(11.2, 10.4), facecolor=ICE)
    fig.text(0.065, 0.893, data["current"], fontsize=30, weight="bold", color=BURGUNDY)
    fig.text(0.065, 0.841, f"vs. {data['historical']}", fontsize=26, weight="bold", color=BLUE)
    if data["window"] == "age_aligned":
        fig.text(0.065, 0.803, f"Through age {data['current_age']}", fontsize=12, color=MUTED)
    height = 0.765
    if data.get("goalie_performance"):
        aligned = data["window"] == "age_aligned"
        draw_goalie_appearances(fig, 0.065, 0.773 if aligned else 0.803, data)
        if aligned:
            height = 0.73
    ax = fig.add_axes([0.025, 0.025, 0.95, height])
    radar.draw_spokes(
        ax,
        data,
        bounds=data["bounds"],
        label_size=12,
        label_sd=False,
        value_formatter=value_formatter,
    )
    _save(fig, out, data["stem"])


def coverage_text(data):
    """Keep coverage and controls available outside the article image."""
    text = f"Closest of {data['candidate_count']} ranked alumni; weighted distance {data['distance']:.3f}."
    if data["pk_status"] == "pk_included":
        text += f" PK minutes were included. {data['candidate_count']} of {data['eligible_count']} eligible alumni had complete audited PK minutes."
        if data.get("all_pool_without_pk_match"):
            text += f" Without PK and its coverage filter, the closest match was {data['all_pool_without_pk_match']}."
        if data.get("same_pool_without_pk_match"):
            text += f" On this same covered pool without PK, the closest match was {data['same_pool_without_pk_match']}."
    elif data["pk_status"] == "not_applicable_goalie":
        if data.get("goalie_performance"):
            text += (
                " The goalie model uses save percentage above league, era-adjusted shots "
                "faced per game, quality-start rate above league and shutout rate above league. "
                "The two start-rate differences are per 100 starts; appearances are context only."
            )
        else:
            text += " The separate four-feature goalie model applies."
    elif data["pk_status"] == "target_pk_coverage_incomplete":
        text += " PK was omitted because the current player's career-window minutes are incomplete."
    elif data["pk_status"] == "insufficient_pk_candidates":
        text += (
            " PK was omitted because fewer than two eligible alumni had complete audited minutes."
        )
    else:
        text += " PK was omitted because the current player was below the regular-usage threshold."
    if data["window"] == "age_aligned" and data["historical_age"] != data["current_age"]:
        text += f" The alumnus's observed profile ends at age {data['historical_age']}, one season-age earlier."
    limitations = []
    if "small_comparison_pool" in data.get("quality_flags", []):
        limitations.append(f"only {data['candidate_count']} eligible alumni were ranked")
    if "distant_analogue" in data.get("quality_flags", []):
        limitations.append("the nearest career remains a distant match")
    if limitations:
        text += " No strong analogue: " + "; ".join(limitations) + "."
    return text


def _unranked_for_window(report, window):
    return [row for row in report.get("unranked", []) if row.get("window", window) == window]


def write_gallery(report, charts, out, results):
    """Make full careers the first page and age adjustment an explicitly separate view."""
    style = """body{margin:0;background:#eff5f8;color:#182d3c;font:16px/1.55 system-ui,sans-serif}main{max-width:1300px;margin:auto;padding:30px clamp(16px,4vw,55px)}h1{font-size:clamp(27px,4vw,43px);margin:0}a{color:#236192}nav{display:flex;gap:20px;margin:18px 0}section{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px}article{background:white;border:1px solid #c8d9e4;border-radius:9px;overflow:hidden}h2,p,details{margin:14px 18px}h2{font-size:20px}img{width:100%;display:block}.note{white-space:pre-wrap;background:white;border:1px solid #c8d9e4;padding:18px;margin:25px 0}details{font-size:14px}.unranked{padding:18px}header p{margin-left:0}@media(max-width:760px){section{grid-template-columns:1fr}}
"""
    for window, (directory, title) in WINDOWS.items():
        selected = sorted(
            (c for c in charts if c["window"] == window),
            key=lambda c: (c["position"] == "G", c["current"]),
        )
        cards = []
        for data in selected:
            stem, name = data["stem"], escape(data["current"])
            cards.append(
                f'''<article><h2>{name} / {escape(data["historical"])}</h2><a href="{stem}.png"><img src="{stem}.png" alt="{name} and {escape(data["historical"])}, {title.lower()} comparison" loading="lazy"></a><p><a href="{stem}.png">PNG</a> · <a href="{stem}.svg">SVG</a></p><details><summary>Coverage and comparison details</summary><p>{escape(coverage_text(data))}</p></details></article>'''
            )
        for row in _unranked_for_window(report, window):
            name, reason = (
                escape(row["name"]),
                escape(row.get("reason", "insufficient_data").replace("_", " ")),
            )
            cards.append(
                f'<article class="unranked"><h2>{name}</h2><p>No comparison chart: {reason}.</p></article>'
            )
        window_csv = results.with_name(f"{window}-matches.csv")
        matches_path = window_csv if window_csv.exists() else results.with_name("matches.csv")
        matches_url = escape(os.path.relpath(matches_path, out / directory))
        (out / directory / "index.html").write_text(
            f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} / Avalanche career comparisons</title><style>{style}</style><main><header><h1>{title} comparisons</h1><nav><a href="../full-career/index.html">Full career</a><a href="../age-adjusted/index.html">Age adjusted</a><a href="../article-note.txt">One-time article note</a></nav><p>{len(selected)} ranked players. The explanatory note is supplied once, outside the images.</p><p><a href="{matches_url}">All match results</a> · <a href="../index.html">Article package</a></p></header><section>{"".join(cards)}</section></main></html>''',
            encoding="utf-8",
        )
    (out / "index.html").write_text(
        f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Avalanche career comparisons</title><style>{style}</style><main><header><h1>Avalanche career comparisons</h1><nav><a href="full-career/index.html"><strong>Full career — main analysis</strong></a><a href="age-adjusted/index.html">Age adjusted — separate analysis</a></nav><p>Individual article images contain the player identities and statistical profile, with no repeated career-window header. Save the PNG files for Substack; SVG files remain editable.</p></header><h2>One-time article note</h2><p><a href="article-note.txt">Open the copy-ready text</a></p><div class="note">{escape(article_note(report))}</div></main></html>""",
        encoding="utf-8",
    )


def publish(report, out, results):
    """Export a new package and leave every prior chart version untouched."""
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Choose an empty article output directory.")
    charts = chart_data(report)
    for directory, _ in WINDOWS.values():
        (out / directory).mkdir(parents=True, exist_ok=True)
    for data in charts:
        draw(data, out / WINDOWS[data["window"]][0])
    (out / "article-note.txt").write_text(article_note(report), encoding="utf-8")
    inputs.write_json(
        out / "chart-data.json", {"charts": charts, "unranked": report.get("unranked", [])}
    )
    write_gallery(report, charts, out, Path(results))
    inputs.write_json(
        out / "manifest.json",
        {
            "results_sha256": inputs.digest(results),
            "code_sha256": {Path(p).name: inputs.digest(p) for p in (__file__, radar.__file__)},
            "outputs_sha256": {
                str(p.relative_to(out)): inputs.digest(p)
                for p in sorted(out.rglob("*"))
                if p.is_file()
            },
        },
    )
    return charts
