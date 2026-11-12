"""Editorial figures and an offline, inspectable article from computed career analogues."""

from __future__ import annotations

import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/avalanche-career-comps-matplotlib")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np  # noqa: F401 -- shared plotting namespace for the article renderers

BURGUNDY = "#6F263D"
BLUE = "#236192"
INK = "#182D3C"
MUTED = "#587080"
ICE = "#EFF5F8"
GOLD = "#D6963B"
WHITE = "#FFFFFF"


def _style():
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 12,
            "text.color": INK,
            "axes.labelcolor": MUTED,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "axes.edgecolor": "#CBD8E0",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": False,
            "axes.titleweight": "bold",
            "figure.facecolor": ICE,
            "axes.facecolor": ICE,
            "svg.fonttype": "none",
        }
    )


def _save(fig, out, name):
    for suffix in ("png", "svg"):
        fig.savefig(out / f"{name}.{suffix}", dpi=190, facecolor=fig.get_facecolor())
    plt.close(fig)
