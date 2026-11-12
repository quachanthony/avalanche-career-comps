"""Publish readable article figures, mobile alternatives, and substantive image alt text."""

from __future__ import annotations

import csv
import re
from html import escape
from math import ceil, sqrt
from pathlib import Path

from . import article_radar, lineup_radar, makar_compact_graphics, radar
from .publication import BLUE, BURGUNDY, ICE, INK, MUTED, _save, _style, np, plt

MACKINNON = 8477492
MAKAR = 8480069
SECTIONS = {"F": "Forwards", "D": "Defensemen", "G": "Goalies"}
UNITS = {
    "goals_per_82": "era-adjusted goals per 82 games",
    "assists_per_82": "era-adjusted assists per 82 games",
    "shots_per_82": "era-adjusted shots per 82 games",
    "pim_per_82": "penalty minutes per 82 games",
    "log_games": "career NHL games",
    "adjusted_pp_points_per_82": "era-adjusted power-play points per 82 games",
    "pk_minutes_per_game": "penalty-kill minutes per game",
    "relative_save_percentage": "save percentage above league, in percentage points",
    "adjusted_shots_per_game": "era-adjusted shots faced per appearance",
    "quality_starts_above_league_per_100_starts": "excess quality starts per 100 starts",
    "era_relative_shutouts_per_100_starts": "excess shutouts per 100 starts",
}


def display_name(name):
    """Use the same initial style for T.J. Hughes and T.J. Galiardi."""
    return re.sub(r"\bT\.?J\.?\s+", "T.J. ", name)


def _names(data):
    return display_name(data["current"]), display_name(data["historical"])


def _context(fig, center, y, data, fontsize):
    """Keep exposure visible outside the radar when career games carry no weight."""
    if any(axis["key"] == "log_games" for axis in data["axes"]):
        return
    from matplotlib.offsetbox import AnnotationBbox, HPacker, TextArea

    children = [
        TextArea(text, textprops={"fontsize": fontsize, "color": color})
        for text, color in (
            (f"{data['current_games']:,.0f}", BURGUNDY),
            (" / ", MUTED),
            (f"{data['historical_games']:,.0f}", BLUE),
            (" NHL games · unweighted", MUTED),
        )
    ]
    fig.add_artist(
        AnnotationBbox(
            HPacker(children=children, align="baseline", pad=0, sep=1),
            (center, y),
            xycoords="figure fraction",
            box_alignment=(0.5, 0.5),
            frameon=False,
            pad=0,
        )
    )


def _panel(fig, rect, data, window, *, compact=False):
    """Draw one named target/comparison pair with its actual weighted model gap."""
    left, bottom, width, height = rect
    center = left + width / 2
    current = display_name(data["current"])
    title_size = 20 if compact else 24
    fig.text(
        center,
        0.91 if compact else 0.925,
        current,
        ha="center",
        color=BURGUNDY,
        fontsize=title_size,
        weight="bold",
    )
    if data.get("unranked"):
        fig.text(
            center,
            0.49,
            "No NHL games\nthrough 2025–26",
            ha="center",
            va="center",
            color=MUTED,
            fontsize=20 if compact else 23,
            linespacing=1.6,
        )
        return
    _, historical = _names(data)
    fig.text(
        center,
        0.847 if compact else 0.865,
        f"vs. {historical}",
        ha="center",
        color=BLUE,
        fontsize=18 if compact else 21,
        weight="bold",
    )
    precision = data.get("gap_precision", 2)
    gap = f"Gap {data['distance']:.{precision}f}"
    if window == "age_aligned":
        gap += f" · through age {data['current_age']}"
    fig.text(
        center,
        0.785 if compact else 0.802,
        gap,
        ha="center",
        color=INK,
        fontsize=16 if compact else 17.5,
    )
    _context(fig, center, 0.735 if compact else 0.747, data, 12 if compact else 13.5)
    ax = fig.add_axes([left, bottom, width, height])
    lineup_radar.draw_radar(ax, data, font_size=19.5 if compact else 20.5)
    if compact:
        # The larger phone-readable type needs more room outside the polygon.
        ax.set_xlim(-2.15, 2.15)
        ax.set_ylim(-1.9, 1.9)


def draw_individual(data, window, out, stem):
    """Export a square-ish single panel with readable type at a 390-pixel viewport."""
    _style()
    fig = plt.figure(figsize=(7.2, 3.1 if data.get("unranked") else 7.8), facecolor=ICE)
    _panel(fig, (0.04, 0.025, 0.92, 0.655), data, window)
    _save(fig, out, stem)


def draw_overview(members, window, out, stem):
    """Use at most two columns and larger type than the prior three-across figures."""
    if not 1 <= len(members) <= 2:
        raise ValueError("Article overviews support one or two comparisons.")
    if len(members) == 1:
        draw_individual(members[0], window, out, stem)
        return
    _style()
    fig = plt.figure(figsize=(8, 6.6), facecolor=ICE)
    for index, data in enumerate(members):
        _panel(fig, (0.015 + 0.5 * index, 0.015, 0.47, 0.65), data, window, compact=True)
    fig.add_artist(
        plt.Line2D([0.5, 0.5], [0.04, 0.95], transform=fig.transFigure, color="#D5E1E8", lw=0.8)
    )
    _save(fig, out, stem)


def pair_alt(data, window):
    """Describe identities, the comparison window, units and the largest feature gaps."""
    current = display_name(data["current"])
    if data.get("unranked"):
        return (
            f"{current}: no NHL regular-season games through the 2025–26 cutoff. "
            "The skater comparison requires at least 50 NHL games; no radar or match is shown."
        )
    _, historical = _names(data)
    period = (
        f"through season-age {data['current_age']}"
        if window == "age_aligned"
        else "full observed NHL regular-season careers through 2025–26"
    )
    axes = sorted(
        data["axes"],
        key=lambda a: a["weight"] * (a["current_z"] - a["historical_z"]) ** 2,
        reverse=True,
    )
    values = []
    for axis in axes[:2]:
        a = article_radar.value_formatter(axis, "current", data)
        b = article_radar.value_formatter(axis, "historical", data)
        values.append(f"{UNITS[axis['key']]}: {a} versus {b}")
    return (
        f"Radar comparing {current} (solid burgundy, round markers) with {historical} "
        f"(dashed blue, square markers), {period}. Weighted statistical gap "
        f"{data['distance']:.2f}; smaller is closer within this candidate pool. "
        f"The two largest weighted differences are {'; '.join(values)}. "
        "Shaded area is a statistical profile, not a similarity percentage."
    )


def _forsberg_charts(report):
    charts = []
    for match in report["matches"][:3]:
        axes, distance = radar.axes_from_stats(
            report["target_features"],
            match,
            report["candidate_means"],
            report["scales"],
            report["weights"],
            article_radar.LABELS,
        )
        charts.append(
            {
                "player_id": report["target_id"],
                "current": report["target_name"],
                "historical": match["name"],
                "current_games": report["target_games"],
                "historical_games": match["nhl_games"],
                "axes": axes,
                "distance": distance,
                "gap_precision": 3,
                "bounds": radar.radial_bounds(axes),
                "stem": article_radar.image_stem(match["player_id"], match["name"]),
            }
        )
    # All three reverse-comparison panels use the same ruler.
    bounds = radar.radial_bounds([a for chart in charts for a in chart["axes"]])
    for chart in charts:
        chart["bounds"] = bounds
    return charts


def draw_forsberg_overview(charts, out):
    """Keep the requested title while showing the actual first two ranked comparisons."""
    _style()
    fig = plt.figure(figsize=(8, 7.1), facecolor=ICE)
    fig.text(0.035, 0.94, "Loosely, the Moose", fontsize=23, color=INK, weight="bold")
    fig.add_artist(
        plt.Line2D(
            [0.65, 0.70],
            [0.955, 0.955],
            transform=fig.transFigure,
            color=BURGUNDY,
            lw=2.5,
            marker="o",
            markevery=[1],
            markersize=4,
        )
    )
    fig.text(0.72, 0.946, "Peter Forsberg", fontsize=15, color=BURGUNDY, weight="bold")
    for i, data in enumerate(charts[:2]):
        center = 0.25 + 0.5 * i
        fig.text(
            center,
            0.825,
            f"{i + 1}. {display_name(data['historical'])}",
            ha="center",
            fontsize=18,
            color=BLUE,
            weight="bold",
        )
        fig.text(center, 0.765, f"Gap {data['distance']:.3f}", ha="center", fontsize=16, color=INK)
        _context(fig, center, 0.715, data, 11.5)
        ax = fig.add_axes([0.015 + 0.5 * i, 0.015, 0.47, 0.62])
        lineup_radar.draw_radar(ax, data, font_size=19.5)
        ax.set_xlim(-2.15, 2.15)
        ax.set_ylim(-1.9, 1.9)
    fig.add_artist(
        plt.Line2D([0.5, 0.5], [0.04, 0.86], transform=fig.transFigure, color="#D5E1E8", lw=0.8)
    )
    _save(fig, out, "loosely-the-moose")


def draw_cale(report, out):
    """Make the five-player career overlay readable with a single-column named legend."""
    _style()
    profiles, keys = report["profiles"], report["feature_order"]
    low, high = report["radial_bounds"]
    angles = np.pi / 2 - np.arange(len(keys)) * 2 * np.pi / len(keys)
    unit = np.column_stack((np.cos(angles), np.sin(angles)))
    closed_unit = np.vstack((unit, unit[0]))
    radius = lambda z: (z - low) / (high - low)
    fig = plt.figure(figsize=(7.2, 9), facecolor=ICE)
    fig.text(0.055, 0.94, "All Hail Cale", fontsize=26, color=INK, weight="bold")
    ax = fig.add_axes([0.04, 0.315, 0.92, 0.535])
    ax.set_aspect("equal")
    ax.axis("off")
    step = max(1, ceil((high - low) / 7))
    for tick in sorted({0, high, *range(int(low) + step, int(high), step)}):
        points = closed_unit * radius(tick)
        ax.plot(
            points[:, 0],
            points[:, 1],
            color="#9DB0BC" if tick == 0 else "#CFDCE4",
            lw=1.2 if tick == 0 else 0.7,
            zorder=1,
        )
    for vector in unit:
        ax.plot([0, vector[0]], [0, vector[1]], color="#CFDCE4", lw=0.7, zorder=1)
    target = next(p for p in profiles if p["player_id"] == MAKAR)
    for player in [p for p in profiles if p["player_id"] != MAKAR] + [target]:
        current = player["player_id"] == MAKAR
        color = makar_compact_graphics.PLAYER_COLORS[player["player_id"]]
        points = np.array([radius(player["z_scores"][key]) for key in keys])[:, None] * unit
        closed = np.vstack((points, points[0]))
        if current:
            ax.fill(closed[:, 0], closed[:, 1], color=BURGUNDY, alpha=0.08, zorder=3)
        ax.plot(
            closed[:, 0],
            closed[:, 1],
            color=color,
            lw=3.2 if current else 1.6,
            ls="-" if current else makar_compact_graphics.LINE_STYLES[player["player_id"]],
            zorder=5 if current else 2,
        )
        ax.scatter(
            points[:, 0],
            points[:, 1],
            color=color,
            s=40 if current else 13,
            zorder=6 if current else 3,
        )
    from matplotlib.offsetbox import AnnotationBbox, TextArea, VPacker

    for key, vector in zip(keys, unit, strict=True):
        value = (
            f"{target['games']:,.0f}" if key == "log_games" else f"{target['features'][key]:.1f}"
        )
        block = VPacker(
            children=[
                TextArea(
                    lineup_radar.LABELS[key],
                    textprops={"fontsize": 18, "weight": "bold", "color": INK},
                ),
                TextArea(value, textprops={"fontsize": 19, "weight": "bold", "color": BURGUNDY}),
            ],
            align="center",
            pad=0,
            sep=2,
        )
        ax.add_artist(
            AnnotationBbox(
                block,
                tuple(vector * 1.12),
                box_alignment=(
                    0 if vector[0] > 0.25 else 1 if vector[0] < -0.25 else 0.5,
                    0 if vector[1] > 0.6 else 1 if vector[1] < -0.6 else 0.5,
                ),
                frameon=False,
                annotation_clip=False,
                pad=0,
            )
        )
    ax.set_xlim(-1.7, 1.7)
    ax.set_ylim(-1.5, 1.5)
    if "log_games" not in keys:
        fig.text(0.16, 0.295, "Observed NHL games · unweighted", fontsize=12.5, color=MUTED)
    for i, player in enumerate(profiles):
        y = 0.258 - i * 0.045
        current = player["player_id"] == MAKAR
        color = makar_compact_graphics.PLAYER_COLORS[player["player_id"]]
        fig.add_artist(
            plt.Line2D(
                [0.065, 0.13],
                [y + 0.008, y + 0.008],
                transform=fig.transFigure,
                color=color,
                lw=3 if current else 1.6,
                ls="-" if current else makar_compact_graphics.LINE_STYLES[player["player_id"]],
            )
        )
        fig.text(
            0.16,
            y,
            f"{display_name(player['name'])} · {player['games']:,.0f} GP",
            fontsize=17,
            color=color,
            weight="bold" if current else "normal",
        )
    _save(fig, out, "all-hail-cale")


def _cale_pairs(report):
    target = next(p for p in report["profiles"] if p["player_id"] == MAKAR)
    pairs = []
    for player in report["profiles"]:
        if player["player_id"] == MAKAR:
            continue
        gap = sqrt(
            sum(
                report["weights"][k] * (target["z_scores"][k] - player["z_scores"][k]) ** 2
                for k in report["feature_order"]
            )
        )
        axes, _ = radar.axes_from_stats(
            target["features"],
            {"features": player["features"], "distance": gap},
            report["candidate_means"],
            report["scales"],
            report["weights"],
            article_radar.LABELS,
        )
        pairs.append(
            {
                "current": target["name"],
                "historical": player["name"],
                "current_games": target["games"],
                "historical_games": player["games"],
                "axes": axes,
                "distance": gap,
                "bounds": report["radial_bounds"],
                "stem": article_radar.image_stem(player["player_id"], player["name"]),
            }
        )
    return pairs


def draw_preview(data, out):
    """Save a 1200 by 675 native plot preview, without adding a new analysis."""
    _style()
    fig = plt.figure(figsize=(12, 6.75), facecolor=ICE)
    fig.text(
        0.05,
        0.84,
        "How Today’s Avs\nStack Up Against\nColorado’s Past",
        fontsize=28,
        color=INK,
        weight="bold",
        linespacing=1.3,
        va="top",
    )
    fig.text(0.05, 0.26, "Era-adjusted career comparisons", fontsize=16, color=MUTED)
    a, b = _names(data)
    fig.text(0.05, 0.17, a, fontsize=17, color=BURGUNDY, weight="bold")
    fig.text(0.05, 0.11, f"vs. {b}", fontsize=16, color=BLUE, weight="bold")
    ax = fig.add_axes([0.54, 0.07, 0.43, 0.86])
    lineup_radar.draw_radar(ax, data, font_size=12)
    fig.savefig(out / "preview.png", dpi=100, facecolor=ICE)
    fig.savefig(out / "preview.svg", dpi=100, facecolor=ICE)
    plt.close(fig)


def _gallery(path, title, sections, *, root_prefix=".."):
    blocks = []
    for heading, cards in sections:
        block = f"<section><h2>{escape(heading)}</h2><div class=grid>"
        for stem, alt in cards:
            block += (
                f'<figure><a href="{stem}.png"><img src="{stem}.png" alt="{escape(alt, quote=True)}" '
                f'loading="lazy"></a><p><a href="{stem}.png">PNG</a> · '
                f'<a href="{stem}.svg">SVG</a></p></figure>'
            )
        blocks.append(block + "</div></section>")
    path.write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(title)}</title><style>body{{margin:30px auto;padding:0 16px;max-width:1050px;"
        "font:16px/1.55 system-ui;background:#eff5f8;color:#182d3c}a{color:#236192}"
        ".grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}"
        "figure{margin:0}img{display:block;width:100%}figure p{margin:4px 0 20px}"
        "@media(max-width:680px){.grid{grid-template-columns:1fr}}"
        f"</style><h1>{escape(title)}</h1><nav>"
        f'<a href="{root_prefix}/index.html">Article figures</a> · '
        f'<a href="{root_prefix}/age-adjusted/index.html">Same-age supplement</a> · '
        f'<a href="{root_prefix}/alt-text.csv">Image descriptions</a></nav>'
        "<p>Each burgundy profile belongs to the named target; each blue profile to the comparison. "
        "Gap is the weighted statistical distance, not a percentage. Raw gaps are specific to "
        "the model and its candidate pool.</p>" + "".join(blocks) + "</html>",
        encoding="utf-8",
    )


def render(reports, out):
    """Create the main article package and an explicitly separate same-age supplement."""
    out = Path(out)
    if (out / "alt-text.csv").exists():
        raise ValueError("Choose a fresh graphics directory to preserve previous article packages.")
    out.mkdir(parents=True, exist_ok=True)
    charts = article_radar.chart_data(reports["roster"])
    selected_ids = [pid for _, ids in lineup_radar.ROWS for pid in ids]
    alt_rows = []
    overview_records = []
    for window, (directory, _) in article_radar.WINDOWS.items():
        destination = out / directory
        individual = destination / "individual"
        overview = destination / "overview"
        individual.mkdir(parents=True, exist_ok=True)
        overview.mkdir(exist_ok=True)
        available = {p["player_id"]: p for p in charts if p["window"] == window}
        unranked = {
            p["player_id"]: p for p in reports["roster"]["unranked"] if p["window"] == window
        }
        grouped = {label: [] for label in SECTIONS.values()}
        for pid in selected_ids:
            if pid in available:
                data = available[pid]
            elif pid in unranked:
                data = {
                    "player_id": pid,
                    "current": unranked[pid]["name"],
                    "unranked": True,
                    "position": "F",
                    "stem": article_radar.image_stem(pid, unranked[pid]["name"]),
                }
            else:
                raise ValueError(f"Requested article player is absent from the ranking: {pid}.")
            section = SECTIONS[data.get("position", "F")]
            draw_individual(data, window, individual, data["stem"])
            alt = pair_alt(data, window)
            grouped[section].append((data, alt))
            alt_rows.append(
                {
                    "file": f"{directory}/individual/{data['stem']}.png",
                    "section": section,
                    "window": window,
                    "target": display_name(data["current"]),
                    "comparison": "" if data.get("unranked") else display_name(data["historical"]),
                    "weighted_gap": "" if data.get("unranked") else data["distance"],
                    "alt_text": alt,
                }
            )
        sections = []
        if window == "whole_career":
            opener = available[MACKINNON]
            draw_individual(opener, window, destination, "opener-mackinnon")
            sections.append(("Start here", [("opener-mackinnon", pair_alt(opener, window))]))
            alt_rows.append(
                {
                    "file": f"{directory}/opener-mackinnon.png",
                    "section": "Opener",
                    "window": window,
                    "target": display_name(opener["current"]),
                    "comparison": display_name(opener["historical"]),
                    "weighted_gap": opener["distance"],
                    "alt_text": pair_alt(opener, window),
                }
            )
            draw_preview(opener, out)
            alt_rows.append(
                {
                    "file": "preview.png",
                    "section": "Preview",
                    "window": window,
                    "target": opener["current"],
                    "comparison": opener["historical"],
                    "weighted_gap": opener["distance"],
                    "alt_text": pair_alt(opener, window),
                }
            )
        for section, members in grouped.items():
            sections.append(
                (
                    section,
                    [
                        (f"individual/{p['stem']}", alt)
                        for p, alt in members
                        if window != "whole_career" or p["player_id"] != MACKINNON
                    ],
                )
            )
            overview_members = [
                (data, alt)
                for data, alt in members
                if window != "whole_career" or data["player_id"] != MACKINNON
            ]
            for i in range(0, len(overview_members), 2):
                batch = overview_members[i : i + 2]
                stem = f"{section.lower()}-{i // 2 + 1:02d}"
                draw_overview([p for p, _ in batch], window, overview, stem)
                overview_records.append(
                    {
                        "file": f"{directory}/overview/{stem}.png",
                        "section": section,
                        "window": window,
                        "target": " / ".join(p["current"] for p, _ in batch),
                        "comparison": "",
                        "weighted_gap": "",
                        "alt_text": " ".join(alt for _, alt in batch),
                    }
                )
        if window == "whole_career":
            draw_cale(reports["makar"], destination)
            cale_alt = (
                "Five full-career profiles on the same statistical ruler, with Cale Makar "
                "as the bold burgundy line. Ray Bourque, Tyson Barrie, Sandis Ozolinsh and "
                "John-Michael Liles are named in the legend. Spoke numbers show Makar's values; "
                "the polygons are profiles, not similarity percentages. Career games in the "
                "legend describe sample size and do not imply equal career stages."
            )
            sections.append(("All Hail Cale", [("all-hail-cale", cale_alt)]))
            alt_rows.append(
                {
                    "file": f"{directory}/all-hail-cale.png",
                    "section": "Cale",
                    "window": window,
                    "target": "Cale Makar",
                    "comparison": "Four former Avs defensemen",
                    "weighted_gap": "",
                    "alt_text": cale_alt,
                }
            )
            details = destination / "cale-detail"
            details.mkdir()
            detail_cards = []
            for pair in _cale_pairs(reports["makar"]):
                draw_individual(pair, window, details, pair["stem"])
                alt = pair_alt(pair, window)
                detail_cards.append((pair["stem"], alt))
                alt_rows.append(
                    {
                        "file": f"{directory}/cale-detail/{pair['stem']}.png",
                        "section": "Cale detail",
                        "window": window,
                        "target": pair["current"],
                        "comparison": pair["historical"],
                        "weighted_gap": pair["distance"],
                        "alt_text": alt,
                    }
                )
            _gallery(
                details / "index.html",
                "Cale: individual comparisons",
                [("Career profiles", detail_cards)],
                root_prefix="../..",
            )
            forsberg = []
            forsberg_charts = _forsberg_charts(reports["forsberg"])
            draw_forsberg_overview(forsberg_charts, destination)
            alt_rows.append(
                {
                    "file": f"{directory}/loosely-the-moose.png",
                    "section": "Forsberg overview",
                    "window": window,
                    "target": "Peter Forsberg",
                    "comparison": " / ".join(
                        display_name(p["historical"]) for p in forsberg_charts[:2]
                    ),
                    "weighted_gap": "",
                    "alt_text": " ".join(pair_alt(p, window) for p in forsberg_charts[:2]),
                }
            )
            for rank, pair in enumerate(forsberg_charts, 1):
                stem = f"forsberg-{rank:02d}-{pair['stem']}"
                draw_individual(pair, window, destination, stem)
                alt = pair_alt(pair, window)
                forsberg.append((stem, alt))
                alt_rows.append(
                    {
                        "file": f"{directory}/{stem}.png",
                        "section": "Forsberg",
                        "window": window,
                        "target": pair["current"],
                        "comparison": pair["historical"],
                        "weighted_gap": pair["distance"],
                        "alt_text": alt,
                    }
                )
            title = reports["forsberg"].get("figure_title") or "Loosely, the Moose"
            sections.append((title, forsberg))
        _gallery(
            destination / "index.html",
            "Same-age supplement"
            if window == "age_aligned"
            else "Article figures: full observed careers",
            sections,
        )
    alt_rows.extend(overview_records)
    for window, (directory, _) in article_radar.WINDOWS.items():
        overview_sections = []
        for section in SECTIONS.values():
            cards = [
                (Path(record["file"]).stem, record["alt_text"])
                for record in overview_records
                if record["window"] == window and record["section"] == section
            ]
            overview_sections.append((section, cards))
        _gallery(
            out / directory / "overview" / "index.html",
            "Compact same-age sheets" if window == "age_aligned" else "Compact career sheets",
            overview_sections,
            root_prefix="../..",
        )
    with (out / "alt-text.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "file",
                "section",
                "window",
                "target",
                "comparison",
                "weighted_gap",
                "alt_text",
            ],
        )
        writer.writeheader()
        writer.writerows(alt_rows)
    (out / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Avalanche article graphics</title><style>body{max-width:760px;margin:35px auto;"
        "padding:0 16px;font:18px/1.6 system-ui;color:#182d3c}a{color:#236192}</style>"
        "<h1>Avalanche article graphics</h1><ul>"
        '<li><a href="full-career/index.html">Main article: full observed careers</a></li>'
        '<li><a href="age-adjusted/index.html">Separate same-age supplement</a></li>'
        '<li><a href="full-career/overview/index.html">Compact two-panel career sheets</a></li>'
        '<li><a href="age-adjusted/overview/index.html">Compact two-panel same-age sheets</a></li>'
        '<li><a href="full-career/loosely-the-moose.png">Forsberg first-two overview</a></li>'
        '<li><a href="preview.png">1200 × 675 preview image</a></li>'
        '<li><a href="alt-text.csv">Alt text to paste into Substack</a></li>'
        '<li><a href="full-career/cale-detail/index.html">Individual Cale comparisons</a></li>'
        "</ul><p>Single-panel images are the mobile default. Each section also contains an "
        "<code>overview/</code> directory of compact two-panel alternatives.</p></html>",
        encoding="utf-8",
    )
    return alt_rows
