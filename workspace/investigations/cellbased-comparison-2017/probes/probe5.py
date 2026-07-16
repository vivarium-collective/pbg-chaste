import chaste, chaste.cell_based as cb, chaste.mesh as me, math
chaste.cell_based.SetupNotebookTest()
_KEEP = []

f0 = cb.GeneralisedLinearSpringForce2_2()
AbstractForce = [k for k in type(f0).__mro__ if k.__name__ == "AbstractForce_2_2"][0]

class PyRandomMotionForce(AbstractForce):
    """Port of CellBasedComparison2017 src/CellSorting/RandomMotionForce."""
    def __init__(self, movement_parameter=0.1):
        AbstractForce.__init__(self)
        self.mMovementParameter = movement_parameter
        self.calls = 0
        self.nodes_touched = 0
    def AddForceContribution(self, rCellPopulation):
        self.calls += 1
        dt = chaste.core.SimulationTime.Instance().GetTimeStep()
        rng = chaste.core.RandomNumberGenerator.Instance()
        scale = math.sqrt(2.0 * self.mMovementParameter * dt) / dt
        for node in rCellPopulation.rGetMesh().rGetNodes() if hasattr(rCellPopulation.rGetMesh(),'rGetNodes') else []:
            pass
        n = rCellPopulation.GetNumNodes()
        for i in range(n):
            node = rCellPopulation.GetNode(i)
            force = [scale * rng.StandardNormalRandomDeviate() for _ in range(2)]
            node.AddAppliedForceContribution(force)
            self.nodes_touched += 1
    def OutputForceParameters(self, rParamsFile):
        pass

gen = me.HoneycombMeshGenerator(3, 3, 0)
gm = gen.GetMesh()
mesh = me.NodesOnlyMesh2()
mesh.ConstructNodesWithoutMesh(gm, 1.5)
_KEEP.append(mesh)
cells = cb.CellsGeneratorUniformCellCycleModel_2().GenerateBasicRandom(mesh.GetNumNodes())
pop = cb.NodeBasedCellPopulation2(mesh, cells)
_KEEP.append(pop)

sim = cb.OffLatticeSimulation2_2(pop)
sim.SetOutputDirectory("probe_pyforce")
sim.SetSamplingTimestepMultiple(10)
sim.SetEndTime(0.05)
spring = cb.GeneralisedLinearSpringForce2_2()
pyf = PyRandomMotionForce(0.1)
_KEEP += [spring, pyf, sim]
sim.AddForce(spring)
sim.AddForce(pyf)
print("solving with a PYTHON-defined force in the C++ loop...")
sim.Solve()
print("RESULT: AddForceContribution called %d times, %d node-force writes" % (pyf.calls, pyf.nodes_touched))
print("VERDICT:", "TRAMPOLINE WORKS — C++ called back into Python" if pyf.calls > 0
      else "*** TRAMPOLINE DEAD — Python override never invoked ***")
