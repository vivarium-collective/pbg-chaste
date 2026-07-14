"""Unit + integration tests for ChasteSimulationProcess.

Shape/config tests run anywhere. Tests that actually drive the Chaste engine
are guarded on Docker + the chaste/pychaste image and *skip* (not fail) when
unavailable, so CI without Docker stays green while a Docker host exercises the
real bridge.
"""

import pytest
from process_bigraph import Composite, allocate_core

from pbg_chaste import CELL_CYCLES, POPULATIONS, ChasteSimulationProcess
from pbg_chaste import runtime

chaste_required = pytest.mark.skipif(
    not runtime.chaste_ready(),
    reason="Docker daemon + chaste/pychaste image required for the real engine",
)


def test_ports_are_dicts():
    core = allocate_core()
    proc = ChasteSimulationProcess(
        config={"population": "mesh", "cell_cycle": "uniform"}, core=core
    )
    assert isinstance(proc.inputs(), dict)
    assert isinstance(proc.outputs(), dict)
    assert "num_cells" in proc.outputs()
    assert "spring_stiffness" in proc.inputs()


def test_rejects_bad_config():
    core = allocate_core()
    with pytest.raises(ValueError):
        ChasteSimulationProcess(config={"population": "nope"}, core=core)
    with pytest.raises(ValueError):
        ChasteSimulationProcess(config={"cell_cycle": "nope"}, core=core)


def test_all_combinations_construct():
    core = allocate_core()
    for pop in POPULATIONS:
        for cyc in CELL_CYCLES:
            if pop == "vertex" and cyc == "delta_notch":
                continue  # documented unsupported combination
            proc = ChasteSimulationProcess(
                config={"population": pop, "cell_cycle": cyc}, core=core
            )
            assert proc.initial_state()["spring_stiffness"] == 0.0


@chaste_required
@pytest.mark.parametrize("population", list(POPULATIONS))
def test_real_step_runs(population):
    """One real Chaste step per population method returns the declared ports."""
    core = allocate_core()
    proc = ChasteSimulationProcess(
        config={"population": population, "cell_cycle": "uniform",
                "width": 2, "height": 2, "timeout": 300.0},
        core=core,
    )
    out = proc.update(proc.initial_state(), interval=1.0)
    assert set(out) >= {"num_cells", "positions", "phase_counts",
                        "mean_delta", "mean_notch"}
    assert isinstance(out["positions"], list)
    # first-step delta is 0 by construction; a real population has >0 cells
    assert proc._prev_cells and proc._prev_cells > 0


def test_vertex_delta_notch_not_implemented():
    core = allocate_core()
    with pytest.raises(NotImplementedError):
        ChasteSimulationProcess(
            config={"population": "vertex", "cell_cycle": "delta_notch"},
            core=core,
        )


@chaste_required
def test_real_delta_notch_has_srn_signal():
    """Delta-Notch on a mesh population produces real sub-cellular signal."""
    core = allocate_core()
    proc = ChasteSimulationProcess(
        config={"population": "mesh", "cell_cycle": "delta_notch",
                "width": 4, "height": 4, "timeout": 300.0},
        core=core,
    )
    out = proc.update(proc.initial_state(), interval=1.0)
    # Delta-Notch SRN should populate a non-zero mean Notch signal
    assert out["mean_notch"] > 0.0
