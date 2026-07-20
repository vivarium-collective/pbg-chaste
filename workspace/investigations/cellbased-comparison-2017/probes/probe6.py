import chaste, chaste.cell_based as cb, chaste.mesh as me, math, traceback
chaste.cell_based.SetupNotebookTest()
_KEEP = []

def build():
    gen = me.HoneycombMeshGenerator(3, 3, 0)
    gm = gen.GetMesh()
    mesh = me.NodesOnlyMesh2(); mesh.ConstructNodesWithoutMesh(gm, 1.5)
    cells = cb.CellsGeneratorUniformCellCycleModel_2().GenerateBasicRandom(mesh.GetNumNodes())
    pop = cb.NodeBasedCellPopulation2(mesh, cells)
    _KEEP.extend([mesh, cells, pop])
    return pop

# ---- CONTROL: identical sim, ONLY the mainline C++ force ----
print("### CONTROL: mainline force only")
pop = build()
sim = cb.OffLatticeSimulation2_2(pop); _KEEP.append(sim)
sim.SetOutputDirectory("probe_control"); sim.SetEndTime(0.05); sim.SetSamplingTimestepMultiple(10)
sp = cb.GeneralisedLinearSpringForce2_2(); _KEEP.append(sp)
sim.AddForce(sp)
try:
    sim.Solve(); print("CONTROL: SOLVED OK -> baseline is fine\n")
except Exception as e:
    print("CONTROL FAILED:", type(e).__name__, e, "\n")

# ---- TEST: Python force whose override does NOTHING (no arg use) ----
print("### TEST: python force, override touches NOTHING")
f0 = cb.GeneralisedLinearSpringForce2_2()
AbstractForce = [k for k in type(f0).__mro__ if k.__name__ == "AbstractForce_2_2"][0]
class NoopPyForce(AbstractForce):
    def __init__(self):
        AbstractForce.__init__(self); self.calls = 0
    def AddForceContribution(self, rCellPopulation):
        self.calls += 1          # never touches the argument
    def OutputForceParameters(self, rParamsFile): pass

pop2 = build()
sim2 = cb.OffLatticeSimulation2_2(pop2); _KEEP.append(sim2)
sim2.SetOutputDirectory("probe_noop"); sim2.SetEndTime(0.05); sim2.SetSamplingTimestepMultiple(10)
sp2 = cb.GeneralisedLinearSpringForce2_2(); nf = NoopPyForce(); _KEEP += [sp2, nf]
sim2.AddForce(sp2); sim2.AddForce(nf)
try:
    sim2.Solve()
    print("TEST: SOLVED. python override called %d times" % nf.calls)
    print("=> conversion error is ONLY about passing the population arg into Python")
except Exception as e:
    print("TEST FAILED:", type(e).__name__, e)
    print("   calls before failure:", nf.calls)
