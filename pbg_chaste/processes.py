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
