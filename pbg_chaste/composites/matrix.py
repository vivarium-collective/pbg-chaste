"""Composite generators for Chaste sub-cellular × multi-cellular combinations.

One general generator (`chaste_simulation`) lets the dashboard pick any
population × cell-cycle pairing via its parameter form; a handful of explicit
headline generators showcase distinct combinations for the Composites tab.
Each builds a document around the real :class:`ChasteSimulationProcess`.
"""

from __future__ import annotations

from viva_superpowers.composite_generator import composite_generator

from ..processes import CELL_CYCLES, POPULATIONS

_STORE = ["stores"]


def build_document(
    population="mesh",
    cell_cycle="uniform",
    *,
    width=4,
    height=4,
    interval=1.0,
    seed=0,
):
    """Return a Composite document: ChasteSimulationProcess + stores + emitter."""
    if population not in POPULATIONS:
        raise ValueError(f"population must be one of {POPULATIONS}")
    if cell_cycle not in CELL_CYCLES:
        raise ValueError(f"cell_cycle must be one of {CELL_CYCLES}")
    if population == "vertex" and cell_cycle == "delta_notch":
        raise ValueError(
            "vertex + delta_notch is not supported (needs Chaste's edge-based "
            "SRN); use mesh/node for delta_notch or another cycle for vertex."
        )

    return {
        "chaste": {
            "_type": "process",
            "address": "local:ChasteSimulationProcess",
            "config": {
                "population": population,
                "cell_cycle": cell_cycle,
                "width": int(width),
                "height": int(height),
                "seed": int(seed),
            },
            "interval": float(interval),
            "inputs": {
                "spring_stiffness": ["stores", "spring_stiffness"],
            },
            "outputs": {
                "num_cells": ["stores", "num_cells"],
                "positions": ["stores", "positions"],
                "phase_counts": ["stores", "phase_counts"],
                "mean_delta": ["stores", "mean_delta"],
                "mean_notch": ["stores", "mean_notch"],
            },
        },
        "stores": {
            "spring_stiffness": 0.0,
            "num_cells": 0,
            "positions": [],
            "phase_counts": {},
            "mean_delta": 0.0,
            "mean_notch": 0.0,
        },
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {
                "emit": {
                    "num_cells": "integer",
                    "mean_delta": "float",
                    "mean_notch": "float",
                    "time": "float",
                }
            },
            "inputs": {
                "num_cells": ["stores", "num_cells"],
                "mean_delta": ["stores", "mean_delta"],
                "mean_notch": ["stores", "mean_notch"],
                "time": ["global_time"],
            },
        },
    }


_PARAMS = {
    "population": {
        "type": "string",
        "default": "mesh",
        "description": "Multi-cellular method: mesh | vertex | node",
    },
    "cell_cycle": {
        "type": "string",
        "default": "uniform",
        "description": "Sub-cellular model: uniform | stochastic | tyson_novak | delta_notch",
    },
    "width": {"type": "integer", "default": 4, "description": "Honeycomb width"},
    "height": {"type": "integer", "default": 4, "description": "Honeycomb height"},
    "interval": {"type": "float", "default": 1.0, "description": "Step size (hours)"},
    "seed": {"type": "integer", "default": 0, "description": "RNG seed"},
}


@composite_generator(
    name="chaste_simulation",
    description="Real Chaste OffLatticeSimulation — pick any multi-cellular "
    "population method × sub-cellular cell-cycle model.",
    parameters=_PARAMS,
)
def chaste_simulation(
    core=None,
    *,
    population="mesh",
    cell_cycle="uniform",
    width=4,
    height=4,
    interval=1.0,
    seed=0,
):
    return build_document(
        population, cell_cycle, width=width, height=height,
        interval=interval, seed=seed,
    )


# --- headline combinations (distinct subcellular × multicellular) ----------

@composite_generator(
    name="mesh_uniform",
    description="Mesh-based population + uniform cell cycle (proliferating disc).",
    parameters={"width": _PARAMS["width"], "height": _PARAMS["height"],
                "interval": _PARAMS["interval"]},
)
def mesh_uniform(core=None, *, width=4, height=4, interval=1.0):
    return build_document("mesh", "uniform", width=width, height=height, interval=interval)


@composite_generator(
    name="mesh_delta_notch",
    description="Mesh-based tissue + Delta-Notch reaction network "
    "(Collier lateral-inhibition patterning coupled across Voronoi neighbours).",
    parameters={"width": _PARAMS["width"], "height": _PARAMS["height"],
                "interval": _PARAMS["interval"]},
)
def mesh_delta_notch(core=None, *, width=5, height=5, interval=1.0):
    return build_document("mesh", "delta_notch", width=width, height=height, interval=interval)


@composite_generator(
    name="vertex_tyson_novak",
    description="Vertex-based epithelium + Tyson-Novak ODE cell cycle "
    "(biochemical oscillator gating division in a confluent sheet).",
    parameters={"width": _PARAMS["width"], "height": _PARAMS["height"],
                "interval": _PARAMS["interval"]},
)
def vertex_tyson_novak(core=None, *, width=3, height=3, interval=1.0):
    return build_document("vertex", "tyson_novak", width=width, height=height, interval=interval)


@composite_generator(
    name="node_stochastic",
    description="Node-based (overlapping spheres) population + stochastic cell cycle.",
    parameters={"width": _PARAMS["width"], "height": _PARAMS["height"],
                "interval": _PARAMS["interval"]},
)
def node_stochastic(core=None, *, width=3, height=3, interval=1.0):
    return build_document("node", "stochastic", width=width, height=height, interval=interval)


@composite_generator(
    name="mesh_tyson_novak",
    description="Mesh-based population + Tyson-Novak ODE cell-cycle model.",
    parameters={"width": _PARAMS["width"], "height": _PARAMS["height"],
                "interval": _PARAMS["interval"]},
)
def mesh_tyson_novak(core=None, *, width=3, height=3, interval=1.0):
    return build_document("mesh", "tyson_novak", width=width, height=height, interval=interval)
