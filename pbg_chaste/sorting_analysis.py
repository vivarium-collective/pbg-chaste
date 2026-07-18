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


def _find_dat(root: str, subdir: str) -> str | None:
    hits = glob.glob(os.path.join(root, subdir, "**", "heterotypicboundary.dat"),
                     recursive=True)
    if not hits:
        hits = glob.glob(os.path.join(root, "**", subdir, "**",
                                      "heterotypicboundary.dat"), recursive=True)
    return sorted(hits)[0] if hits else None


def load_source(root: str, source: str) -> dict[str, Trajectory]:
    """Load every model's trajectory under an output root.

    source="cxx" uses the C++ CellSorting/<Model> layout; source="pychaste" uses
    the pbg_sort_<model> layout. Models with no file are omitted (e.g. CA under
    pychaste, which is unsupported).
    """
    mapping = CXX_MODEL_DIRS if source == "cxx" else PYCHASTE_MODEL_DIRS
    out: dict[str, Trajectory] = {}
    for model, subdir in mapping.items():
        path = _find_dat(root, subdir)
        if path:
            out[model] = read_dat(path, model=model, source=source)
    return out


@dataclass
class ModelComparison:
    model: str
    times: list[float]
    cxx: list[float | None]
    pychaste: list[float | None]
    abs_diff: list[float | None]
    max_abs_diff: float | None
    note: str = ""


def compare(cxx: Trajectory, pychaste: Trajectory, *, tol: float = 1e-6) -> ModelComparison:
    """Align two trajectories on shared timepoints and diff fractional length."""
    times, a, b, diff = [], [], [], []
    for tt, fa in zip(cxx.times, cxx.fractional_length):
        fb = pychaste.at(tt, tol=tol)
        if fb is None and fa is None:
            continue
        times.append(tt)
        a.append(fa)
        b.append(fb)
        diff.append(abs(fa - fb) if (fa is not None and fb is not None) else None)
    real = [d for d in diff if d is not None]
    return ModelComparison(
        model=cxx.model, times=times, cxx=a, pychaste=b, abs_diff=diff,
        max_abs_diff=max(real) if real else None,
    )
