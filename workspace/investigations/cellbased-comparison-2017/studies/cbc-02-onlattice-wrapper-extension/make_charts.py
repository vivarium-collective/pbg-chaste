"""cbc-02: readouts for the on-lattice + differential-adhesion wrapper extension.

Two figures, both from recorded data (no engine re-run):

  00_reproduction_scorecard.png  the structural reproducibility_metrics — does the
                                 wrapper build the paper's populations/labelling/writer
                                 and cover the reachable models?
  01_os_boundary_degeneracy.png  why OS fractional length is float-noise on the
                                 pristine honeycomb lattice (tangent cells → zero-length
                                 shared edge), the finding that gates OS sampling in cbc-04.
"""
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from _chartkit import (style, save, INK, MUTED, GRID, TEAL, CORAL, GREEN,  # noqa: E402
                       verdict_color)

CHARTS = os.path.join(HERE, "charts")


def load_metrics():
    doc = yaml.safe_load(open(os.path.join(HERE, "study.yaml")))
    rm = doc["reproducibility_metrics"]["metrics"]
    label = {"real_cell_count": "Real cell count (20×20)",
             "labelled_cell_count": "Labelled cells (50%)",
             "metric_writer": "Boundary-length writer",
             "model_coverage": "Model coverage"}
    short = {"heterotypicboundary.dat (5 cols)": ".dat · 5 cols"}
    rows = []
    for m in rm:
        tv, rv = str(m["tutorial_value"]), str(m["reproduction_value"])
        rows.append((label.get(m["observable"], m["observable"]),
                     short.get(tv, tv), short.get(rv, rv),
                     m.get("verdict", ""), m.get("note", "")))
    return rows


def build_scorecard(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    style()
    fig, ax = plt.subplots(figsize=(9.6, 0.92 * len(rows) + 2.0))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, len(rows) + 0.85)
    ax.axis("off")
    xc = {"check": 0.15, "tut": 4.9, "rep": 6.75, "verdict": 8.6}
    hy = len(rows) + 0.28
    ax.text(xc["check"], hy, "CHECK", fontsize=8.5, color=MUTED, fontweight="bold")
    ax.text(xc["tut"], hy, "TUTORIAL", fontsize=8.5, color=TEAL, fontweight="bold")
    ax.text(xc["rep"], hy, "WRAPPER", fontsize=8.5, color=CORAL, fontweight="bold")
    ax.text(xc["verdict"] + 0.575, hy, "VERDICT", fontsize=8.5, color=MUTED,
            fontweight="bold", ha="center")
    for i, (check, tut, rep, verdict, note) in enumerate(rows):
        y = len(rows) - 1 - i + 0.5
        ax.text(xc["check"], y + 0.14, check, fontsize=11, color=INK, va="center", fontweight="medium")
        if note:
            ax.text(xc["check"], y - 0.24, note[:64] + ("…" if len(note) > 64 else ""),
                    fontsize=7.6, color=MUTED, va="center")
        ax.text(xc["tut"], y, tut, fontsize=9.5, color=INK, va="center")
        ax.text(xc["rep"], y, rep, fontsize=9.5, color=INK, va="center")
        col = verdict_color(verdict)
        pill = FancyBboxPatch((xc["verdict"], y - 0.22), 1.15, 0.44,
                              boxstyle="round,pad=0.02,rounding_size=0.22",
                              fc=col, ec="none", alpha=0.16, zorder=1)
        ax.add_patch(pill)
        ax.text(xc["verdict"] + 0.575, y, verdict.upper(), fontsize=8.5, color=col,
                ha="center", va="center", fontweight="bold", zorder=2)
        ax.axhline(len(rows) - 1 - i, color=GRID, lw=0.9, zorder=0)
    fig.suptitle("Structural reproducibility — paper setup vs the ChasteCellSortingProcess wrapper",
                 fontsize=13, fontweight="bold", color=INK, x=0.005, ha="left", y=1.0)
    fig.text(0.005, 0.02,
             "All four reachable models (CP · OS · VT · VM) build the paper's exact config and emit "
             "heterotypicboundary.dat; CA needs a custom Ca switching rule and is reported, not dropped.",
             fontsize=8.6, color=MUTED)
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    return save(fig, CHARTS, "00_reproduction_scorecard", {
        "title": "Structural reproducibility — wrapper vs paper setup",
        "caption": "Each check compares the tutorial's assertion against what the "
                   "ChasteCellSortingProcess wrapper produces on the real engine.",
        "interpretation": "Cell count, 50% labelling and the boundary-length writer match "
                          "exactly; coverage is 4/5 (CA blocked by a custom switching rule, "
                          "reported with evidence).",
    })


def build_os_degeneracy():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.patches import Circle
    style()
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(9.6, 4.0),
                                   gridspec_kw={"width_ratios": [1, 1.15]})

    # left: two tangent cells on the honeycomb lattice (r=0.5, spacing=1.0)
    axL.set_aspect("equal")
    axL.set_xlim(-0.85, 1.85); axL.set_ylim(-1.15, 1.15)
    axL.axis("off")
    for cx, col, name in [(0.0, TEAL, "cell A"), (1.0, CORAL, "cell B")]:
        axL.add_patch(Circle((cx, 0), 0.5, fc=col, ec="none", alpha=0.18, zorder=1))
        axL.add_patch(Circle((cx, 0), 0.5, fill=False, ec=col, lw=2, zorder=2))
        axL.text(cx, -0.72, name, ha="center", fontsize=9, color=col)
    axL.plot([0, 1], [0, 0], color=MUTED, lw=1, ls=(0, (3, 3)), zorder=3)
    axL.plot([0, 0.5], [0.78, 0.78], color=INK, lw=1.2)
    axL.plot([0, 0], [0.72, 0.84], color=INK, lw=1.2)
    axL.plot([0.5, 0.5], [0.72, 0.84], color=INK, lw=1.2)
    axL.text(0.25, 0.9, "r = 0.5", ha="center", fontsize=8.5, color=INK)
    axL.text(0.5, -0.05, "d = 1.0", ha="center", va="top", fontsize=8.5, color=MUTED)
    axL.text(0.5, -1.02, "overlap  2r − d = 0.000   " + r"$\rightarrow$" + "  tangent",
             ha="center", fontsize=9.5, color=INK, fontweight="bold")
    axL.set_title("Pristine honeycomb: neighbours are exactly tangent",
                  fontsize=10.5, color=INK, loc="left", pad=8)

    # right: the recorded os-heterotypicboundary.dat readback — ratio equality
    axR.axis("off")
    axR.set_xlim(0, 1); axR.set_ylim(0, 1)
    axR.text(0.0, 0.93, "os-heterotypicboundary.dat  (t = 0.2, before relaxation)",
             fontsize=10, color=INK, fontweight="medium")
    axR.text(0.02, 0.80, "0.2   2.95028e-07   5.68982e-07   14   27",
             fontsize=10.5, family="monospace", color=CORAL)
    axR.text(0.02, 0.70, "heterotypic_len   total_len   n_het   n_pairs",
             fontsize=7.6, family="monospace", color=MUTED)
    axR.annotate("", xy=(0.30, 0.44), xytext=(0.30, 0.66),
                 arrowprops=dict(arrowstyle="-", color=GRID, lw=1.2))
    axR.text(0.06, 0.50,
             r"$\frac{2.95\times10^{-7}}{5.69\times10^{-7}} = 0.5185$",
             fontsize=14, color=INK)
    axR.text(0.56, 0.50, r"$=\ \frac{14}{27} = 0.5185$", fontsize=14, color=GREEN)
    axR.text(0.06, 0.34, "fractional length = pair-count ratio   " + r"$\rightarrow$" + "  length weighting adds nothing",
             fontsize=9.2, color=INK, fontweight="medium")
    axR.text(0.06, 0.20,
             "Lengths sit at float-noise scale (1e-7). OS only becomes\n"
             "meaningful after the paper's 10 h relaxation compresses\n"
             "cells into genuine overlap — so cbc-04 must not sample OS early.",
             fontsize=8.8, color=MUTED, va="top")
    axR.set_title("Consequence: OS length is degenerate until relaxation",
                  fontsize=10.5, color=INK, loc="left", pad=8)

    fig.suptitle("Why overlapping-spheres boundary length is float-noise on the raw lattice",
                 fontsize=13, fontweight="bold", color=INK, x=0.005, ha="left", y=1.02)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    return save(fig, CHARTS, "01_os_boundary_degeneracy", {
        "title": "OS boundary length is degenerate on the pristine lattice",
        "caption": "Honeycomb neighbours are exactly tangent (2r−d=0), so the writer's "
                   "Heron's-formula shared edge is zero-length; the recorded OS metric "
                   "equals the pair-count ratio (14/27) with no length contribution.",
        "interpretation": "Not a bug but the paper's own OS configuration — the 10 h "
                          "relaxation is what conditions it, so OS must not be sampled "
                          "before compression (a constraint carried into cbc-04).",
    })


if __name__ == "__main__":
    print("wrote", build_scorecard(load_metrics()))
    print("wrote", build_os_degeneracy())
