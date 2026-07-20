"""Composite generators for the Osborne et al. 2017 cell-sorting study.

Each builds a document around the real :class:`ChasteCellSortingProcess` for one
of the four model classes PyChaste can reach (cp / os / vt / vm). CA is absent —
see :data:`pbg_chaste.processes.SORTING_MODELS`. These back the member study
``cbc-04-cell-sorting-reproduction`` of the cellbased-comparison-2017
investigation, and expose the paper's fractional-boundary-length measure.
"""

from __future__ import annotations

from pbg_superpowers.composite_generator import composite_generator

from ..processes import SORTING_MODELS


def build_sorting_document(
    model="cp",
    *,
    width=20,
    height=20,
    k_pert=1.0,
    relax_time=10.0,
    interval=5.0,
    seed=0,
    ghost_layers=20,
):
    """Composite: ChasteCellSortingProcess + stores + emitter.

    The emitter captures the paper's sorting measure (fractional_length) plus the
    diagnostic pair_fraction and the random_motion provenance flag, so a run's
    trajectory and its noise treatment are both recorded.
    """
    if model not in SORTING_MODELS:
        raise ValueError(f"model must be one of {SORTING_MODELS}, got {model!r}")

    return {
        "sorting": {
            "_type": "process",
            "address": "local:ChasteCellSortingProcess",
            "config": {
                "model": model,
                "width": int(width),
                "height": int(height),
                "k_pert": float(k_pert),
                "relax_time": float(relax_time),
                "ghost_layers": int(ghost_layers),
                "seed": int(seed),
            },
            "interval": float(interval),
            "inputs": {},
            "outputs": {
                "fractional_length": ["stores", "fractional_length"],
                "pair_fraction": ["stores", "pair_fraction"],
                "num_cells": ["stores", "num_cells"],
                "num_labelled": ["stores", "num_labelled"],
                "random_motion": ["stores", "random_motion"],
                "positions": ["stores", "positions"],
                "labels": ["stores", "labels"],
            },
        },
        "stores": {
            "fractional_length": 0.0,
            "pair_fraction": 0.0,
            "num_cells": 0,
            "num_labelled": 0,
            "random_motion": "unknown",
            "positions": [],
            "labels": [],
        },
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {
                "emit": {
                    "fractional_length": "float",
                    "pair_fraction": "float",
                    "num_cells": "integer",
                    "random_motion": "string",
                    "time": "float",
                }
            },
            "inputs": {
                "fractional_length": ["stores", "fractional_length"],
                "pair_fraction": ["stores", "pair_fraction"],
                "num_cells": ["stores", "num_cells"],
                "random_motion": ["stores", "random_motion"],
                "time": ["global_time"],
            },
        },
    }


_SORT_PARAMS = {
    "model": {
        "type": "string",
        "default": "cp",
        "description": "Model class: cp | os | vt | vm (ca unsupported)",
    },
    "width": {"type": "integer", "default": 20, "description": "Cells across (CD)"},
    "height": {"type": "integer", "default": 20, "description": "Cells up (CD)"},
    "k_pert": {"type": "float", "default": 1.0, "description": "Noise multiplier (Fig 3 axis)"},
    "relax_time": {"type": "float", "default": 10.0, "description": "Pre-label relaxation (h)"},
    "interval": {"type": "float", "default": 5.0, "description": "Step size (h)"},
    "seed": {"type": "integer", "default": 0, "description": "RNG seed"},
}


@composite_generator(
    name="cell_sorting",
    description="Cell sorting by differential adhesion (Osborne et al. 2017, "
    "Figs 2-4) — pick a model class cp | os | vt | vm and read out fractional "
    "boundary length. CA is unsupported (custom Ca switching rule).",
    parameters=_SORT_PARAMS,
)
def cell_sorting(core=None, *, model="cp", width=20, height=20, k_pert=1.0,
                 relax_time=10.0, interval=5.0, seed=0, ghost_layers=20, **_):
    return build_sorting_document(
        model, width=width, height=height, k_pert=k_pert,
        relax_time=relax_time, interval=interval, seed=seed, ghost_layers=ghost_layers,
    )


# --- one headline generator per reachable model ----------------------------

@composite_generator(
    name="sorting_potts",
    description="Cell sorting — cellular Potts (CP): OnLatticeSimulation with "
    "volume/surface/differential-adhesion update rules.",
    parameters={k: _SORT_PARAMS[k] for k in ("width", "height", "k_pert", "relax_time", "interval", "seed")},
)
def sorting_potts(core=None, *, width=20, height=20, k_pert=1.0, interval=5.0,
           relax_time=10.0, seed=0, ghost_layers=20, **_):
    return build_sorting_document("cp", width=width, height=height,
                                  k_pert=k_pert, interval=interval,
                                  relax_time=relax_time, seed=seed, ghost_layers=ghost_layers)


@composite_generator(
    name="sorting_overlapping_spheres",
    description="Cell sorting — overlapping spheres (OS): NodeBasedCellPopulation "
    "with differential-adhesion springs + diffusion-force random motion.",
    parameters={k: _SORT_PARAMS[k] for k in ("width", "height", "k_pert", "relax_time", "interval", "seed")},
)
def sorting_overlapping_spheres(core=None, *, width=20, height=20, k_pert=1.0, interval=5.0,
           relax_time=10.0, seed=0, ghost_layers=20, **_):
    return build_sorting_document("os", width=width, height=height,
                                  k_pert=k_pert, interval=interval,
                                  relax_time=relax_time, seed=seed, ghost_layers=ghost_layers)


@composite_generator(
    name="sorting_vertex",
    description="Cell sorting — vertex model (VM): VertexBasedCellPopulation with "
    "Nagai-Honda differential adhesion + diffusion-force random motion.",
    parameters={k: _SORT_PARAMS[k] for k in ("width", "height", "k_pert", "relax_time", "interval", "seed")},
)
def sorting_vertex(core=None, *, width=20, height=20, k_pert=1.0, interval=5.0,
           relax_time=10.0, seed=0, ghost_layers=20, **_):
    return build_sorting_document("vm", width=width, height=height,
                                  k_pert=k_pert, interval=interval,
                                  relax_time=relax_time, seed=seed, ghost_layers=ghost_layers)


@composite_generator(
    name="sorting_voronoi",
    description="Cell sorting — Voronoi tessellation (VT): "
    "MeshBasedCellPopulationWithGhostNodes. NOTE: runs without random motion — "
    "DiffusionForce is incompatible with VT's per-step remesh (see study cbc-03).",
    parameters={k: _SORT_PARAMS[k] for k in ("width", "height", "k_pert", "relax_time", "interval", "seed")},
)
def sorting_voronoi(core=None, *, width=20, height=20, k_pert=1.0, interval=5.0,
           relax_time=10.0, seed=0, ghost_layers=20, **_):
    return build_sorting_document("vt", width=width, height=height,
                                  k_pert=k_pert, interval=interval,
                                  relax_time=relax_time, seed=seed, ghost_layers=ghost_layers)
