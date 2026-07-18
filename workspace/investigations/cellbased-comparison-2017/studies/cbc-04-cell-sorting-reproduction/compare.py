"""cbc-04: compare the PyChaste sorting reproduction against the cbc-01 C++ baseline.

Loads both sources' fractional-length trajectories, aligns them per model on the
1.0-hour sampling grid, and reports the per-model maximum absolute divergence plus
a Fig-3-style overlay (raw and normalized). This is the investigation's headline
result: the quantitative sense in which pbg-chaste reproduces Osborne et al. 2017.

Outputs (in this study dir):
  comparison_table.csv      per-model frac@110 (cxx vs pychaste) + max abs diff
  fractional_length.png     overlay of both sources per model (normalized)
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CXX = os.path.join(HERE, "cxx-baseline")
PYC = os.path.join(HERE, "pychaste-baseline")

sys.path.insert(0, os.path.join(HERE, "..", "..", "..", ".."))  # repo root for pbg_chaste
from pbg_chaste.sorting_analysis import load_source, compare  # noqa: E402

MODELS = ["ca", "cp", "os", "vt", "vm"]
LABELS = {"ca": "CA", "cp": "CP", "os": "OS", "vt": "VT", "vm": "VM"}


def _normalize(tr):
    """Fractional length divided by its value at labelling (t=10), as in Fig 3."""
    base = tr.at(10.0)
    if not base:
        # fall back to first defined value
        base = next((x for x in tr.fractional_length if x), None)
    if not base:
        return tr.times, tr.fractional_length
    norm = [None if v is None else v / base for v in tr.fractional_length]
    return tr.times, norm


def main():
    cxx = load_source(CXX, "cxx")
    pyc = load_source(PYC, "pychaste")
    print("cxx models:", sorted(cxx), "| pychaste models:", sorted(pyc))

    rows = []
    for m in MODELS:
        c, p = cxx.get(m), pyc.get(m)
        cend = c.endpoint if c else None
        pend = p.endpoint if p else None
        maxdiff = None
        note = ""
        if c and p:
            cmp = compare(c, p)
            maxdiff = cmp.max_abs_diff
        elif m == "ca":
            note = "CA unsupported in PyChaste (custom Ca switching rule)"
        elif m == "vt" and p:
            note = "VT PyChaste runs without random motion (DiffusionForce incompatible; cbc-03)"
        rows.append((m, cend, pend, maxdiff, note))

    # table
    with open(os.path.join(HERE, "comparison_table.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "cxx_frac_end", "pychaste_frac_end", "max_abs_diff", "note"])
        for m, ce, pe, md, note in rows:
            w.writerow([m,
                        "" if ce is None else "%.4f" % ce,
                        "" if pe is None else "%.4f" % pe,
                        "" if md is None else "%.4f" % md, note])
    print("\n%-5s %12s %12s %12s  %s" % ("model", "cxx@110", "pyc@110", "max|diff|", "note"))
    for m, ce, pe, md, note in rows:
        print("%-5s %12s %12s %12s  %s" % (
            LABELS[m],
            "-" if ce is None else "%.4f" % ce,
            "-" if pe is None else "%.4f" % pe,
            "-" if md is None else "%.4f" % md, note))

    # figure (normalized overlay)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, len(MODELS), figsize=(4 * len(MODELS), 3.4), sharey=True)
        for ax, m in zip(axes, MODELS):
            c, p = cxx.get(m), pyc.get(m)
            if c:
                t, n = _normalize(c)
                ax.plot(t, n, "-", color="#1f77b4", lw=2, label="C++ (cbc-01)")
            if p:
                t, n = _normalize(p)
                ax.plot(t, n, "--", color="#d62728", lw=2, label="PyChaste (cbc-04)")
            ax.set_title(LABELS[m])
            ax.set_xlabel("time (h)")
            ax.set_ylim(0, 1.1)
            ax.axhline(0.15 / (c.at(10.0) if (c and c.at(10.0)) else 1), color="grey",
                       ls=":", lw=1) if c else None
        axes[0].set_ylabel("fractional length (norm. to t=10)")
        axes[-1].legend(fontsize=8, loc="upper right")
        fig.suptitle("Cell sorting: PyChaste vs C++ baseline (k_pert=1)")
        fig.tight_layout()
        out = os.path.join(HERE, "fractional_length.png")
        fig.savefig(out, dpi=110)
        print("\nwrote", out)
    except Exception as e:
        print("figure skipped:", type(e).__name__, e)


if __name__ == "__main__":
    main()
