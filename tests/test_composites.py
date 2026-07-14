"""Composite-generator registration + assembly tests (no Docker needed)."""

import pytest
from process_bigraph import Composite, allocate_core

from pbg_chaste.composites import build_document

HEADLINE = ["mesh_uniform", "mesh_delta_notch", "vertex_tyson_novak",
            "node_stochastic", "mesh_tyson_novak", "chaste_simulation"]


@pytest.mark.parametrize("name", HEADLINE)
def test_generator_is_registered(name):
    from pbg_superpowers.composite_generator import _REGISTRY
    matches = [eid for eid in _REGISTRY if eid.endswith(f".{name}")]
    assert matches, f"{name} missing; have {sorted(_REGISTRY)[:8]}"


def test_generators_discoverable():
    from pbg_superpowers.composite_generator import discover_generators
    gens = discover_generators()
    assert any("pbg_chaste" in g for g in gens), "no pbg_chaste generators discovered"


def test_build_document_shape():
    doc = build_document("mesh", "delta_notch", width=3, height=3)
    assert set(doc) == {"chaste", "stores", "emitter"}
    assert doc["chaste"]["address"] == "local:ChasteSimulationProcess"
    assert doc["chaste"]["config"]["population"] == "mesh"
    assert doc["chaste"]["config"]["cell_cycle"] == "delta_notch"


def test_vertex_delta_notch_rejected():
    import pytest
    with pytest.raises(ValueError):
        build_document("vertex", "delta_notch")


def test_document_assembles_in_composite():
    core = allocate_core()
    doc = build_document("mesh", "uniform", width=2, height=2)
    sim = Composite({"state": doc}, core=core)  # schema reconciliation
    assert sim is not None


def test_build_document_rejects_bad_args():
    with pytest.raises(ValueError):
        build_document("nope", "uniform")
    with pytest.raises(ValueError):
        build_document("mesh", "nope")
