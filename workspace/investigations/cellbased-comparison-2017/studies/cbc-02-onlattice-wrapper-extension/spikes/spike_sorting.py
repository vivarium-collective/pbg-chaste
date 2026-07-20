"""Spike: build the Osborne 2017 cell-sorting setup for CP/OS/VT/VM in PyChaste.

Deliberately small (SCALE cells per side, short t) — this proves the CONFIG is
constructible and that HeterotypicBoundaryLengthWriter emits, not the science.
Paper geometry is 20x20 to t=100.
"""
import os, sys, glob, traceback
import chaste
chaste.init()
import chaste.cell_based as cb
import chaste.mesh as me

SCALE = int(os.environ.get("SPIKE_SCALE", "5"))
END = float(os.environ.get("SPIKE_END", "0.2"))
OUT = os.environ.get("CHASTE_TEST_OUTPUT", "/work/out")
_KEEP = []


_LABELLED = {}


def cells_for(n, label_type=None):
    """Non-dividing cells, as the paper's sorting sims use.

    GenerateBasicRandom returns a plain Python list of Cell, so we label here.
    NOTE: the paper labels at t=10 after relaxing to steady state, not at
    construction. This spike labels up-front — enough to prove the differential
    -adhesion config is constructible and that the writer emits. The real
    protocol needs a mid-run label pass over GetCellUsingLocationIndex.
    """
    cg = cb.CellsGenerator["UniformG1GenerationalCellCycleModel", "2"]()
    cells = cg.GenerateBasicRandom(n, cb.DifferentiatedCellProliferativeType())
    p_label = cb.CellLabel()
    _KEEP.append(p_label)
    rng = chaste.core.RandomNumberGenerator.Instance()
    k = 0
    for cell in cells:
        if rng.ranf() < 0.5:
            cell.AddCellProperty(p_label)
            k += 1
    _LABELLED["n"] = k
    return cells


def build_cp():
    gen = me.PottsMeshGenerator["2"](12 * SCALE, SCALE, 4, 12 * SCALE, SCALE, 4)
    mesh = gen.GetMesh()
    cells = cells_for(mesh.GetNumElements())
    pop = cb.PottsBasedCellPopulation["2"](mesh, cells)
    pop.SetTemperature(0.2)
    sim = cb.OnLatticeSimulation["2"](pop)
    sim.SetDt(0.01)
    sim.SetSamplingTimestepMultiple(10)
    r1 = cb.VolumeConstraintPottsUpdateRule["2"]()
    r1.SetMatureCellTargetVolume(16); r1.SetDeformationEnergyParameter(0.1)
    r2 = cb.SurfaceAreaConstraintPottsUpdateRule["2"]()
    r2.SetMatureCellTargetSurfaceArea(16); r2.SetDeformationEnergyParameter(0.01)
    r3 = cb.DifferentialAdhesionPottsUpdateRule["2"]()
    r3.SetLabelledCellLabelledCellAdhesionEnergyParameter(0.1)
    r3.SetLabelledCellCellAdhesionEnergyParameter(0.5)
    r3.SetCellCellAdhesionEnergyParameter(0.1)
    r3.SetCellBoundaryAdhesionEnergyParameter(0.2)
    r3.SetLabelledCellBoundaryAdhesionEnergyParameter(1.0)
    for r in (r1, r2, r3):
        sim.AddUpdateRule(r)
    _KEEP.extend([gen, mesh, pop, r1, r2, r3, sim])
    return sim, pop


def build_os():
    gen = me.HoneycombMeshGenerator(SCALE, SCALE, 0)
    gm = gen.GetMesh()
    mesh = me.NodesOnlyMesh["2"]()
    mesh.ConstructNodesWithoutMesh(gm, 2.5)
    cells = cells_for(mesh.GetNumNodes())
    pop = cb.NodeBasedCellPopulation["2"](mesh, cells)
    sim = cb.OffLatticeSimulation["2", "2"](pop)
    sim.SetDt(1.0 / 200.0)
    sim.SetSamplingTimestepMultiple(200)
    f = cb.DifferentialAdhesionGeneralisedLinearSpringForce["2", "2"]()
    f.SetMeinekeSpringStiffness(50.0)
    f.SetHomotypicLabelledSpringConstantMultiplier(1.0)
    f.SetHeterotypicSpringConstantMultiplier(0.1)
    f.SetCutOffLength(2.5)
    sim.AddForce(f)
    _KEEP.extend([gen, gm, mesh, pop, f, sim])
    return sim, pop


def build_vt():
    gen = me.HoneycombMeshGenerator(SCALE, SCALE, SCALE)  # ghost layers
    mesh = gen.GetMesh()
    loc = gen.GetCellLocationIndices()
    cells = cells_for(len(loc))
    pop = cb.MeshBasedCellPopulationWithGhostNodes["2"](mesh, cells, loc)
    sim = cb.OffLatticeSimulation["2", "2"](pop)
    sim.SetDt(1.0 / 200.0)
    sim.SetSamplingTimestepMultiple(200)
    f = cb.DifferentialAdhesionGeneralisedLinearSpringForce["2", "2"]()
    f.SetMeinekeSpringStiffness(50.0)
    f.SetHomotypicLabelledSpringConstantMultiplier(1.0)
    f.SetHeterotypicSpringConstantMultiplier(0.1)
    sim.AddForce(f)
    _KEEP.extend([gen, mesh, pop, f, sim])
    return sim, pop


def build_vm():
    gen = me.HoneycombVertexMeshGenerator(SCALE, SCALE)
    mesh = gen.GetMesh()
    mesh.SetCellRearrangementThreshold(0.1)
    cells = cells_for(mesh.GetNumElements())
    pop = cb.VertexBasedCellPopulation["2"](mesh, cells)
    sim = cb.OffLatticeSimulation["2", "2"](pop)
    sim.SetDt(1.0 / 200.0)
    sim.SetSamplingTimestepMultiple(200)
    f = cb.NagaiHondaDifferentialAdhesionForce["2"]()
    f.SetNagaiHondaDeformationEnergyParameter(50.0)
    f.SetNagaiHondaMembraneSurfaceEnergyParameter(1.0)
    f.SetNagaiHondaCellCellAdhesionEnergyParameter(1.0)
    f.SetNagaiHondaLabelledCellCellAdhesionEnergyParameter(2.0)
    f.SetNagaiHondaLabelledCellLabelledCellAdhesionEnergyParameter(1.0)
    f.SetNagaiHondaCellBoundaryAdhesionEnergyParameter(10.0)
    f.SetNagaiHondaLabelledCellBoundaryAdhesionEnergyParameter(20.0)
    sim.AddForce(f)
    # paper sets target area per cell BY HAND and omits SimpleTargetAreaModifier
    for i in range(mesh.GetNumElements()):
        if pop.IsCellAttachedToLocationIndex(i):
            pop.GetCellUsingLocationIndex(i).GetCellData().SetItem("target area", 1.0)
    _KEEP.extend([gen, mesh, pop, f, sim])
    return sim, pop


BUILDERS = {"cp": build_cp, "os": build_os, "vt": build_vt, "vm": build_vm}


def read_heterotypic(outdir):
    hits = glob.glob(os.path.join(OUT, outdir, "**", "heterotypicboundary.dat"), recursive=True)
    if not hits:
        return None
    with open(hits[0]) as f:
        lines = [l for l in f.read().strip().splitlines() if l.strip()]
    if not lines:
        return None
    cols = lines[-1].split()
    # time, heterotypic_len, total_len, num_het_pairs, total_pairs
    return [float(c) for c in cols]


def run(model):
    cb.SetupNotebookTest()
    chaste.core.RandomNumberGenerator.Instance().Reseed(0)
    sim, pop = BUILDERS[model]()
    outdir = "spike_sort_" + model
    sim.SetOutputDirectory(outdir)
    w = cb.HeterotypicBoundaryLengthWriter["2", "2"]()
    _KEEP.append(w)
    pop.AddPopulationWriter(w)
    n_lab = _LABELLED.get("n", 0)
    sim.SetEndTime(END)
    sim.Solve()
    row = read_heterotypic(outdir)
    return {"cells": int(pop.GetNumRealCells()), "labelled": n_lab, "het_row": row}


if __name__ == "__main__":
    only = sys.argv[1:] or list(BUILDERS)
    results = {}
    for m in only:
        print("=" * 60, flush=True)
        print("MODEL:", m.upper(), flush=True)
        try:
            r = run(m)
            results[m] = r
            print("  cells=%s labelled=%s" % (r["cells"], r["labelled"]))
            if r["het_row"]:
                t, het, tot = r["het_row"][0], r["het_row"][1], r["het_row"][2]
                frac = het / tot if tot else float("nan")
                print("  heterotypicboundary.dat last row: t=%.3f het=%.4f total=%.4f" % (t, het, tot))
                print("  FRACTIONAL BOUNDARY LENGTH = %.4f" % frac)
                print("  STATUS: OK")
            else:
                print("  STATUS: *** RAN BUT NO heterotypicboundary.dat ***")
        except Exception as e:
            results[m] = {"error": str(e)}
            print("  STATUS: *** FAILED *** %s: %s" % (type(e).__name__, e))
            print(traceback.format_exc()[-1500:])
    print("=" * 60)
    print("SUMMARY:", {k: ("ok" if "error" not in v else "FAIL") for k, v in results.items()})
