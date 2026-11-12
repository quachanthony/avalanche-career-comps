"""Show five complete career profiles in two compact, consistently scaled figures."""

from __future__ import annotations

from math import ceil, isfinite
from textwrap import fill

from .publication import BLUE, BURGUNDY, GOLD, ICE, INK, MUTED, _save, _style, np, plt

PLAYER_COLORS = {
    8480069: BURGUNDY,
    8475197: BLUE,
    8445621: "#277869",
    8458544: GOLD,
    8468639: "#75539A",
}

MAKAR = 8480069
LINE_STYLES = {
    8445621: (0, (6, 3)),
    8475197: (0, (3, 2)),
    8458544: (0, (1, 2)),
    8468639: "-.",
}


def validate_radar(report):
    """Reject missing profiles or clipped coordinates instead of changing the ruler."""
    profiles = report["profiles"]
    keys = report["feature_order"]
    if len(profiles) != 5 or len({p["player_id"] for p in profiles}) != 5:
        raise ValueError("The compact career figure requires five distinct players.")
    if sum(p["player_id"] == MAKAR for p in profiles) != 1 or len(keys) != 6:
        raise ValueError("The compact radar requires Makar and the six common career stats.")
    low, high = report["radial_bounds"]
    if not low < 0 < high:
        raise ValueError("The shared radial bounds must include the alumni-average ring.")
    for player in profiles:
        for key in keys:
            raw, z = player["features"][key], player["z_scores"][key]
            if not isfinite(raw) or not isfinite(z) or not low <= z <= high:
                raise ValueError("The five-player radar has missing or clipped feature data.")


def draw_radar(report, out):
    """Highlight Makar while using one shared six-spoke scale for all five players."""
    from matplotlib.offsetbox import AnnotationBbox, TextArea, VPacker

    validate_radar(report)
    _style()
    profiles = report["profiles"]
    keys = report["feature_order"]
    target = next(p for p in profiles if p["player_id"] == MAKAR)
    low, high = report["radial_bounds"]
    angles = np.pi / 2 - np.arange(len(keys)) * 2 * np.pi / len(keys)
    unit = np.column_stack((np.cos(angles), np.sin(angles)))
    closed_unit = np.vstack((unit, unit[0]))
    radius = lambda z: (z - low) / (high - low)

    fig = plt.figure(figsize=(12, 6.2), facecolor=ICE)
    fig.text(0.045, 0.935, "All Hail Cale", fontsize=26, weight="bold", color=INK)
    ax = fig.add_axes([0.005, 0.035, 0.63, 0.785])
    ax.set_aspect("equal")
    ax.axis("off")
    step = max(1, ceil((high - low) / 7))
    rings = sorted({0, high, *range(int(low) + step, int(high), step)})
    for tick in rings:
        vertices = closed_unit * radius(tick)
        ax.plot(
            vertices[:, 0],
            vertices[:, 1],
            color="#91A8B6" if tick == 0 else "#D3E0E8",
            lw=1.25 if tick == 0 else 0.7,
            zorder=1,
        )
    for vector in unit:
        ax.plot([0, vector[0]], [0, vector[1]], color="#D3E0E8", lw=0.7, zorder=1)

    ordered = [p for p in profiles if p["player_id"] != MAKAR] + [target]
    for player in ordered:
        current = player["player_id"] == MAKAR
        color = PLAYER_COLORS[player["player_id"]]
        vertices = np.array([radius(player["z_scores"][key]) for key in keys])[:, None] * unit
        closed = np.vstack((vertices, vertices[0]))
        if current:
            ax.fill(closed[:, 0], closed[:, 1], color=BURGUNDY, alpha=0.09, zorder=3)
        ax.plot(
            closed[:, 0],
            closed[:, 1],
            color=color,
            lw=3.5 if current else 1.5,
            ls="-" if current else LINE_STYLES[player["player_id"]],
            alpha=1 if current else 0.85,
            zorder=5 if current else 2,
        )
        ax.scatter(
            vertices[:, 0],
            vertices[:, 1],
            color=color,
            s=38 if current else 12,
            zorder=6 if current else 3,
        )

    for key, vector in zip(keys, unit, strict=True):
        value = (
            f"{target['games']:,.0f}" if key == "log_games" else f"{target['features'][key]:.1f}"
        )
        block = VPacker(
            children=[
                TextArea(
                    fill(report["feature_labels"][key], 19),
                    textprops={"fontsize": 11, "weight": "bold", "color": INK, "ha": "center"},
                ),
                TextArea(value, textprops={"fontsize": 13, "weight": "bold", "color": BURGUNDY}),
            ],
            align="center",
            pad=0,
            sep=3,
        )
        horizontal = 0 if vector[0] > 0.25 else 1 if vector[0] < -0.25 else 0.5
        vertical = 0 if vector[1] > 0.6 else 1 if vector[1] < -0.6 else 0.5
        ax.add_artist(
            AnnotationBbox(
                block,
                tuple(vector * 1.15),
                box_alignment=(horizontal, vertical),
                frameon=False,
                annotation_clip=False,
                pad=0,
            )
        )
    ax.set_xlim(-1.7, 1.7)
    ax.set_ylim(-1.4, 1.4)

    for index, player in enumerate(profiles):
        y = 0.76 - index * 0.112
        current = player["player_id"] == MAKAR
        color = PLAYER_COLORS[player["player_id"]]
        fig.add_artist(
            plt.Line2D(
                [0.665, 0.705],
                [y + 0.009, y + 0.009],
                transform=fig.transFigure,
                color=color,
                lw=3.5 if current else 1.5,
                ls="-" if current else LINE_STYLES[player["player_id"]],
            )
        )
        fig.text(
            0.721,
            y,
            player["name"],
            fontsize=16 if current else 14,
            color=color,
            weight="bold",
        )
        fig.text(0.721, y - 0.035, f"{player['games']:,.0f} NHL games", fontsize=10.5, color=MUTED)
    _save(fig, out, "five-player-radar")
