"""Shared chart styling for the cellbased-comparison-2017 studies.

Matches the palette and typography that cbc-04/compare.py established, so every
study's figures read as one set. Import from a study's make_charts.py:

    from _chartkit import style, save, INK, MUTED, GRID, TEAL, CORAL, verdict_color
"""
import json
import os

# palette — muted teal (tutorial / expected) vs warm coral (our reproduction)
INK = "#1f2a37"
MUTED = "#6b7787"
GRID = "#e6ebf1"
TEAL = "#2f6f8f"
CORAL = "#d1615d"
GREEN = "#1a7f42"
AMBER = "#f3c969"
SLATE = "#8a94a6"

# verdict → colour, for scorecards that render reproducibility_metrics verdicts
_VERDICT = {
    "match": GREEN,
    "close": "#7bb662",
    "supported": GREEN,
    "partial": AMBER,
    "blocked": CORAL,
    "refuted": CORAL,
    "unavailable": CORAL,
}


def verdict_color(verdict):
    return _VERDICT.get((verdict or "").strip().lower(), SLATE)


def style():
    import matplotlib as mpl
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 11, "axes.edgecolor": GRID, "axes.linewidth": 1.0,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.9,
        "axes.axisbelow": True, "text.color": INK, "axes.labelcolor": MUTED,
        "xtick.color": MUTED, "ytick.color": MUTED,
        "axes.spines.top": False, "axes.spines.right": False,
        "figure.facecolor": "white", "axes.facecolor": "white",
    })


def save(fig, charts_dir, stem, meta):
    """Write <charts_dir>/<stem>.png at 150 dpi + a <stem>.meta.json caption."""
    import matplotlib.pyplot as plt
    os.makedirs(charts_dir, exist_ok=True)
    out = os.path.join(charts_dir, f"{stem}.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    with open(os.path.join(charts_dir, f"{stem}.meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    return out
