"""cbc-01: reproduction readout for the C++ ground-truth baseline.

Adds a paper-vs-reproduction dumbbell of the normalized fractional-length
endpoint (Osborne et al. 2017 Fig 3, k_pert=1) for all five models, read from
this study's own reproducibility_metrics block. The existing
00_cxx_fractional_length.png shows the trajectories; this shows how closely our
regenerated C++ endpoints land on the published figure.
"""
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from _chartkit import style, save, INK, MUTED, TEAL, CORAL, verdict_color  # noqa: E402

CHARTS = os.path.join(HERE, "charts")
LABEL = {"cp": "CP", "os": "OS", "vt": "VT", "vm": "VM", "ca": "CA"}
NAME = {"cp": "Cellular Potts", "os": "Overlapping spheres",
        "vt": "Voronoi tessellation", "vm": "Vertex model",
        "ca": "Cellular automaton"}


def load_endpoints():
    doc = yaml.safe_load(open(os.path.join(HERE, "study.yaml")))
    rows = []
    for m in doc["reproducibility_metrics"]["metrics"]:
        if m["observable"] == "normalized_fractional_length_endpoint":
            rows.append((m["model"], float(m["tutorial_value"]),
                         float(m["reproduction_value"]), m.get("verdict", "")))
    # order most-sorted (lowest residual interface) → least
    rows.sort(key=lambda r: r[2])
    return rows


def build(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    style()
    fig, ax = plt.subplots(figsize=(7.6, 3.9))
    ys = list(range(len(rows)))[::-1]
    for y, (m, paper, repro, verdict) in zip(ys, rows):
        ax.plot([paper, repro], [y, y], "-", color="#c7d0da", lw=3,
                solid_capstyle="round", zorder=1)
        ax.plot(paper, y, "o", color=TEAL, ms=9, zorder=3)
        ax.plot(repro, y, "o", color=CORAL, ms=9, zorder=3,
                markerfacecolor="white", markeredgecolor=CORAL, markeredgewidth=2)
        d = abs(paper - repro)
        ax.text(max(paper, repro) + 0.03, y,
                f"Δ {d:.02f}", va="center", ha="left", fontsize=8.5,
                color=verdict_color(verdict))
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{LABEL[m]}  ·  {NAME[m]}" for m, *_ in rows],
                       fontsize=10, color=INK)
    ax.set_xlim(-0.03, 1.06)
    ax.set_xlabel("normalized fractional boundary length at endpoint  (1.0 = value at labelling)")
    ax.set_title("Regenerated C++ baseline vs the published figure",
                 fontsize=14, fontweight="bold", color=INK, pad=30, loc="left")
    ax.text(0.0, 1.045, "Lower = more sorted · one seed · endpoints read off Osborne et al. 2017 Fig 3-left",
            transform=ax.transAxes, fontsize=9, color=MUTED, va="bottom")
    handles = [Line2D([0], [0], marker="o", color="w", markerfacecolor=TEAL,
                      markersize=9, label="paper (Fig 3)"),
               Line2D([0], [0], marker="o", color="w", markerfacecolor="white",
                      markeredgecolor=CORAL, markeredgewidth=2, markersize=9,
                      label="our C++ run")]
    ax.legend(handles=handles, loc="upper right", frameon=False, fontsize=9.5)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return save(fig, CHARTS, "01_paper_vs_reproduction_endpoints", {
        "title": "Regenerated C++ baseline vs the published figure",
        "caption": "Normalized fractional-length endpoint per model — teal = Osborne "
                   "et al. 2017 Fig 3, hollow coral = our regenerated C++ run. Models "
                   "ordered most-sorted (OS) to least (VT).",
        "interpretation": "Every model lands within 0.06 of the published endpoint and "
                          "the ordering (OS < CP < CA < VM < VT) matches Fig 3 exactly, "
                          "confirming the build + paper-parameter restoration.",
    })


if __name__ == "__main__":
    out = build(load_endpoints())
    print("wrote", out)
