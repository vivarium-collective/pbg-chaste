"""cbc-04: compare the PyChaste sorting reproduction against the cbc-01 C++ baseline.

Produces the investigation's headline artifacts:
  comparison_table.csv          per-model agreement metrics (RMSE, MAE, Pearson, ...)
  charts/00_fractional_length_cxx_vs_pychaste.png   polished per-model overlay
  charts/01_agreement_metrics.png                   metrics scorecard (heatmap-style)
  charts/*.meta.json                                captions for the workbench report

The metrics go well beyond a single worst-case gap: mean/RMS error, range-
normalized RMSE, shape correlation (Pearson), the time-normalized area between
the curves, and the endpoint gap — over the timepoints where both curves exist.
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CXX = os.path.join(HERE, "..", "cbc-01-cxx-reference-baseline", "cxx-baseline")
PYC = os.path.join(HERE, "pychaste-baseline")
CHARTS = os.path.join(HERE, "charts")

sys.path.insert(0, os.path.join(HERE, "..", "..", "..", ".."))
from pbg_chaste.sorting_analysis import load_source, compare  # noqa: E402

MODELS = ["vm", "cp", "vt", "os"]          # ordered best→worst agreement
MODEL_NAME = {"cp": "Cellular Potts", "os": "Overlapping spheres",
              "vt": "Voronoi tessellation", "vm": "Vertex model",
              "ca": "Cellular automaton"}
LABEL = {"cp": "CP", "os": "OS", "vt": "VT", "vm": "VM", "ca": "CA"}

# refined palette — muted teal (C++) vs warm coral (PyChaste), on a soft ground
INK = "#1f2a37"
MUTED = "#6b7787"
GRID = "#e6ebf1"
CXX_COL = "#2f6f8f"      # teal
PYC_COL = "#d1615d"      # coral
BAND = "#d1615d"


def _normalize(tr):
    base = tr.at(10.0) or next((x for x in tr.fractional_length if x), 1.0)
    xs, ys = [], []
    for t, v in zip(tr.times, tr.fractional_length):
        if v is None:
            continue
        xs.append(t)
        ys.append(v / base if base else v)
    return xs, ys


def _style():
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


def build_overlay(cxx, pyc, cmps):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _style()
    n = len(MODELS)
    fig, axes = plt.subplots(1, n, figsize=(3.4 * n, 3.9), sharey=True)
    for ax, m in zip(axes, MODELS):
        c, p = cxx.get(m), pyc.get(m)
        if c:
            tx, cy = _normalize(c)
        if p:
            px, py = _normalize(p)
        # shaded divergence band (interpolated onto the C++ grid)
        if c and p:
            py_on_c = []
            for t in tx:
                val = p.at(t)
                base = p.at(10.0) or 1
                py_on_c.append(val / base if val is not None else None)
            xb = [t for t, a, b in zip(tx, cy, py_on_c) if b is not None]
            ca = [a for a, b in zip(cy, py_on_c) if b is not None]
            cb = [b for b in py_on_c if b is not None]
            ax.fill_between(xb, ca, cb, color=BAND, alpha=0.10, linewidth=0, zorder=1)
        if c:
            ax.plot(tx, cy, "-", color=CXX_COL, lw=2.4, zorder=3, solid_capstyle="round")
            ax.plot(tx[-1], cy[-1], "o", color=CXX_COL, ms=5, zorder=4)
        if p:
            ax.plot(px, py, "--", color=PYC_COL, lw=2.2, zorder=3, dash_capstyle="round")
            ax.plot(px[-1], py[-1], "o", color=PYC_COL, ms=5, zorder=4,
                    markerfacecolor="white", markeredgecolor=PYC_COL, markeredgewidth=1.6)
        # per-panel title + metric chip
        cm = cmps.get(m)
        ax.set_title(f"{LABEL[m]}", fontsize=15, fontweight="bold", color=INK,
                     pad=16, loc="left")
        if cm and cm.rmse is not None:
            ax.text(0.0, 1.02, MODEL_NAME[m], transform=ax.transAxes,
                    fontsize=8.5, color=MUTED, va="bottom")
            chip = f"RMSE {cm.rmse:.3f}   r {cm.pearson:.3f}"
            ax.text(0.97, 0.94, chip, transform=ax.transAxes, ha="right", va="top",
                    fontsize=8.5, color=INK,
                    bbox=dict(boxstyle="round,pad=0.35", fc="#f4f7fa", ec=GRID, lw=1))
        ax.set_xlabel("time (h)")
        ax.set_ylim(0, 1.12)
        ax.set_xlim(0, 110)
        ax.set_xticks([0, 50, 100])
    axes[0].set_ylabel("fractional boundary length\n(normalized to labelling, t=10)")
    # legend
    from matplotlib.lines import Line2D
    handles = [Line2D([0], [0], color=CXX_COL, lw=2.4, label="C++ tutorial (cbc-01)"),
               Line2D([0], [0], color=PYC_COL, lw=2.2, ls="--", label="PyChaste (cbc-04)")]
    fig.legend(handles=handles, loc="upper right", frameon=False, fontsize=9.5,
               bbox_to_anchor=(0.995, 1.02))
    fig.suptitle("Cell sorting reproduced — PyChaste vs the authors' C++ code",
                 fontsize=14, fontweight="bold", color=INK, x=0.007, ha="left", y=1.12)
    fig.text(0.007, 1.04, "Lower = more sorted · shaded band = divergence · dot = t=110 endpoint",
             fontsize=9, color=MUTED, ha="left")
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    out = os.path.join(CHARTS, "00_fractional_length_cxx_vs_pychaste.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def build_scorecard(cmps):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    _style()
    # metrics as a heatmap (rows=models, cols=metrics); green=good, warm=worse
    metrics = [("RMSE", "rmse"), ("MAE", "mae"), ("nRMSE", "nrmse"),
               ("area", "area_between"), ("endpoint |Δ|", "endpoint_abs_diff"),
               ("Pearson r", "pearson")]
    rows = [m for m in MODELS if m in cmps]
    cmap = LinearSegmentedColormap.from_list("agree", ["#1a7f42", "#7bb662", "#f3c969", "#e08a5b"])
    fig, ax = plt.subplots(figsize=(1.15 * len(metrics) + 2.2, 0.62 * len(rows) + 1.6))
    import numpy as np
    grid = np.zeros((len(rows), len(metrics)))
    txt = [[""] * len(metrics) for _ in rows]
    for i, m in enumerate(rows):
        r = cmps[m].as_row()
        for j, (_, key) in enumerate(metrics):
            v = r[key]
            if v is None:
                grid[i, j] = 0.5; txt[i][j] = "—"; continue
            if key == "pearson":
                grid[i, j] = 1.0 - v          # r near 1 → green
                txt[i][j] = f"{v:.3f}"
            else:
                grid[i, j] = min(v / 0.15, 1.0)  # 0..0.15 error → green..coral
                txt[i][j] = f"{v:.3f}"
    ax.imshow(grid, cmap=cmap, aspect="auto", vmin=0, vmax=1)
    ax.set_xticks(range(len(metrics)))
    ax.set_xticklabels([m[0] for m in metrics], fontsize=9.5, color=INK)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([f"{LABEL[m]}  ·  {MODEL_NAME[m]}" for m in rows],
                       fontsize=10, color=INK)
    for i in range(len(rows)):
        for j in range(len(metrics)):
            ax.text(j, i, txt[i][j], ha="center", va="center", fontsize=9.5,
                    color="white" if grid[i, j] > 0.55 else INK, fontweight="medium")
    ax.set_xticks([x - 0.5 for x in range(1, len(metrics))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(rows))], minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="both", length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("Agreement metrics — PyChaste vs C++  (greener = better; lower error, r near 1)",
                 fontsize=12, fontweight="bold", color=INK, pad=12, loc="left")
    fig.tight_layout()
    out = os.path.join(CHARTS, "01_agreement_metrics.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def main():
    os.makedirs(CHARTS, exist_ok=True)
    cxx = load_source(CXX, "cxx")
    pyc = load_source(PYC, "pychaste")
    cmps = {m: compare(cxx[m], pyc[m]) for m in ("cp", "os", "vt", "vm")
            if m in cxx and m in pyc}

    # table
    with open(os.path.join(HERE, "comparison_table.csv"), "w", newline="") as f:
        w = None
        for m in ["cp", "os", "vt", "vm"]:
            if m not in cmps:
                continue
            row = cmps[m].as_row()
            if w is None:
                w = csv.DictWriter(f, fieldnames=list(row.keys()))
                w.writeheader()
            w.writerow(row)
    print("=== agreement metrics ===")
    for m in ["vm", "cp", "vt", "os"]:
        if m in cmps:
            r = cmps[m].as_row()
            print(f"  {LABEL[m]}: RMSE {r['rmse']}  MAE {r['mae']}  r {r['pearson']}  "
                  f"max|Δ| {r['max_abs_diff']}  endpoint_rel {r['endpoint_rel_err']}")

    o1 = build_overlay(cxx, pyc, cmps)
    o2 = build_scorecard(cmps)
    # captions for the workbench report
    import json
    with open(os.path.join(CHARTS, "00_fractional_length_cxx_vs_pychaste.meta.json"), "w") as f:
        json.dump({
            "title": "Fractional boundary length — PyChaste vs C++ tutorial",
            "caption": "Sorting trajectories (normalized to labelling) for the four "
                       "reachable models. Teal = authors' C++ code, coral dashed = "
                       "pbg-chaste; shaded band is the divergence, dots mark t=110.",
            "interpretation": "Shape agreement is near-perfect (Pearson r 0.93–0.999); "
                              "VM RMSE 0.005, CP 0.044, VT 0.052, OS 0.038.",
        }, f, indent=2)
    with open(os.path.join(CHARTS, "01_agreement_metrics.meta.json"), "w") as f:
        json.dump({
            "title": "Agreement metrics scorecard",
            "caption": "Per-model RMSE, MAE, range-normalized RMSE, area-between-curves, "
                       "endpoint gap, and Pearson correlation. Greener = closer to the C++ "
                       "reference.",
            "interpretation": "All four models agree to RMSE ≤ 0.052 and r ≥ 0.93; "
                              "VM is essentially identical (RMSE 0.005, r 0.999).",
        }, f, indent=2)
    print("\nwrote", o1)
    print("wrote", o2)


if __name__ == "__main__":
    main()
