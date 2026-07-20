"""Tests for ChasteCellSortingProcess (Osborne et al. 2017, Figs 2-4).

Shape/config tests run anywhere. Tests that drive the real Chaste engine are
Docker-gated and skip when the image is unavailable. The real-engine tests use a
deliberately small tissue and a short relaxation — they assert the PROTOCOL is
wired correctly (on-lattice dispatch, ghost exclusion, labelling), not the
paper's science, which needs 20x20 to t=100 and belongs to cbc-04.
"""

import math

import pytest
from process_bigraph import allocate_core

from pbg_chaste import SORTING_MODELS, ChasteCellSortingProcess
from pbg_chaste import runtime

chaste_required = pytest.mark.skipif(
    not runtime.chaste_ready(),
    reason="Docker daemon + chaste/pychaste image required for the real engine",
)


def _proc(core, **cfg):
    base = {"width": 4, "height": 4, "relax_time": 0.05, "ghost_layers": 2,
            "sampling_multiple": 1, "timeout": 900.0, "start_timeout": 1800.0}
    base.update(cfg)
    return ChasteCellSortingProcess(config=base, core=core)


# --- config / shape --------------------------------------------------------

def test_ports_declared():
    proc = _proc(allocate_core(), model="cp")
    assert proc.inputs() == {}
    outs = proc.outputs()
    assert "fractional_length" in outs
    assert "pair_fraction" in outs
    assert "num_cells" in outs and "num_labelled" in outs


def test_all_reachable_models_construct():
    core = allocate_core()
    for model in SORTING_MODELS:
        assert _proc(core, model=model).config["model"] == model


def test_ca_raises_with_actionable_reason():
    """CA must fail loudly and explain why, not be silently absent."""
    with pytest.raises(NotImplementedError) as e:
        _proc(allocate_core(), model="ca")
    msg = str(e.value)
    assert "DifferentialAdhesionCaSwitchingUpdateRule" in msg
    assert "ca" not in SORTING_MODELS


def test_rejects_unknown_model():
    with pytest.raises(ValueError):
        _proc(allocate_core(), model="nope")


def test_missing_metric_is_nan_not_zero():
    """A missing writer row must not read as 'perfectly sorted'."""
    proc = _proc(allocate_core(), model="cp")
    shaped = proc._shape({"fractional_length": None, "pair_fraction": None,
                          "num_cells": 4, "num_labelled": 2})
    assert math.isnan(shaped["fractional_length"])
    assert math.isnan(shaped["pair_fraction"])
    assert shaped["num_cells"] == 4


# --- real engine -----------------------------------------------------------

@chaste_required
def test_cp_runs_onlattice_and_emits_boundary():
    """cbc-02 AC: onlattice-populations-run-and-emit-heterotypic-boundary.

    CP is the strictest test of the new dispatch seam — the only model needing
    OnLatticeSimulation AND update rules AND labels — and needs no substitute
    classes, so a failure here is unambiguously a wrapper bug.
    """
    proc = _proc(allocate_core(), model="cp")
    out = proc.update({}, interval=0.05)
    assert out["num_cells"] > 0
    frac = out["fractional_length"]
    assert not math.isnan(frac), "writer emitted no row -> boundary length missing"
    assert 0.0 <= frac <= 1.0


@chaste_required
def test_vt_excludes_ghost_nodes_from_cell_count():
    """cbc-02 AC: ghost-nodes-excluded-from-cell-counts.

    A 4x4 tissue with 2 ghost layers must report exactly 16 real cells. If ghost
    nodes leaked into the count it would be substantially higher — the failure
    mode is silent inflation of every population-level number.
    """
    proc = _proc(allocate_core(), model="vt", width=4, height=4, ghost_layers=2)
    out = proc.update({}, interval=0.05)
    assert out["num_cells"] == 16, (
        f"expected 16 real cells, got {out['num_cells']} — ghost nodes are "
        "likely being counted as cells"
    )
    assert len(out["positions"]) == 16


@chaste_required
@pytest.mark.parametrize("model", list(SORTING_MODELS))
def test_labelling_splits_population_in_half(model):
    """cbc-02 AC: cell-labelling-splits-population-in-half.

    Labelling is applied AFTER relaxation, by shuffling real-cell indices and
    taking exactly half — so this is exact, not binomial.
    """
    proc = _proc(allocate_core(), model=model)
    out = proc.update({}, interval=0.05)
    n, k = out["num_cells"], out["num_labelled"]
    assert n > 0
    assert k == round(0.5 * n), f"{model}: labelled {k} of {n}, expected {round(0.5*n)}"
    assert sum(out["labels"]) == k
