"""In-container PyChaste stepping server (runs inside chaste/pychaste).

Held resident in one long-lived container for the lifetime of a
ChasteSimulationProcess. It builds a REAL Chaste OffLatticeSimulation once,
then advances it one interval at a time on command — Chaste resumes correctly
across repeated ``SetEndTime`` + ``Solve`` calls on the same in-memory object,
which is how we step it without the (unavailable) archiver.

Protocol (all files in the bind-mounted /work):
  params.json   -> written by host before start: population, cell_cycle, sizes…
  ready.json    <- written by server once the sim is built (+ initial state)
  cmd_<i>.json  -> host asks for step i: {"interval": float, "stiffness": float}
  out_<i>.json  <- server's genuine observables after step i (or an "error")
  STOP          -> host asks the server to exit

Runs under the container's Python (only ``chaste`` + stdlib available).
Nothing here reimplements Chaste — every number comes from the real solver.

Key correctness notes learned from the live engine:
  * Manually-built cells (needed for the Delta-Notch SRN) segfault unless the
    Python cell-cycle / SRN objects are kept alive — we stash them in ``_KEEP``.
  * ``TearDownNotebookTest`` segfaults after a real run, so we extract state
    and write results BEFORE any teardown, and never tear down mid-session.
"""
import glob
import json
import os
import time
import traceback

import chaste
chaste.init()
import chaste.cell_based as cb
import chaste.mesh as me

WORK = "/work"
_KEEP = []  # keep-alive refs for manually built cell-cycle / SRN objects


def _write(name, obj):
    tmp = os.path.join(WORK, name + ".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, os.path.join(WORK, name))


# --- cell-cycle model -> CellsGenerator class (2D) -------------------------
CYCLE_GENERATOR = {
    "uniform": "CellsGeneratorUniformCellCycleModel_2",
    "stochastic": "CellsGeneratorExponentialG1GenerationalCellCycleModel_2",
    "tyson_novak": "CellsGeneratorTysonNovakCellCycleModel_2",
}


def _make_generated_cells(cycle, n):
    gen_cls = CYCLE_GENERATOR[cycle]
    cg = getattr(cb, gen_cls)()
    return cg.GenerateBasicRandom(n, cb.TransitCellProliferativeType())


def _make_delta_notch_cells(n):
    """Manually build cells carrying a Delta-Notch SRN. Refs kept in _KEEP."""
    p_state = cb.WildTypeCellMutationState()
    p_type = cb.TransitCellProliferativeType()
    _KEEP.append((p_state, p_type))
    cells = []
    for i in range(n):
        cc = cb.UniformG1GenerationalCellCycleModel()
        cc.SetDimension(2)
        srn = cb.DeltaNotchSrnModel()
        srn.SetInitialConditions([1.0, 1.0])
        cell = cb.Cell(p_state, cc, srn)
        cell.SetCellProliferativeType(p_type)
        cell.SetBirthTime(-2.0 * (i % 5))
        _KEEP.append((cc, srn))  # <-- prevents the pybind keep-alive segfault
        cells.append(cell)
    return cells


def build(params):
    population = params["population"]
    cycle = params["cell_cycle"]
    w = int(params.get("width", 4))
    h = int(params.get("height", 4))
    cutoff = float(params.get("spring_cutoff", 1.5))

    cb.SetupNotebookTest()
    try:
        chaste.core.RandomNumberGenerator.Instance().Reseed(int(params.get("seed", 0)))
    except Exception:
        pass

    dn = cycle == "delta_notch"
    if dn and population == "vertex":
        # The non-edge DeltaNotchSrnModel/DeltaNotchTrackingModifier used here
        # couples via Voronoi neighbours (mesh/node). Vertex Delta-Notch needs
        # Chaste's edge-based SRN framework (a DeltaNotchEdgeSrnModel per cell
        # edge). Building those requires enumerating each element's edges via
        # mesh.GetElement(i) — but this PyChaste build does not register the
        # VertexElement<2,2> return type, so element edges are unreachable from
        # Python and the per-edge SRNs cannot be constructed. Blocked upstream.
        raise RuntimeError(
            "vertex + delta_notch requires Chaste's edge-based SRN framework, "
            "which needs per-element edge access (mesh.GetElement); this "
            "PyChaste build does not expose VertexElement to Python, so it is "
            "unsupported. Use population 'mesh' or 'node' for delta_notch."
        )
    # Every Chaste object built here must be kept alive for the lifetime of the
    # simulation: the population/simulator hold C++ pointers into the mesh,
    # cells, generator and modifiers, and if their Python owners are collected
    # the next call aborts with "pure virtual method called". Stash them all.
    gen = None
    if population == "mesh":
        gen = me.HoneycombMeshGenerator(w, h)
        mesh = gen.GetMesh()
        n = mesh.GetNumNodes()
        cells = _make_delta_notch_cells(n) if dn else _make_generated_cells(cycle, n)
        pop = cb.MeshBasedCellPopulation2_2(mesh, cells)
        force = cb.GeneralisedLinearSpringForce2_2()
        modifiers = []
    elif population == "node":
        gen = me.HoneycombMeshGenerator(w, h)
        gm = gen.GetMesh()
        mesh = me.NodesOnlyMesh2()
        mesh.ConstructNodesWithoutMesh(gm, cutoff)
        n = mesh.GetNumNodes()
        cells = _make_delta_notch_cells(n) if dn else _make_generated_cells(cycle, n)
        pop = cb.NodeBasedCellPopulation2(mesh, cells)
        force = cb.GeneralisedLinearSpringForce2_2()
        modifiers = []
    elif population == "vertex":
        gen = me.HoneycombVertexMeshGenerator(w, h)
        mesh = gen.GetMesh()
        n = mesh.GetNumElements()
        cells = _make_delta_notch_cells(n) if dn else _make_generated_cells(cycle, n)
        pop = cb.VertexBasedCellPopulation2(mesh, cells)
        force = cb.NagaiHondaForce2()
        area_mod = cb.SimpleTargetAreaModifier2()
        # Without a growth duration the modifier requires a phase-based cycle
        # model; setting it lets vertex pair with uniform/tyson_novak too.
        try:
            area_mod.SetGrowthDuration(1.0)
        except Exception:
            pass
        modifiers = [area_mod]
    else:
        raise ValueError(f"unknown population: {population!r}")

    if dn:
        modifiers = list(modifiers) + [cb.DeltaNotchTrackingModifier2()]

    sim = cb.OffLatticeSimulation2_2(pop)
    sim.SetOutputDirectory("pbg_chaste_" + population + "_" + cycle)
    sim.SetSamplingTimestepMultiple(int(params.get("sampling_multiple", 12)))
    sim.AddForce(force)
    for m in modifiers:
        sim.AddSimulationModifier(m)

    ctx = {"sim": sim, "pop": pop, "force": force, "mesh": mesh,
           "cells": cells, "gen": gen, "modifiers": modifiers,
           "population": population, "cycle": cycle, "cap": max(2000, n * 60)}
    _KEEP.append(ctx)  # belt-and-braces: keep the whole context alive too
    return ctx


def _apply_stiffness(ctx, stiffness):
    if stiffness is None or stiffness <= 0:
        return
    force = ctx["force"]
    try:
        if ctx["population"] == "vertex":
            force.SetNagaiHondaDeformationEnergyParameter(float(stiffness))
        else:
            force.SetMeinekeSpringStiffness(float(stiffness))
    except Exception:
        pass


def _vertex_polygons():
    """Read the real cell polygons Chaste just wrote to VTK (vertex pops).

    VertexElement<2,2> is not exposed to Python, so element→node connectivity
    is unreachable via the API; instead we parse the newest results_*.vtu the
    population writes, which contains the exact polygon of every cell.
    """
    try:
        import vtk  # available inside chaste/pychaste
    except Exception:
        return []
    root = os.environ.get("CHASTE_TEST_OUTPUT", "/work/out")
    vtus = glob.glob(os.path.join(root, "**", "*.vtu"), recursive=True)
    if not vtus:
        return []
    newest = max(vtus, key=os.path.getmtime)
    reader = vtk.vtkXMLUnstructuredGridReader()
    reader.SetFileName(newest)
    reader.Update()
    grid = reader.GetOutput()
    polys = []
    for ci in range(grid.GetNumberOfCells()):
        ids = grid.GetCell(ci).GetPointIds()
        poly = []
        for k in range(ids.GetNumberOfIds()):
            p = grid.GetPoint(ids.GetId(k))
            poly.append([float(p[0]), float(p[1])])
        if len(poly) >= 3:
            polys.append(poly)
    return polys


def _cell_radius(ctx, i):
    """Per-cell radius for the touching-circle rendering (node/mesh)."""
    if ctx["population"] == "node":
        try:
            return float(ctx["pop"].GetNode(i).GetRadius())
        except Exception:
            return 0.5
    return 0.5  # mesh: nominal, matches the spring rest length


def _extract(ctx):
    pop = ctx["pop"]
    dn = ctx["cycle"] == "delta_notch"
    vertex = ctx["population"] == "vertex"
    target = int(pop.GetNumRealCells())
    positions, phases, radii = [], {}, []
    per_cell_delta = []  # aligned 1:1 with positions (for spatial colouring)
    deltas, notches = [], []
    found, i, cap = 0, 0, ctx["cap"]
    while found < target and i < cap:
        if pop.IsCellAttachedToLocationIndex(i):
            cell = pop.GetCellUsingLocationIndex(i)
            found += 1
            try:
                loc = pop.GetLocationOfCellCentre(cell)
            except Exception:
                i += 1
                continue
            positions.append([float(loc[0]), float(loc[1])])
            radii.append(_cell_radius(ctx, i))
            d = 0.0
            if dn:
                try:
                    d = float(cell.GetCellData().GetItem("delta"))
                    deltas.append(d)
                    notches.append(float(cell.GetCellData().GetItem("notch")))
                except Exception:
                    d = 0.0
            per_cell_delta.append(d)
            try:
                ph = str(cell.GetCellCycleModel().GetCurrentCellCyclePhase())
                phases[ph] = phases.get(ph, 0.0) + 1.0
            except Exception:
                pass
        i += 1
    out = {
        "num_cells": target,
        "positions": positions,
        "radii": radii,
        "polygons": _vertex_polygons() if vertex else [],
        "per_cell_delta": per_cell_delta,
        "phase_counts": phases,
        "mean_delta": sum(deltas) / len(deltas) if deltas else 0.0,
        "mean_notch": sum(notches) / len(notches) if notches else 0.0,
    }
    return out


def main():
    with open(os.path.join(WORK, "params.json")) as f:
        params = json.load(f)
    try:
        ctx = build(params)
        t = 0.0
        # Cell positions / phases are only valid AFTER the first Solve() sets up
        # the population (calling them earlier aborts with "pure virtual method
        # called"), so the ready state reports only the safe cell count.
        state = {"num_cells": int(ctx["pop"].GetNumRealCells()),
                 "positions": [], "phase_counts": {},
                 "mean_delta": 0.0, "mean_notch": 0.0, "time": 0.0}
        _write("ready.json", {"ok": True, "state": state})
    except Exception as e:
        _write("ready.json", {"ok": False, "error": f"{type(e).__name__}: {e}",
                              "tb": traceback.format_exc()[-2000:]})
        return

    i = 1
    idle = 0.0
    while True:
        if os.path.exists(os.path.join(WORK, "STOP")):
            break
        cmd_path = os.path.join(WORK, f"cmd_{i}.json")
        if not os.path.exists(cmd_path):
            time.sleep(0.05)
            idle += 0.05
            if idle > 3600:  # safety: no commands for an hour -> exit
                break
            continue
        idle = 0.0
        try:
            with open(cmd_path) as f:
                cmd = json.load(f)
            _apply_stiffness(ctx, cmd.get("stiffness"))
            t += float(cmd["interval"])
            ctx["sim"].SetEndTime(t)
            ctx["sim"].Solve()
            out = _extract(ctx)
            out["time"] = t
            _write(f"out_{i}.json", {"ok": True, "state": out})
        except Exception as e:
            _write(f"out_{i}.json", {"ok": False,
                                    "error": f"{type(e).__name__}: {e}",
                                    "tb": traceback.format_exc()[-2000:]})
        i += 1


if __name__ == "__main__":
    main()
