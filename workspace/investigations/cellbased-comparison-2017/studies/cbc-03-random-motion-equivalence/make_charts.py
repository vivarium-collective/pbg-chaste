"""cbc-03: readouts for the random-motion equivalence study.

Two figures, from this study's recorded reproducibility_metrics (no engine re-run):

  00_free_diffusion_msd.png     the free-limit check — mainline DiffusionForce,
                                calibrated to scaling = xi*radius, reproduces the
                                paper's RandomMotionForce diffusion (MSD = 4*D*t).
  01_substitution_viability.png where the substitution holds (OS, VM) and where it
                                is mechanically blocked (VT: per-step remesh discards
                                node radii, which DiffusionForce divides by).
"""
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from _chartkit import (style, save, INK, MUTED, GRID, TEAL, CORAL, GREEN,  # noqa: E402
                       verdict_color)

CHARTS = os.path.join(HERE, "charts")

# Free-diffusion measurement (spikes/msd_diffusion.py, chaste/pychaste):
# 144 independent walkers, xi=0.1, dt=0.005, t=1. Recorded in study.yaml
# reproducibility_metrics + early_findings evidence.
XI = 0.1                       # D = xi (calibrated)
T_END = 1.0
SEM = 0.030                    # early_findings: "Measured MSD = 0.383, SEM 0.030"


def load():
    doc = yaml.safe_load(open(os.path.join(HERE, "study.yaml")))
    rm = doc["reproducibility_metrics"]["metrics"]
    msd = next(m for m in rm if m["observable"] == "free_diffusion_msd_2d")
    return doc, float(msd["tutorial_value"]), float(msd["reproduction_value"])


def build_msd(theory_end, measured_end):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.lines import Line2D
    style()
    fig, ax = plt.subplots(figsize=(7.8, 4.4))
    D = XI
    ts = np.linspace(0, T_END, 100)
    ax.plot(ts, 4 * D * ts, "-", color=TEAL, lw=2.6, zorder=2,
            solid_capstyle="round",
            label=r"theory  $\langle r^2\rangle = 4Dt$,  $D=\xi=0.1$")
    z = (measured_end - theory_end) / SEM
    ax.errorbar([T_END], [measured_end], yerr=[SEM], fmt="o", color=CORAL, ms=9,
                capsize=5, capthick=1.8, elinewidth=1.8, zorder=4,
                markerfacecolor="white", markeredgecolor=CORAL, markeredgewidth=2,
                label="DiffusionForce (144 walkers)")
    ax.plot([T_END], [theory_end], "o", color=TEAL, ms=8, zorder=3)
    # annotate the endpoint comparison
    ax.annotate(f"measured {measured_end:.3f}\n(theory {theory_end:.3f})",
                xy=(T_END, measured_end), xytext=(0.60, 0.20),
                fontsize=9.5, color=INK, ha="left", va="center",
                arrowprops=dict(arrowstyle="-", color=GRID, lw=1.2))
    ax.text(0.02, 0.95,
            f"z = {z:+.2f}   " + r"$\rightarrow$" + "   within noise (MATCH)",
            transform=ax.transAxes, fontsize=10, color=GREEN, fontweight="bold",
            va="top")
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 0.46)
    ax.set_xlabel("time  (h)")
    ax.set_ylabel(r"mean squared displacement  $\langle |r(t)-r(0)|^2 \rangle$")
    ax.set_title("Free-diffusion limit: DiffusionForce reproduces RandomMotionForce",
                 fontsize=13.5, fontweight="bold", color=INK, pad=26, loc="left")
    ax.text(0.0, 1.04,
            "144 independent 2D walkers · xi = 0.1 · dt = 0.005 · calibration scaling = xi·radius",
            transform=ax.transAxes, fontsize=9, color=MUTED, va="bottom")
    ax.legend(loc="lower right", frameon=False, fontsize=9.5)
    fig.tight_layout()
    return save(fig, CHARTS, "00_free_diffusion_msd", {
        "title": "Free-diffusion limit — DiffusionForce vs RandomMotionForce",
        "caption": "Mean squared displacement of 144 non-interacting walkers under "
                   "mainline DiffusionForce (coral, ±SEM) against the analytic 4·D·t "
                   "line the paper's RandomMotionForce also follows (D = xi = 0.1).",
        "interpretation": "Measured MSD 0.383 vs theory 0.400 (z = −0.56) — a match. "
                          "The calibration scaling = xi·radius makes DiffusionForce a "
                          "sound substitute in the free limit (OS, VM).",
    })


def build_viability():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    style()
    rows = [
        ("OS  ·  Overlapping spheres", "match",
         "NodeBasedCellPopulation keeps node radii, so DiffusionForce runs; free-limit MSD matches."),
        ("VM  ·  Vertex model", "match",
         "Radii preserved across steps, so DiffusionForce runs; sorting trajectories track cbc-01."),
        ("VT  ·  Voronoi tessellation", "blocked",
         "Per-step remesh discards node radii, which DiffusionForce divides by and throws — "
         "mechanical, not tuning, so VT stays deterministic."),
    ]
    fig, ax = plt.subplots(figsize=(9.4, 0.98 * len(rows) + 1.5))
    ax.set_xlim(0, 10); ax.set_ylim(0, len(rows))
    ax.axis("off")
    for i, (model, verdict, why) in enumerate(rows):
        y = len(rows) - 1 - i + 0.5
        col = verdict_color(verdict)
        ax.add_patch(FancyBboxPatch((0.1, y - 0.34), 9.8, 0.82,
                     boxstyle="round,pad=0.02,rounding_size=0.06",
                     fc=col, ec="none", alpha=0.07, zorder=0))
        ax.plot([0.18, 0.18], [y - 0.30, y + 0.44], color=col, lw=4,
                solid_capstyle="round", zorder=2)
        ax.text(0.45, y + 0.22, model, fontsize=11.5, color=INK, va="center", fontweight="medium")
        ax.text(0.45, y - 0.14, why, fontsize=8.7, color=MUTED, va="center")
        pill = FancyBboxPatch((8.35, y + 0.02), 1.35, 0.42,
                              boxstyle="round,pad=0.02,rounding_size=0.21",
                              fc=col, ec="none", alpha=0.18, zorder=2)
        ax.add_patch(pill)
        label = "SOUND" if verdict == "match" else "BLOCKED"
        ax.text(9.02, y + 0.23, label, fontsize=8.5, color=col, ha="center",
                va="center", fontweight="bold", zorder=3)
    fig.suptitle("DiffusionForce as the RandomMotionForce substitute — where it holds",
                 fontsize=13, fontweight="bold", color=INK, x=0.005, ha="left", y=1.0)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    return save(fig, CHARTS, "01_substitution_viability", {
        "title": "DiffusionForce substitution — viability by model",
        "caption": "Which models can use mainline DiffusionForce for the paper's random "
                   "motion: sound for OS and VM, mechanically blocked for VT.",
        "interpretation": "OS/VM keep node radii so DiffusionForce runs and matches the "
                          "free limit; VT's per-step remesh discards radii, so VT remains "
                          "deterministic — a refutation carried from cbc-02.",
    })


if __name__ == "__main__":
    _, theory_end, measured_end = load()
    print("wrote", build_msd(theory_end, measured_end))
    print("wrote", build_viability())
