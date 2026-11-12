"""Export an honest spider chart from the exact career-comparison feature scales.

Run with python -m avalanche_career_comps.radar --help. The polygon is an
unweighted profile, not a new distance calculation or an overlap-area score.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from statistics import mean, pstdev

from avalanche_career_comps.analysis import ProfileError, build_profile, position_group
from avalanche_career_comps.inputs import digest, read_json, write_json
from avalanche_career_comps.publication import BLUE, BURGUNDY, ICE, INK, MUTED, _style

LABELS = {
    "goals_per_82": "GOAL SCORING\nAdjusted goals / 82",
    "assists_per_82": "PLAYMAKING\nAdjusted assists / 82",
    "shots_per_82": "SHOT VOLUME\nAdjusted shots / 82",
    "pim_per_82": "PENALTY MINUTES\nMinutes / 82",
    "log_games": "CAREER EXPERIENCE\nNHL games · log scale",
    "debut_age": "NHL ENTRY AGE\nSeason-age · later = outward",
    "scoring_trajectory": "RECENT SCORING LIFT\nAdjusted points / 82 above career pace",
}


def radar_data(bundle, report, player_id=8477492):
    """Reconstruct the original comparison pool and verify every plotted gap."""
    target = next(r for r in report["results"] if r["player_id"] == player_id)
    if target["status"] != "matched" or target["position"] == "G":
        raise ValueError("This first radar design requires a matched skater.")
    match = target["matches"][0]
    current_ids = {p["player_id"] for p in bundle["roster"]}
    config = report["config"]
    league = {r["season_id"]: r for r in bundle["league"]}
    pool = []
    for player in bundle["players"]:
        if player["player_id"] in current_ids:
            continue
        if position_group(player["position"]) != target["position"]:
            continue
        if player["avs_games"] < config["min_avs_skater_games"]:
            continue
        try:
            profile = build_profile(player, league, config["last_season"], max_age=target["age"])
        except ProfileError:
            continue
        if profile["last_age"] >= target["age"] - 1 and profile["nhl_games"] >= 50:
            pool.append(profile)
    if len(pool) != target["candidate_count"]:
        raise ValueError("Comparison pool differs from the preserved report.")
    axes, distance = feature_axes(
        target["target_features"], match, pool, target["scales"], target["feature_weights"], LABELS
    )
    return {
        "current": target["name"],
        "historical": match["name"],
        "current_age": target["age"],
        "historical_age": match["last_age"],
        "current_games": target["nhl_games"],
        "historical_games": match["nhl_games"],
        "candidate_count": len(pool),
        "distance": distance,
        "axes": axes,
        "interpretation": "Similarity comes from the weighted gaps between markers on each spoke.",
    }


def feature_axes(current, match, pool, scales, weights, labels):
    """Standardize both markers with the same candidate mean and saved spread."""
    means = {}
    for key in weights:
        values = [p["features"][key] for p in pool]
        scale = pstdev(values) or 1.0
        if not math.isclose(scale, scales[key], rel_tol=1e-10):
            raise ValueError(f"Preserved feature scale differs: {key}")
        means[key] = mean(values)
    return axes_from_stats(current, match, means, scales, weights, labels)


def axes_from_stats(current, match, means, scales, weights, labels):
    axes = []
    for key, weight in weights.items():
        center, scale = means[key], scales[key]
        a, b = current[key], match["features"][key]
        axes.append(
            {
                "key": key,
                "label": labels[key],
                "weight": weight,
                "pool_mean": center,
                "pool_sd": scale,
                "current_z": (a - center) / scale,
                "historical_z": (b - center) / scale,
                "current_raw": a,
                "historical_raw": b,
            }
        )
    distance = math.sqrt(sum(a["weight"] * (a["current_z"] - a["historical_z"]) ** 2 for a in axes))
    if not math.isclose(distance, match["distance"], rel_tol=1e-10):
        raise ValueError("Plotted coordinate gaps do not reconcile to the original distance.")
    return axes, distance


def _value(axis, field, data):
    value = axis[field + "_raw"]
    if axis["key"] == "hits_per_game":
        return f"{value:.2f}"
    if axis["key"] == "pk_minutes_per_game":
        minutes, seconds = divmod(round(60 * value), 60)
        return f"{minutes}:{seconds:02d}"
    if axis["key"] == "log_games":
        return f"{data[field + '_games']:,.0f}"
    if axis["key"] == "scoring_trajectory":
        return f"{value * 82:+.1f}"
    return f"{value:.0f}" if axis["key"] == "debut_age" else f"{value:.1f}"


def radial_bounds(axes):
    points = [a[k] for a in axes for k in ("current_z", "historical_z")]
    return min(-2, math.floor(min(points))), max(4, math.ceil(max(points)))


def draw_spokes(ax, data, *, bounds=None, label_size=12, label_sd=True, value_formatter=None):
    """Use polygonal rings and shared z-score limits; never clip a profile."""
    import numpy as np
    from matplotlib.offsetbox import AnnotationBbox, HPacker, TextArea

    formatter = value_formatter or _value
    ax.set_aspect("equal")
    ax.axis("off")
    n = len(data["axes"])
    angles = np.pi / 2 - np.arange(n) * 2 * np.pi / n
    unit = np.column_stack((np.cos(angles), np.sin(angles)))
    low, high = bounds or radial_bounds(data["axes"])
    step = 1 if label_sd else max(1, math.ceil((high - low) / 10))
    rings = sorted({0, high, *range(low + step, high, step)})
    radius = lambda z: (z - low) / (high - low)
    for tick in rings:
        polygon = np.vstack((unit, unit[0])) * radius(tick)
        color = "#9DB0BC" if tick == 0 else "#CFDCE4"
        ax.plot(polygon[:, 0], polygon[:, 1], color=color, lw=1.1 if tick == 0 else 0.7, zorder=1)
        if tick != 0 and not label_sd:
            continue
        # Ring labels fit between goal-scoring and recent-trend spokes.
        phi = np.deg2rad(116)
        label = "POOL AVERAGE" if tick == 0 else f"{tick:+d} SD"
        ax.text(
            radius(tick) * np.cos(phi),
            radius(tick) * np.sin(phi),
            label,
            fontsize=label_size - 2.5,
            color=MUTED,
            ha="center",
            va="center",
            zorder=4,
            bbox={"facecolor": ICE, "edgecolor": "none", "pad": 1.4},
        )
    for vector in unit:
        ax.plot([0, vector[0]], [0, vector[1]], color="#CFDCE4", lw=0.7, zorder=1)
    for field, color, line, marker in [
        ("current", BURGUNDY, "-", "o"),
        ("historical", BLUE, "--", "s"),
    ]:
        vertices = np.array([radius(a[field + "_z"]) for a in data["axes"]])[:, None] * unit
        closed = np.vstack((vertices, vertices[0]))
        ax.fill(closed[:, 0], closed[:, 1], color=color, alpha=0.08, zorder=2)
        ax.plot(closed[:, 0], closed[:, 1], color=color, lw=3, ls=line, zorder=3)
        ax.scatter(vertices[:, 0], vertices[:, 1], c=color, s=50, marker=marker, zorder=4)
    for axis, vector in zip(data["axes"], unit, strict=True):
        x, y = vector * 1.17
        align = "left" if x > 0.2 else "right" if x < -0.2 else "center"
        ax.text(
            x,
            y + 0.04,
            axis["label"],
            ha=align,
            va="center",
            fontsize=label_size,
            color=INK,
            linespacing=1.55,
            weight="bold",
        )
        values = HPacker(
            children=[
                TextArea(
                    value, textprops={"fontsize": label_size + 1, "weight": "bold", "color": color}
                )
                for value, color in (
                    (formatter(axis, "current", data), BURGUNDY),
                    ("/", MUTED),
                    (formatter(axis, "historical", data), BLUE),
                )
            ],
            align="baseline",
            pad=0,
            sep=4,
        )
        ax.add_artist(
            AnnotationBbox(
                values,
                (x, y - 0.085),
                box_alignment=({"left": 0, "center": 0.5, "right": 1}[align], 0.5),
                frameon=False,
                pad=0,
                annotation_clip=False,
            )
        )
    ax.set_xlim(-1.68, 1.68)
    ax.set_ylim(-1.40, 1.40)


def draw(data, out):
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    _style()
    fig = plt.figure(figsize=(15, 14), facecolor=ICE)
    fig.text(0.065, 0.955, "COLORADO / CAREER ECHOES", color=BURGUNDY, fontsize=13, weight="bold")
    fig.text(
        0.065,
        0.907,
        f"{data['current']} × {data['historical']}",
        fontsize=31,
        weight="bold",
        color=INK,
    )
    fig.text(
        0.065,
        0.874,
        f"Full NHL careers through season-age {data['current_age']} · "
        f"{data['current_games']:,.0f} vs. {data['historical_games']:,.0f} regular-season games",
        color=MUTED,
        fontsize=13,
    )
    if data["historical_age"] != data["current_age"]:
        fig.text(
            0.065,
            0.845,
            f"Historical profile ends at season-age {data['historical_age']}.",
            color=MUTED,
            fontsize=12,
        )
    legend = [
        Line2D([0], [0], color=BURGUNDY, lw=3.2, marker="o", label=data["current"]),
        Line2D([0], [0], color=BLUE, lw=3.2, ls="--", marker="s", label=data["historical"]),
    ]
    fig.legend(
        handles=legend,
        loc="upper left",
        bbox_to_anchor=(0.058, 0.855),
        ncol=2,
        frameon=False,
        fontsize=13,
        handlelength=3,
    )
    draw_spokes(fig.add_axes([0.04, 0.18, 0.92, 0.63]), data)
    fig.text(
        0.065,
        0.135,
        "Compare the two markers on each spoke.",
        fontsize=15,
        weight="bold",
        color=INK,
    )
    fig.text(
        0.065,
        0.109,
        "Closer markers mean the players were more alike on that stat.",
        fontsize=13,
        color=INK,
    )
    fig.text(
        0.065,
        0.084,
        "The match score combines those gaps, with some stats counting more. "
        "Shading helps you follow each player.",
        fontsize=12,
        color=MUTED,
    )
    fig.text(
        0.065,
        0.059,
        f"The darker ring shows the average for {data['candidate_count']} former Avs forwards. "
        "MacKinnon’s number comes first.",
        fontsize=11,
        color=MUTED,
    )
    fig.text(
        0.065,
        0.037,
        "NHL regular season · MacKinnon through 2025–26 · Sakic through 1999–2000",
        fontsize=10,
        color=MUTED,
    )
    out = Path(out)
    for suffix in ("png", "svg"):
        fig.savefig(out / f"04-mackinnon-sakic-web.{suffix}", dpi=200, facecolor=ICE)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        parser.error("Choose a new output directory to preserve prior graphics.")
    bundle, report = read_json(args.inputs), read_json(args.results)
    if digest(args.inputs) != report["input_sha256"]:
        raise ValueError("Input checksum differs from the preserved analysis.")
    data = radar_data(bundle, report)
    args.out.mkdir(parents=True, exist_ok=True)
    draw(data, args.out)
    write_json(args.out / "radar-data.json", data)
    write_json(
        args.out / "manifest.json",
        {
            "input_sha256": digest(args.inputs),
            "results_sha256": digest(args.results),
            "code_sha256": digest(__file__),
            "plot": data["interpretation"],
            "outputs_sha256": {
                p.name: digest(p) for p in sorted(args.out.iterdir()) if p.is_file()
            },
        },
    )
    print((args.out / "04-mackinnon-sakic-web.png").resolve())


if __name__ == "__main__":
    main()
