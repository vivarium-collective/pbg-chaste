"""Process-bigraph wrapper for the real Chaste cell-based simulator.

A single parametrized :class:`ChasteSimulationProcess` exposes Chaste's three
multi-cellular population methods (mesh / vertex / node) crossed with four
sub-cellular cell-cycle models (uniform / stochastic / Tyson-Novak ODE /
Delta-Notch reaction network). The engine is the genuine Chaste C++ library,
driven inside the ``chaste/pychaste`` Docker image via a resident
:class:`pbg_chaste.runtime.ChasteSession` — no science is reimplemented here.
"""

from __future__ import annotations

from process_bigraph import Process

from . import runtime

POPULATIONS = ("mesh", "vertex", "node")
CELL_CYCLES = ("uniform", "stochastic", "tyson_novak", "delta_notch")

#: Model classes of Osborne et al. 2017 that PyChaste can reach.
#: CA is absent: its DifferentialAdhesionCaSwitchingUpdateRule is custom to the
#: paper's repo and AbstractCaSwitchingUpdateRule_2 exposes no constructor to
#: subclass. See workspace/investigations/cellbased-comparison-2017/probes/.
SORTING_MODELS = ("cp", "os", "vt", "vm")


class ChasteSimulationProcess(Process):
    """Advance a real Chaste ``OffLatticeSimulation`` one interval per update.

    Config selects the *multi-cellular* population method and the *sub-cellular*
    cell-cycle model; every combination is a valid simulation. A resident
    container holds the simulator in memory between steps (Chaste resumes on
    repeated ``Solve``), so each update is a genuine continuation, not a restart.

    Inputs (control signals a sibling process may write each step)
    -------------------------------------------------------------
    spring_stiffness : float
        Tissue mechanical stiffness applied to the live force law before each
        step (Meineke spring stiffness for mesh/node, Nagai-Honda deformation
        energy for vertex). Lets an upstream controller modulate mechanics.
        <= 0 leaves Chaste's default untouched.

    Outputs
    -------
    num_cells : integer
        **Delta** in real-cell count over the interval — composes additively
        with sibling division/death processes.
    positions : overwrite[list[list[float]]]
        Absolute snapshot of cell-centre coordinates (sensor reading).
    phase_counts : overwrite[map[string,float]]
        Cells per proliferative phase this step (phase-based cycle models only).
    mean_delta, mean_notch : overwrite[float]
        Sub-cellular Delta/Notch means (delta_notch model only; else 0.0).
    """

    config_schema = {
        "population": {"_type": "string", "_default": "mesh"},
        "cell_cycle": {"_type": "string", "_default": "uniform"},
        "width": {"_type": "integer", "_default": 4},
        "height": {"_type": "integer", "_default": 4},
        "spring_cutoff": {"_type": "float", "_default": 1.5},
        "sampling_multiple": {"_type": "integer", "_default": 12},
        "seed": {"_type": "integer", "_default": 0},
        "timeout": {"_type": "float", "_default": 120.0},
        "start_timeout": {"_type": "float", "_default": 300.0},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config, core)
        pop = self.config["population"]
        cyc = self.config["cell_cycle"]
        if pop not in POPULATIONS:
            raise ValueError(f"population must be one of {POPULATIONS}, got {pop!r}")
        if cyc not in CELL_CYCLES:
            raise ValueError(f"cell_cycle must be one of {CELL_CYCLES}, got {cyc!r}")
        if pop == "vertex" and cyc == "delta_notch":
            # Real Chaste limitation: vertex Delta-Notch needs the edge-based
            # SRN framework, which this wrapper does not yet wire. All other
            # 11 population × cell-cycle combinations are supported.
            raise NotImplementedError(
                "vertex + delta_notch is not supported (requires Chaste's "
                "edge-based SRN framework). Use 'mesh' or 'node' with "
                "delta_notch, or a different cell cycle with 'vertex'."
            )
        self._session: runtime.ChasteSession | None = None
        self._prev_cells: int | None = None

    def inputs(self):
        return {"spring_stiffness": "float"}

    def outputs(self):
        return {
            "num_cells": "integer",
            "positions": "overwrite[list[list[float]]]",
            "phase_counts": "overwrite[map[string,float]]",
            "mean_delta": "overwrite[float]",
            "mean_notch": "overwrite[float]",
        }

    def initial_state(self):
        return {"spring_stiffness": 0.0}

    def _ensure_session(self):
        if self._session is None:
            self._session = runtime.ChasteSession(
                {
                    "population": self.config["population"],
                    "cell_cycle": self.config["cell_cycle"],
                    "width": self.config["width"],
                    "height": self.config["height"],
                    "spring_cutoff": self.config["spring_cutoff"],
                    "sampling_multiple": self.config["sampling_multiple"],
                    "seed": self.config["seed"],
                },
                step_timeout=float(self.config["timeout"]),
                start_timeout=float(self.config["start_timeout"]),
            )
            state = self._session.start()
            self._prev_cells = int(state["num_cells"])

    def update(self, state, interval):
        self._ensure_session()
        stiffness = float(state.get("spring_stiffness", 0.0))
        result = self._session.step(interval, stiffness=stiffness)

        n = int(result["num_cells"])
        d_cells = 0 if self._prev_cells is None else n - self._prev_cells
        self._prev_cells = n

        return {
            "num_cells": d_cells,
            "positions": result.get("positions", []),
            "phase_counts": result.get("phase_counts", {}),
            "mean_delta": float(result.get("mean_delta", 0.0)),
            "mean_notch": float(result.get("mean_notch", 0.0)),
        }

    def __del__(self):
        # best-effort container cleanup; the container also self-exits when idle
        try:
            if self._session is not None:
                self._session.close()
        except Exception:
            pass


class ChasteCellSortingProcess(Process):
    """Cell sorting by differential adhesion (Osborne et al. 2017, Figs 2-4).

    Reproduces the paper's first case study across the four model classes
    PyChaste can reach — ``cp`` (cellular Potts), ``os`` (overlapping spheres),
    ``vt`` (Voronoi tessellation, with ghost nodes) and ``vm`` (vertex) — driving
    the real Chaste engine in a resident container.

    The protocol matches the authors' TestCellSortingLiteratePaper.hpp: a tissue
    of non-dividing cells relaxes for ``relax_time`` hours, then ``label_fraction``
    of cells are labelled with ``CellLabel``, then the simulation steps on.

    ``ca`` is deliberately unsupported — see :data:`SORTING_MODELS`.

    Outputs
    -------
    fractional_length : overwrite[float]
        The paper's sorting measure: heterotypic boundary length / total shared
        edge length, from Chaste's own ``HeterotypicBoundaryLengthWriter``. 1.0 is
        fully mixed, 0.0 fully sorted. Computed here because the writer emits the
        two lengths separately and does not divide.
    pair_fraction : overwrite[float]
        Heterotypic pairs / total pairs — the same ratio UNWEIGHTED by edge length.
        Diagnostic, not a paper measure: when it equals ``fractional_length`` the
        length weighting is carrying no information, which for ``os`` means the
        tissue has not compressed out of the tangent configuration.
    num_cells, num_labelled : integer
        Real-cell count (ghost nodes excluded) and the labelled subset.
    random_motion : overwrite[string]
        How the paper's RandomMotionForce is supplied: ``"temperature"`` (cp, the
        population temperature), ``"diffusion_force"`` (os/vm, via mainline
        DiffusionForce — pending cbc-03's equivalence check), or ``"unavailable"``
        (vt: DiffusionForce is incompatible with vt's per-step remesh, so vt runs
        deterministically here). Not silent — a consumer can see when noise is off.
    positions, labels : overwrite[...]
        Cell centres and their 0/1 label, aligned 1:1.
    """

    config_schema = {
        "model": {"_type": "string", "_default": "cp"},
        "width": {"_type": "integer", "_default": 20},
        "height": {"_type": "integer", "_default": 20},
        "k_pert": {"_type": "float", "_default": 1.0},
        "relax_time": {"_type": "float", "_default": 10.0},
        "label_fraction": {"_type": "float", "_default": 0.5},
        "ghost_layers": {"_type": "integer", "_default": 20},
        "sampling_multiple": {"_type": "integer", "_default": 100},
        "seed": {"_type": "integer", "_default": 0},
        "timeout": {"_type": "float", "_default": 600.0},
        "start_timeout": {"_type": "float", "_default": 1800.0},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config, core)
        model = self.config["model"]
        if model == "ca":
            raise NotImplementedError(
                "model 'ca' is not supported: the paper's cellular automaton uses "
                "DifferentialAdhesionCaSwitchingUpdateRule, a custom class in "
                "Chaste/CellBasedComparison2017, and PyChaste exposes no "
                "constructible AbstractCaSwitchingUpdateRule base to subclass. "
                f"Use one of {SORTING_MODELS}."
            )
        if model not in SORTING_MODELS:
            raise ValueError(
                f"model must be one of {SORTING_MODELS}, got {model!r}"
            )
        self._session: runtime.ChasteSession | None = None

    def inputs(self):
        return {}

    def outputs(self):
        return {
            "fractional_length": "overwrite[float]",
            "pair_fraction": "overwrite[float]",
            "num_cells": "integer",
            "num_labelled": "integer",
            "random_motion": "overwrite[string]",
            "positions": "overwrite[list[list[float]]]",
            "labels": "overwrite[list[integer]]",
        }

    def initial_state(self):
        return {}

    def _ensure_session(self):
        if self._session is None:
            self._session = runtime.ChasteSession(
                {
                    "model": self.config["model"],
                    "width": self.config["width"],
                    "height": self.config["height"],
                    "k_pert": self.config["k_pert"],
                    "relax_time": self.config["relax_time"],
                    "label_fraction": self.config["label_fraction"],
                    "ghost_layers": self.config["ghost_layers"],
                    "sampling_multiple": self.config["sampling_multiple"],
                    "seed": self.config["seed"],
                },
                server_src=runtime._SORTING_SERVER_SRC,
                run_prefix=f"sort-{self.config['model']}",
                step_timeout=float(self.config["timeout"]),
                start_timeout=float(self.config["start_timeout"]),
            )
            self._session.start()

    def _shape(self, result):
        frac = result.get("fractional_length")
        pair = result.get("pair_fraction")
        return {
            # None until the writer has emitted a row; surfaced as NaN rather
            # than 0.0, which would read as "perfectly sorted"
            "fractional_length": float("nan") if frac is None else float(frac),
            "pair_fraction": float("nan") if pair is None else float(pair),
            "num_cells": int(result.get("num_cells", 0)),
            "num_labelled": int(result.get("num_labelled", 0)),
            "random_motion": str(result.get("random_motion", "unknown")),
            "positions": result.get("positions", []),
            "labels": result.get("labels", []),
        }

    def update(self, state, interval):
        self._ensure_session()
        return self._shape(self._session.step(interval))

    def __del__(self):
        try:
            if self._session is not None:
                self._session.close()
        except Exception:
            pass
