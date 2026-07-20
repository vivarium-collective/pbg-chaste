"""In-container PyChaste server for the Osborne et al. 2017 cell-sorting study.

Runs inside chaste/pychaste, held resident by a ChasteSession exactly like
``_chaste_server.py``. It reproduces the paper's differential-adhesion protocol
for the four model classes PyChaste can reach:

  cp  cellular Potts        PottsBasedCellPopulation      + OnLatticeSimulation
  os  overlapping spheres   NodeBasedCellPopulation       + OffLatticeSimulation
  vt  Voronoi tessellation  MeshBasedCellPopulationWithGhostNodes + OffLattice
  vm  vertex model          VertexBasedCellPopulation     + OffLatticeSimulation

CA is absent by design: its DifferentialAdhesionCaSwitchingUpdateRule is custom
to the paper's repo and AbstractCaSwitchingUpdateRule_2 exposes no constructor
to subclass from Python. See the investigation's probes/ for the evidence.

Protocol (Osborne et al. 2017, TestCellSortingLiteratePaper.hpp):
  1. build a width x height tissue of NON-DIVIDING differentiated cells
  2. relax to steady state for ``relax_time`` hours (default 10)
  3. label a ``label_fraction`` (default 0.5) subset with CellLabel
  4. step on command; heterotypic boundary length is emitted throughout

Why relaxation matters, and why it is not optional: on the pristine honeycomb
lattice, cells sit at spacing 1.0 with radius 0.5 — exactly TANGENT. The
HeterotypicBoundaryLengthWriter derives an OS shared edge from Heron's formula
on the two radii and their separation, so a tangent pair yields a zero-length
chord. Before relaxation the OS lengths are float noise (~1e-7) and their ratio
collapses to the pair-count ratio, carrying no geometric information. Only
compression under the spring force creates genuine overlap. Sampling OS before
relaxation is therefore meaningless, not merely noisy.

Nothing here reimplements Chaste science — every number comes from the solver.
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
_KEEP = []  # keep-alive refs; without these the next call aborts with
            # "pure virtual method called" (see _chaste_server.py)

MODELS = ("cp", "os", "vt", "vm")


def _write(name, obj):
    tmp = os.path.join(WORK, name + ".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, os.path.join(WORK, name))


def _make_cells(n):
    """Non-dividing cells: the paper's sorting sims assert 0 births/deaths."""
    cg = cb.CellsGenerator["UniformG1GenerationalCellCycleModel", "2"]()
    return cg.GenerateBasicRandom(n, cb.DifferentiatedCellProliferativeType())


# --- per-model builders ----------------------------------------------------
# Parameters are taken from the authors' TestCellSortingLiteratePaper.hpp, not
# from the paper's tables, where the two differ.

def _build_cp(p):
    w, h = p["width"], p["height"]
    # PottsMeshGenerator(nodesX, elementsX, elementWidth, nodesY, elementsY, elementHeight)
    gen = me.PottsMeshGenerator["2"](12 * w, w, 4, 12 * h, h, 4)
    mesh = gen.GetMesh()
    cells = _make_cells(mesh.GetNumElements())
    pop = cb.PottsBasedCellPopulation["2"](mesh, cells)
    pop.SetTemperature(p["temperature"] * p["k_pert"])
    sim = cb.OnLatticeSimulation["2"](pop)
    sim.SetDt(p["dt"])
    r1 = cb.VolumeConstraintPottsUpdateRule["2"]()
    r1.SetMatureCellTargetVolume(16)
    r1.SetDeformationEnergyParameter(0.1)
    r2 = cb.SurfaceAreaConstraintPottsUpdateRule["2"]()
    r2.SetMatureCellTargetSurfaceArea(16)
    r2.SetDeformationEnergyParameter(0.01)
    r3 = cb.DifferentialAdhesionPottsUpdateRule["2"]()
    r3.SetLabelledCellLabelledCellAdhesionEnergyParameter(0.1)
    r3.SetLabelledCellCellAdhesionEnergyParameter(0.5)
    r3.SetCellCellAdhesionEnergyParameter(0.1)
    r3.SetCellBoundaryAdhesionEnergyParameter(0.2)
    r3.SetLabelledCellBoundaryAdhesionEnergyParameter(1.0)
    for r in (r1, r2, r3):
        sim.AddUpdateRule(r)
    _KEEP.extend([gen, mesh, r1, r2, r3])
    return sim, pop, mesh, None


def _diff_adhesion_spring(cutoff=None):
    f = cb.DifferentialAdhesionGeneralisedLinearSpringForce["2", "2"]()
    f.SetMeinekeSpringStiffness(50.0)
    f.SetHomotypicLabelledSpringConstantMultiplier(1.0)
    f.SetHeterotypicSpringConstantMultiplier(0.1)
    if cutoff is not None:
        f.SetCutOffLength(cutoff)
    return f


def _build_os(p):
    gen = me.HoneycombMeshGenerator(p["width"], p["height"], 0)
    gm = gen.GetMesh()
    mesh = me.NodesOnlyMesh["2"]()
    mesh.ConstructNodesWithoutMesh(gm, 2.5)  # r_max = 2.5 (Table 2)
    cells = _make_cells(mesh.GetNumNodes())
    pop = cb.NodeBasedCellPopulation["2"](mesh, cells)
    sim = cb.OffLatticeSimulation["2", "2"](pop)
    sim.SetDt(p["dt"])
    f = _diff_adhesion_spring(cutoff=2.5)
    sim.AddForce(f)
    _KEEP.extend([gen, gm, mesh, f])
    return sim, pop, mesh, None


def _build_vt(p):
    ghosts = p.get("ghost_layers", 20)
    gen = me.HoneycombMeshGenerator(p["width"], p["height"], ghosts)
    mesh = gen.GetMesh()
    loc = gen.GetCellLocationIndices()  # real-cell indices; the rest are ghosts
    cells = _make_cells(len(loc))
    pop = cb.MeshBasedCellPopulationWithGhostNodes["2"](mesh, cells, loc)
    sim = cb.OffLatticeSimulation["2", "2"](pop)
    sim.SetDt(p["dt"])
    f = _diff_adhesion_spring(cutoff=None)  # authors leave the default 1.5
    sim.AddForce(f)
    _KEEP.extend([gen, mesh, f])
    return sim, pop, mesh, list(loc)


def _build_vm(p):
    gen = me.HoneycombVertexMeshGenerator(p["width"], p["height"])
    mesh = gen.GetMesh()
    mesh.SetCellRearrangementThreshold(0.1)  # l_r = 0.1 CD (Table 1)
    cells = _make_cells(mesh.GetNumElements())
    pop = cb.VertexBasedCellPopulation["2"](mesh, cells)
    sim = cb.OffLatticeSimulation["2", "2"](pop)
    sim.SetDt(p["dt"])
    f = cb.NagaiHondaDifferentialAdhesionForce["2"]()
    f.SetNagaiHondaDeformationEnergyParameter(50.0)
    f.SetNagaiHondaMembraneSurfaceEnergyParameter(1.0)
    f.SetNagaiHondaCellCellAdhesionEnergyParameter(1.0)
    f.SetNagaiHondaLabelledCellCellAdhesionEnergyParameter(2.0)
    f.SetNagaiHondaLabelledCellLabelledCellAdhesionEnergyParameter(1.0)
    f.SetNagaiHondaCellBoundaryAdhesionEnergyParameter(10.0)
    f.SetNagaiHondaLabelledCellBoundaryAdhesionEnergyParameter(20.0)
    sim.AddForce(f)
    _KEEP.append(f)
    # The authors set "target area" per cell BY HAND and deliberately do NOT
    # attach SimpleTargetAreaModifier — their source notes the modifiers
    # misbehave by producing very long G1 phases. Reproduce their choice.
    for i in range(mesh.GetNumElements()):
        if pop.IsCellAttachedToLocationIndex(i):
            pop.GetCellUsingLocationIndex(i).GetCellData().SetItem("target area", 1.0)
    _KEEP.extend([gen, mesh])
    return sim, pop, mesh, None


BUILDERS = {"cp": _build_cp, "os": _build_os, "vt": _build_vt, "vm": _build_vm}

#: Baseline noise per model (Table 2). CA/CP use temperature T; OS/VT/VM use
#: the perturbation magnitude xi. Multiplied by k_pert.
BASE_NOISE = {"cp": 0.2, "os": 0.05, "vt": 0.1, "vm": 0.1}

#: DiffusionForce.GetDiffusionScalingConstant() = C * AbsoluteTemperature /
#: Viscosity. C measured from the binding at T=1, Viscosity=1 (probe_fix.py).
#: Lets us invert to a target scaling, since no direct scaling setter is bound.
DIFFUSION_SCALING_C = 2.636845e-08

#: Models whose random-motion term (paper: RandomMotionForce) can be supplied by
#: mainline DiffusionForce. VT is EXCLUDED: MeshBasedCellPopulation re-triangulates
#: every timestep, creating fresh nodes without radius attributes, and
#: DiffusionForce divides its force by node radius (throwing on radius 0). The
#: paper's RandomMotionForce has no radius division and so is immune. This is a
#: mechanical refutation of the DiffusionForce substitution for VT specifically —
#: see study cbc-03. VT therefore runs here with NO random motion, flagged in the
#: emitted state as random_motion="unavailable".
RANDOM_MOTION_VIA_DIFFUSION = ("os", "vm")


def _add_random_motion(sim, pop, mesh, model, xi):
    """The paper's RandomMotionForce, via mainline DiffusionForce.

    RandomMotionForce is custom to the authors' repo and cannot be ported as a
    Python subclass (the C++ -> Python trampoline fails marshalling the
    population argument). DiffusionForce is the same expression:

        RandomMotionForce:  F = sqrt(2*D*dt)/dt * xi
        DiffusionForce:     F = nu * sqrt(2*(scaling/radius)*dt)/dt * xi

    so they coincide when nu == 1 (Chaste's default damping, and the paper's
    eta = 1.0) and scaling == D * radius. cbc-03 TESTS this equivalence against
    the authors' C++ output; until it passes, treat OS/VT/VM noise as unverified.

    DiffusionForce throws on radius 0 — the default for vertex meshes — so radii
    are set explicitly here.

    DiffusionForce has no direct scaling setter; the scaling constant is derived
    as C * AbsoluteTemperature / Viscosity, with C = 2.636845e-8 measured from the
    binding (probe_fix.py). We want scaling = xi * radius so that the per-node
    diffusion constant scaling/radius equals the paper's movement parameter xi;
    with Viscosity = 1 that means AbsoluteTemperature = xi * radius / C.
    """
    if xi <= 0:
        return None
    radius = 0.5
    # DiffusionForce iterates rGetMesh() nodes and divides the force by each
    # node's radius, throwing on radius 0. The set of nodes it touches is the
    # MESH's nodes — for VT that includes ghost nodes, for VM the polygon
    # vertices — not just pop.GetNode(i). On a MutableMesh / vertex mesh the
    # nodes carry no radius attribute at all, so GetRadius() itself throws;
    # SetRadius() must be called unconditionally to construct the attribute.
    # With every node at the same radius, scaling/radius is the same constant xi
    # on every node, which is exactly the paper's uniform RandomMotionForce.
    for i in range(mesh.GetNumNodes()):
        try:
            mesh.GetNode(i).SetRadius(radius)
        except Exception:
            pass
    f = cb.DiffusionForce["2"]()
    f.SetViscosity(1.0)
    f.SetAbsoluteTemperature(xi * radius / DIFFUSION_SCALING_C)
    sim.AddForce(f)
    _KEEP.append(f)
    return f


def _real_cell_indices(ctx):
    """Location indices holding a REAL cell.

    For VT the mesh also carries ghost nodes, which are not cells; counting
    every location index would silently inflate every population-level number.
    """
    pop = ctx["pop"]
    if ctx["loc"] is not None:
        return [i for i in ctx["loc"] if pop.IsCellAttachedToLocationIndex(i)]
    out, i, found = [], 0, 0
    target = int(pop.GetNumRealCells())
    cap = ctx["cap"]
    while found < target and i < cap:
        if pop.IsCellAttachedToLocationIndex(i):
            out.append(i)
            found += 1
        i += 1
    return out


def _label_cells(ctx, fraction):
    """The authors' RandomlyLabelCells(..., 0.5), applied AFTER relaxation.

    Records the labelled cells' unique ids in ctx["labelled_ids"]. CellLabel is a
    CellProperty and PyChaste binds no read-back for it (HasCellProperty and the
    property collection are unreachable from Python), so we track membership by
    the stable cell id — cells neither divide nor die in the sorting protocol.
    The label still drives the C++ physics; this is only for reporting labels.
    """
    pop = ctx["pop"]
    p_label = cb.CellLabel()
    _KEEP.append(p_label)
    idx = _real_cell_indices(ctx)
    rng = chaste.core.RandomNumberGenerator.Instance()
    # shuffle so exactly round(fraction*n) cells are labelled, rather than
    # each cell being labelled independently (which only gives 50% on average)
    order = list(idx)
    for i in range(len(order) - 1, 0, -1):
        j = int(rng.ranf() * (i + 1))
        j = min(max(j, 0), i)
        order[i], order[j] = order[j], order[i]
    k = int(round(fraction * len(order)))
    labelled_ids = set()
    for i in order[:k]:
        cell = pop.GetCellUsingLocationIndex(i)
        cell.AddCellProperty(p_label)
        labelled_ids.add(int(cell.GetCellId()))
    ctx["labelled_ids"] = labelled_ids
    return k


def _read_het(outdir):
    """Latest row of heterotypicboundary.dat, across all results_from_time_* dirs.

    Columns: time, heterotypic_length, total_length, num_heterotypic_pairs,
    total_pairs. The writer does NOT divide — the paper's fractional boundary
    length is column 1 / column 2, computed here.
    """
    root = os.environ.get("CHASTE_TEST_OUTPUT", "/work/out")
    hits = glob.glob(os.path.join(root, outdir, "**", "heterotypicboundary.dat"),
                     recursive=True)
    best = None
    for path in hits:
        try:
            with open(path) as f:
                for line in f:
                    cols = line.split()
                    if len(cols) < 5:
                        continue
                    row = [float(c) for c in cols[:5]]
                    if best is None or row[0] > best[0]:
                        best = row
        except Exception:
            continue
    if best is None:
        return None
    t, het, total, het_pairs, total_pairs = best
    return {
        "time": t,
        "heterotypic_length": het,
        "total_length": total,
        "num_heterotypic_pairs": int(het_pairs),
        "total_pairs": int(total_pairs),
        "fractional_length": (het / total) if total > 0 else None,
        "pair_fraction": (het_pairs / total_pairs) if total_pairs > 0 else None,
    }


def build(params):
    model = params["model"]
    if model not in BUILDERS:
        raise ValueError(
            f"unknown model {model!r}; expected one of {MODELS}. "
            "CA is unsupported: its DifferentialAdhesionCaSwitchingUpdateRule is "
            "custom to the paper's repo and has no constructible PyChaste base."
        )
    p = {
        "width": int(params.get("width", 20)),
        "height": int(params.get("height", 20)),
        "dt": float(params.get("dt", 0.01 if model == "cp" else 1.0 / 200.0)),
        "k_pert": float(params.get("k_pert", 1.0)),
        "temperature": float(params.get("temperature", BASE_NOISE["cp"])),
        "ghost_layers": int(params.get("ghost_layers", 20)),
    }
    cb.SetupNotebookTest()  # must precede cell generation (SimulationTime)
    try:
        chaste.core.RandomNumberGenerator.Instance().Reseed(int(params.get("seed", 0)))
    except Exception:
        pass

    sim, pop, mesh, loc = BUILDERS[model](p)
    outdir = "pbg_sort_" + model
    sim.SetOutputDirectory(outdir)
    sim.SetSamplingTimestepMultiple(int(params.get("sampling_multiple", 100)))
    writer = cb.HeterotypicBoundaryLengthWriter["2", "2"]()
    pop.AddPopulationWriter(writer)
    _KEEP.append(writer)

    ctx = {"sim": sim, "pop": pop, "mesh": mesh, "loc": loc, "model": model,
           "outdir": outdir, "params": p, "labelled": 0, "labelled_yet": False,
           "labelled_ids": set(),
           "cap": max(4000, int(pop.GetNumRealCells()) * 60)}
    _KEEP.append(ctx)

    # noise is applied to the off-lattice models as a force; for CP it is the
    # population temperature, already set in the builder
    if model == "cp":
        ctx["random_motion"] = "temperature"  # T * k_pert, set in _build_cp
    elif model in RANDOM_MOTION_VIA_DIFFUSION:
        xi = BASE_NOISE[model] * p["k_pert"]
        _add_random_motion(sim, pop, mesh, model, xi)
        ctx["random_motion"] = "diffusion_force"
    else:
        # VT: no mainline substitute for RandomMotionForce (see the module
        # constant). Runs deterministically; cbc-03 owns the fix.
        ctx["random_motion"] = "unavailable"
    return ctx


def _extract(ctx):
    pop = ctx["pop"]
    het = _read_het(ctx["outdir"])
    idx = _real_cell_indices(ctx)
    labelled_ids = ctx.get("labelled_ids", set())
    positions, labels = [], []
    for i in idx:
        try:
            cell = pop.GetCellUsingLocationIndex(i)
            loc = pop.GetLocationOfCellCentre(cell)
        except Exception:
            continue
        positions.append([float(loc[0]), float(loc[1])])
        labels.append(1 if int(cell.GetCellId()) in labelled_ids else 0)
    out = {
        "num_cells": int(pop.GetNumRealCells()),
        "num_labelled": int(ctx["labelled"]),
        "random_motion": ctx.get("random_motion", "unknown"),
        "positions": positions,
        "labels": labels,
        "fractional_length": (het or {}).get("fractional_length"),
        "heterotypic_length": (het or {}).get("heterotypic_length"),
        "total_length": (het or {}).get("total_length"),
        "num_heterotypic_pairs": (het or {}).get("num_heterotypic_pairs"),
        "total_pairs": (het or {}).get("total_pairs"),
        "pair_fraction": (het or {}).get("pair_fraction"),
    }
    return out


def main():
    with open(os.path.join(WORK, "params.json")) as f:
        params = json.load(f)
    try:
        ctx = build(params)
        relax = float(params.get("relax_time", 10.0))
        t = 0.0
        # Phase 1: relax to steady state BEFORE labelling. Not cosmetic — see
        # the module docstring on OS tangency.
        if relax > 0:
            t = relax
            ctx["sim"].SetEndTime(t)
            ctx["sim"].Solve()
        # Phase 2: label, exactly as the authors do at t = relax
        ctx["labelled"] = _label_cells(ctx, float(params.get("label_fraction", 0.5)))
        ctx["labelled_yet"] = True
        ctx["t"] = t
        state = _extract(ctx)
        state["time"] = t
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
            if idle > 3600:
                break
            continue
        idle = 0.0
        try:
            with open(cmd_path) as f:
                cmd = json.load(f)
            ctx["t"] += float(cmd["interval"])
            ctx["sim"].SetEndTime(ctx["t"])
            ctx["sim"].Solve()
            out = _extract(ctx)
            out["time"] = ctx["t"]
            _write(f"out_{i}.json", {"ok": True, "state": out})
        except Exception as e:
            _write(f"out_{i}.json", {"ok": False,
                                    "error": f"{type(e).__name__}: {e}",
                                    "tb": traceback.format_exc()[-2000:]})
        i += 1


if __name__ == "__main__":
    main()
