"""Reduction + comparison for the Osborne et al. 2017 cell-sorting measure.

The sorting case study is scored by *fractional boundary length*: the length of
interface between unlike (labelled vs unlabelled) cells divided by the total
shared interface length. Chaste's HeterotypicBoundaryLengthWriter emits the two
lengths separately (it does not divide), so the fraction is computed here.

This module reads heterotypicboundary.dat files — from either the paper authors'
C++ runs (cbc-01) or our PyChaste runs (cbc-04) — reduces them to fractional-length
trajectories, and compares the two sources per model per timepoint. It is the
shared currency that lets cbc-04 state, quantitatively, whether pbg-chaste
reproduces the paper.

heterotypicboundary.dat columns (whitespace-separated, one row per sampled time):
  0 time
  1 heterotypic_boundary_length
  2 total_shared_edge_length
  3 num_heterotypic_pairs
  4 total_num_pairs

fractional_length = col1 / col2. When col2 == 0 the fraction is undefined (e.g.
an OS tissue still in the tangent configuration before relaxation) — reported as
None, never silently 0.0.
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field


@dataclass
class Trajectory:
    """A single run's fractional-length time series."""
    model: str
    source: str                       # "cxx" | "pychaste" | free label
    times: list[float] = field(default_factory=list)
    fractional_length: list[float | None] = field(default_factory=list)
    pair_fraction: list[float | None] = field(default_factory=list)
    path: str | None = None

    def at(self, t: float, tol: float = 1e-6) -> float | None:
        for tt, fl in zip(self.times, self.fractional_length):
            if abs(tt - t) <= tol:
                return fl
        return None

    @property
    def endpoint(self) -> float | None:
        return self.fractional_length[-1] if self.fractional_length else None


def read_dat(path: str, *, model: str = "?", source: str = "?") -> Trajectory:
    """Parse one heterotypicboundary.dat into a Trajectory."""
    traj = Trajectory(model=model, source=source, path=path)
    with open(path) as f:
        for line in f:
            cols = line.split()
            if len(cols) < 5:
                continue
            try:
                t, het, total, hpairs, tpairs = (float(cols[i]) for i in range(5))
            except ValueError:
                continue
            traj.times.append(t)
            traj.fractional_length.append(het / total if total > 0 else None)
            traj.pair_fraction.append(hpairs / tpairs if tpairs > 0 else None)
    return traj


#: How each source lays out its per-model output directories.
#: cbc-01 (C++): CHASTE_TEST_OUTPUT/CellSorting/{Ca,Potts,Node,Mesh,Vertex}/...
#: cbc-04 (PyChaste _sorting_server): CHASTE_TEST_OUTPUT/pbg_sort_{cp,os,vt,vm}/...
CXX_MODEL_DIRS = {"ca": "Ca", "cp": "Potts", "os": "Node", "vt": "Mesh", "vm": "Vertex"}
PYCHASTE_MODEL_DIRS = {m: f"pbg_sort_{m}" for m in ("cp", "os", "vt", "vm")}


def _find_dats(root: str, subdir: str) -> list[str]:
    """All heterotypicboundary.dat files under a model dir.

    Chaste writes one per results_from_time_<t> phase (e.g. a relaxation phase
    from t=0 and a sorting phase from t=10). The full trajectory is their
    concatenation in time order — returning only the first (alphabetically
    results_from_time_0) would give just the pre-label relaxation, which carries
    no labels and hence fractional length 0 throughout.
    """
    hits = glob.glob(os.path.join(root, subdir, "**", "heterotypicboundary.dat"),
                     recursive=True)
    if not hits:
        hits = glob.glob(os.path.join(root, "**", subdir, "**",
                                      "heterotypicboundary.dat"), recursive=True)
    return sorted(hits)


def _merge_dats(paths: list[str], *, model: str, source: str) -> Trajectory | None:
    """Merge phase files into one trajectory, ordered by time (later phase wins ties)."""
    rows: dict[float, tuple[float | None, float | None]] = {}
    for p in paths:
        tr = read_dat(p, model=model, source=source)
        for t, fl, pf in zip(tr.times, tr.fractional_length, tr.pair_fraction):
            rows[t] = (fl, pf)          # later files (higher phase) overwrite ties
    if not rows:
        return None
    merged = Trajectory(model=model, source=source, path=";".join(paths))
    for t in sorted(rows):
        fl, pf = rows[t]
        merged.times.append(t)
        merged.fractional_length.append(fl)
        merged.pair_fraction.append(pf)
    return merged


def load_source(root: str, source: str) -> dict[str, Trajectory]:
    """Load every model's trajectory under an output root.

    source="cxx" uses the C++ CellSorting/<Model> layout; source="pychaste" uses
    the pbg_sort_<model> layout. Models with no file are omitted (e.g. CA under
    pychaste, which is unsupported).
    """
    mapping = CXX_MODEL_DIRS if source == "cxx" else PYCHASTE_MODEL_DIRS
    out: dict[str, Trajectory] = {}
    for model, subdir in mapping.items():
        paths = _find_dats(root, subdir)
        if paths:
            merged = _merge_dats(paths, model=model, source=source)
            if merged is not None:
                out[model] = merged
    return out


@dataclass
class ModelComparison:
    model: str
    times: list[float]
    cxx: list[float | None]
    pychaste: list[float | None]
    abs_diff: list[float | None]
    # scalar agreement metrics over the shared, both-defined timepoints
    max_abs_diff: float | None = None   # worst pointwise gap
    mae: float | None = None            # mean absolute error
    rmse: float | None = None           # root-mean-square error
    nrmse: float | None = None          # RMSE / observed range of the C++ curve
    pearson: float | None = None        # trajectory shape correlation
    area_between: float | None = None   # trapezoidal ∫|cxx-pyc| dt, time-normalized
    endpoint_abs_diff: float | None = None
    endpoint_rel_err: float | None = None
    n_points: int = 0
    note: str = ""

    def as_row(self) -> dict:
        def f(x, nd=4):
            return None if x is None else round(x, nd)
        return {
            "model": self.model,
            "max_abs_diff": f(self.max_abs_diff),
            "mae": f(self.mae),
            "rmse": f(self.rmse),
            "nrmse": f(self.nrmse),
            "pearson": f(self.pearson, 3),
            "area_between": f(self.area_between),
            "endpoint_abs_diff": f(self.endpoint_abs_diff),
            "endpoint_rel_err": f(self.endpoint_rel_err, 3),
            "n_points": self.n_points,
            "note": self.note,
        }


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / (sxx ** 0.5 * syy ** 0.5)


def compare(cxx: Trajectory, pychaste: Trajectory, *, tol: float = 1e-6) -> ModelComparison:
    """Align two trajectories on shared timepoints and compute agreement metrics.

    Beyond the worst-case gap (max_abs_diff), reports whole-trajectory metrics a
    reviewer actually needs: mean/RMS error, range-normalized RMSE, shape
    correlation (Pearson), the time-normalized area between the curves, and the
    endpoint gap in absolute and relative terms. All are over the timepoints
    where BOTH curves are defined.
    """
    times, a, b, diff = [], [], [], []
    xs, ys, ts = [], [], []   # both-defined pairs for the scalar metrics
    for tt, fa in zip(cxx.times, cxx.fractional_length):
        fb = pychaste.at(tt, tol=tol)
        if fb is None and fa is None:
            continue
        times.append(tt)
        a.append(fa)
        b.append(fb)
        if fa is not None and fb is not None:
            diff.append(abs(fa - fb))
            xs.append(fa)
            ys.append(fb)
            ts.append(tt)
        else:
            diff.append(None)

    cmp = ModelComparison(model=cxx.model, times=times, cxx=a, pychaste=b, abs_diff=diff)
    real = [d for d in diff if d is not None]
    if not real:
        return cmp
    n = len(xs)
    cmp.n_points = n
    cmp.max_abs_diff = max(real)
    cmp.mae = sum(real) / len(real)
    cmp.rmse = (sum((x - y) ** 2 for x, y in zip(xs, ys)) / n) ** 0.5
    rng = max(xs) - min(xs)
    cmp.nrmse = (cmp.rmse / rng) if rng > 0 else None
    cmp.pearson = _pearson(xs, ys)
    # trapezoidal area between |cxx-pyc| over time, normalized by the time span
    if len(ts) >= 2:
        area = 0.0
        for i in range(1, len(ts)):
            dt = ts[i] - ts[i - 1]
            d0 = abs(xs[i - 1] - ys[i - 1])
            d1 = abs(xs[i] - ys[i])
            area += 0.5 * (d0 + d1) * dt
        span = ts[-1] - ts[0]
        cmp.area_between = (area / span) if span > 0 else None
    cmp.endpoint_abs_diff = abs(xs[-1] - ys[-1])
    cmp.endpoint_rel_err = (cmp.endpoint_abs_diff / abs(xs[-1])) if xs[-1] else None
    return cmp
