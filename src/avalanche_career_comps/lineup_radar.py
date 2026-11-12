"""Arrange the user's selected players into compact article-row radar images."""

from __future__ import annotations

import os
import zipfile
from html import escape
from pathlib import Path

from . import article_radar, inputs, radar
from .publication import BLUE, BURGUNDY, ICE, INK, MUTED, _save, _style, np, plt

# Presentation groups supplied by the user, not independently inferred playing lines.
ROWS = (
    ("01-lehkonen-mackinnon-necas", (8477476, 8477492, 8480039)),
    ("02-landeskog-nelson-roy", (8476455, 8475754, 8478462)),
    ("03-schwartz-kadri-hughes", (8475768, 8475172, 8486171)),
    ("04-kelly-svechkov-oconnor", (8480448, 8482768, 8481186)),
    ("05-toews-makar", (8478038, 8480069)),
    ("06-kulak-manson", (8476967, 8476312)),
    ("07-malinski-burns", (8484258, 8470613)),
    ("08-blackwood-wedgewood", (8478406, 8475809)),
)
HUGHES = 8486171
LABELS = {
    "goals_per_82": "G/82",
    "assists_per_82": "A/82",
    "shots_per_82": "S/82",
    "pim_per_82": "PIM/82",
    "log_games": "GP",
    "adjusted_pp_points_per_82": "PP/82",
    "pk_minutes_per_game": "PK",
    "relative_save_percentage": "SV+",
    "adjusted_shots_per_game": "SA/G",
    "schedule_adjusted_games_per_season": "Apps/82",
    "quality_starts_above_league_per_100_starts": "QS+",
    "era_relative_shutouts_per_100_starts": "SO+",
}
NOTE = """Burgundy identifies the current Av and blue identifies the matched alumnus. At each spoke, the burgundy number is above the blue number. Closer markers mean more similar values; the shaded shapes are profiles, not a similarity score. The darker ring marks the alumni average. Each chart uses its own comparison pool and scale.

G/82, A/82, S/82 and PP/82 are era-adjusted goals, assists, shots and power-play points per 82 games. PIM/82 is unadjusted penalty minutes per 82 games; GP is career NHL games; PK is minutes:seconds per game where complete coverage permits it. Goalies show SV+ (save percentage above league, in percentage points), SA/G (era-adjusted shots faced per game), Apps/82 (appearances per 82-game season) and career GP.

The main images compare full observed NHL careers through 2025–26. The separate age-adjusted set limits alumni to the current player's season-age. The rows are the article's presentation groups.
"""
LEGACY_GOALIE_NOTE = (
    "Goalies show SV+ (save percentage above league, in percentage points), SA/G "
    "(era-adjusted shots faced per game), Apps/82 (appearances per 82-game season) and career GP."
)


def article_note(report):
    """Use the selected goalie definitions without altering archived notes."""
    note = NOTE
    if report.get("goalie_method"):
        note = note.replace(LEGACY_GOALIE_NOTE, article_radar.PERFORMANCE_GOALIE_NOTE)
    return note + "\n" + article_radar.eligibility_note(report)


def select_rows(charts, unranked, window):
    """Enforce the requested order and never manufacture a profile for Hughes."""
    available = {c["player_id"]: c for c in charts if c["window"] == window}
    missing = {r["player_id"]: r for r in unranked if r["window"] == window}
    selected = []
    for stem, ids in ROWS:
        members = []
        for pid in ids:
            if pid == HUGHES:
                if pid in available or pid not in missing:
                    raise ValueError(
                        "Hughes cannot be labelled insufficient without an unranked source record."
                    )
                members.append(
                    {"player_id": pid, "current": missing[pid]["name"], "unranked": True}
                )
            elif pid not in available:
                raise ValueError(f"Requested lineup player has no saved chart: {pid}.")
            else:
                members.append(available[pid])
        selected.append({"stem": stem, "members": members})
    return selected


def draw_radar(ax, data, *, font_size=15):
    """Keep the saved statistical coordinates; stack values to save panel width."""
    from matplotlib.offsetbox import AnnotationBbox, TextArea, VPacker

    ax.set_aspect("equal")
    ax.axis("off")
    axes = data["axes"]
    angles = np.pi / 2 - np.arange(len(axes)) * 2 * np.pi / len(axes)
    unit = np.column_stack((np.cos(angles), np.sin(angles)))
    low, high = data["bounds"]
    radius = lambda z: (z - low) / (high - low)
    step = max(1, int(np.ceil((high - low) / 7)))
    rings = sorted({0, high, *range(low + step, high, step)})
    closed_unit = np.vstack((unit, unit[0]))
    for tick in rings:
        points = closed_unit * radius(tick)
        ax.plot(
            points[:, 0],
            points[:, 1],
            color="#9DB0BC" if tick == 0 else "#CFDCE4",
            lw=1.1 if tick == 0 else 0.7,
            zorder=1,
        )
    for vector in unit:
        ax.plot([0, vector[0]], [0, vector[1]], color="#CFDCE4", lw=0.7, zorder=1)
    for field, color, line, marker in (
        ("current", BURGUNDY, "-", "o"),
        ("historical", BLUE, "--", "s"),
    ):
        points = np.array([radius(a[field + "_z"]) for a in axes])[:, None] * unit
        closed = np.vstack((points, points[0]))
        ax.fill(closed[:, 0], closed[:, 1], color=color, alpha=0.08, zorder=2)
        ax.plot(closed[:, 0], closed[:, 1], color=color, lw=2.5, ls=line, zorder=3)
        ax.scatter(points[:, 0], points[:, 1], color=color, s=28, marker=marker, zorder=4)
    for axis, vector in zip(axes, unit, strict=True):
        children = [
            TextArea(
                LABELS[axis["key"]],
                textprops={"fontsize": font_size - 0.5, "weight": "bold", "color": INK},
            )
        ]
        for field, color in (("current", BURGUNDY), ("historical", BLUE)):
            children.append(
                TextArea(
                    article_radar.value_formatter(axis, field, data),
                    textprops={"fontsize": font_size, "weight": "bold", "color": color},
                )
            )
        block = VPacker(children=children, align="center", pad=0, sep=1)
        x, y = vector * 1.12
        horizontal = 0 if vector[0] > 0.25 else 1 if vector[0] < -0.25 else 0.5
        vertical = 0 if vector[1] > 0.6 else 1 if vector[1] < -0.6 else 0.5
        ax.add_artist(
            AnnotationBbox(
                block,
                (x, y),
                box_alignment=(horizontal, vertical),
                frameon=False,
                annotation_clip=False,
                pad=0,
            )
        )
    ax.set_xlim(-1.75, 1.75)
    ax.set_ylim(-1.75, 1.75)


def draw_row(row, window, out):
    """Export one landscape image per requested row, with no explanatory footer."""
    _style()
    members = row["members"]
    count = len(members)
    fig = plt.figure(figsize=(12, 5.4), facecolor=ICE)
    width = 0.96 / count
    for index, data in enumerate(members):
        left = 0.02 + index * width
        center = left + width / 2
        fig.text(
            center,
            0.86,
            data["current"],
            fontsize=21 if count == 3 else 23,
            weight="bold",
            color=BURGUNDY,
            ha="center",
        )
        if data.get("unranked"):
            fig.text(
                center,
                0.47,
                "Not enough data",
                fontsize=20,
                weight="bold",
                color=MUTED,
                ha="center",
            )
            continue
        fig.text(
            center,
            0.79,
            f"vs. {data['historical']}",
            fontsize=17 if count == 3 else 19,
            weight="bold",
            color=BLUE,
            ha="center",
        )
        if window == "age_aligned":
            fig.text(
                center,
                0.737,
                f"Through age {data['current_age']}",
                fontsize=12,
                color=MUTED,
                ha="center",
            )
        if data.get("goalie_performance"):
            article_radar.draw_goalie_appearances(
                fig,
                center,
                0.707 if window == "age_aligned" else 0.737,
                data,
                fontsize=10.5,
                centered=True,
            )
        ax = fig.add_axes(
            [left + 0.004, 0.06, width - 0.008, 0.645 if window == "whole_career" else 0.605]
        )
        draw_radar(ax, data, font_size=15 if count == 3 else 16)
        if index:
            fig.add_artist(
                plt.Line2D(
                    [left, left], [0.04, 0.88], color="#D5E1E8", lw=0.8, transform=fig.transFigure
                )
            )
    _save(fig, out, row["stem"])


def gallery(rows, window, out, source_gallery):
    """Preview the article rows in order with downloads and separate detail links."""
    title = article_radar.WINDOWS[window][1]
    cards = []
    for row in rows:
        names = " / ".join(m["current"] for m in row["members"])
        details = []
        for member in row["members"]:
            if member.get("unranked"):
                continue
            individual = source_gallery / article_radar.WINDOWS[window][0] / f"{member['stem']}.png"
            link = escape(os.path.relpath(individual, out))
            details.append(
                f'<p><a href="{link}">{escape(member["current"])} — individual chart</a><br>{escape(article_radar.coverage_text(member))}</p>'
            )
        stem = row["stem"]
        cards.append(
            f'<article><a href="{stem}.png"><img src="{stem}.png" alt="{escape(names)}"></a><p><a href="{stem}.png">PNG</a> · <a href="{stem}.svg">SVG</a></p><details><summary>Individual charts and comparison details</summary>{"".join(details)}</details></article>'
        )
    (out / "index.html").write_text(
        f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} article rows</title>
<style>body{{margin:0;background:#eff5f8;color:#182d3c;font:16px/1.5 system-ui}}main{{max-width:760px;margin:auto;padding:25px 12px}}h1{{margin:0}}nav{{display:flex;gap:15px;flex-wrap:wrap;margin:18px 0}}article{{margin:24px 0;background:white;border:1px solid #c8d9e4;border-radius:8px;overflow:hidden}}img{{width:100%;display:block}}a{{color:#236192}}p,details{{margin:12px 16px}}header p{{margin-left:0}}</style><main><header><h1>{title}: article rows</h1><nav><a href="../full-career/index.html">Full career</a><a href="../age-adjusted/index.html">Age adjusted</a><a href="../{article_radar.WINDOWS[window][0]}-pngs.zip">Download all eight PNGs</a><a href="../article-note.txt">One-time article note</a></nav><p>The requested player groups, in order. Open a PNG for full resolution.</p></header>{"".join(cards)}</main></html>""",
        encoding="utf-8",
    )


def publish(report, results, source_gallery, out):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Choose an empty lineup output directory.")
    charts = article_radar.chart_data(report)
    layouts = {}
    for window, (directory, _) in article_radar.WINDOWS.items():
        destination = out / directory
        destination.mkdir(parents=True, exist_ok=True)
        rows = select_rows(charts, report["unranked"], window)
        for row in rows:
            draw_row(row, window, destination)
        gallery(rows, window, destination, Path(source_gallery))
        layouts[window] = rows
    (out / "article-note.txt").write_text(article_note(report), encoding="utf-8")
    for directory, _ in article_radar.WINDOWS.values():
        with zipfile.ZipFile(
            out / f"{directory}-pngs.zip", "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for path in sorted((out / directory).glob("*.png")):
                archive.write(path, path.name)
            archive.write(out / "article-note.txt", "article-note.txt")
    (out / "index.html").write_text(
        """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Avalanche article rows</title><style>body{max-width:760px;margin:35px auto;padding:0 18px;background:#eff5f8;color:#182d3c;font:18px/1.6 system-ui}a{color:#236192}</style><h1>Avalanche article rows</h1><p><a href="full-career/index.html">Full career — main set</a><br><a href="age-adjusted/index.html">Age adjusted — separate set</a></p><p><a href="full-career-pngs.zip">Download full-career PNGs</a><br><a href="age-adjusted-pngs.zip">Download age-adjusted PNGs</a><br><a href="article-note.txt">One-time article explanation</a></p></html>""",
        encoding="utf-8",
    )
    inputs.write_json(
        out / "chart-data.json",
        {
            "layouts": layouts,
            "rankings_changed_by_renderer": False,
            "analysis_changes_from_previous_model": report.get("summary"),
        },
    )
    inputs.write_json(
        out / "manifest.json",
        {
            "results_sha256": inputs.digest(results),
            "code_sha256": {
                Path(p).name: inputs.digest(p)
                for p in (__file__, article_radar.__file__, radar.__file__)
            },
            "outputs_sha256": {
                str(p.relative_to(out)): inputs.digest(p)
                for p in sorted(out.rglob("*"))
                if p.is_file()
            },
        },
    )
    return layouts
