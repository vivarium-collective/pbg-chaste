"""cbc-03: verify the DiffusionForce calibration in the free-diffusion limit.

Under DiffusionForce ALONE (no spring/adhesion force added), cells do not
interact, so every cell in one population is an independent 2D random walker with
  E[|r(t)-r(0)|^2] = 4 * D * t,   D = scaling / radius.
Our calibration sets scaling = xi * radius so D = xi — exactly the paper's
RandomMotionForce (x_new = x_old + sqrt(2*xi*dt)*W, D=xi). We measure the mean
squared displacement across all cells in ONE Solve (a single process, one
SimulationTime — avoids the repeated-SetupNotebookTest reset bug), which gives a
statistically valid check without the C++ RandomMotionForce.
"""
import os, math
import chaste
chaste.init()
import chaste.cell_based as cb
import chaste.mesh as me

XI = float(os.environ.get("MSD_XI", "0.1"))
RADIUS = 0.5
DT = float(os.environ.get("MSD_DT", "0.005"))
NSTEPS = int(os.environ.get("MSD_NSTEPS", "200"))
WIDTH = int(os.environ.get("MSD_WIDTH", "12"))   # WIDTH^2 independent walkers
SCALING_C = 2.636845e-08
_KEEP = []


def main():
    cb.SetupNotebookTest()
    chaste.core.RandomNumberGenerator.Instance().Reseed(1)
    base = me.HoneycombMeshGenerator(WIDTH, WIDTH, 0)
    nodes = me.NodesOnlyMesh["2"]()
    nodes.ConstructNodesWithoutMesh(base.GetMesh(), 1.5)
    cg = cb.CellsGenerator["UniformG1GenerationalCellCycleModel", "2"]()
    cells = cg.GenerateBasicRandom(nodes.GetNumNodes(),
                                   cb.DifferentiatedCellProliferativeType())
    pop = cb.NodeBasedCellPopulation["2"](nodes, cells)
    for i in range(nodes.GetNumNodes()):
        nodes.GetNode(i).SetRadius(RADIUS)
    sim = cb.OffLatticeSimulation["2", "2"](pop)
    sim.SetDt(DT)
    sim.SetSamplingTimestepMultiple(NSTEPS)
    sim.SetOutputDirectory("msd_multi")
    f = cb.DiffusionForce["2"]()
    f.SetViscosity(1.0)
    f.SetAbsoluteTemperature(XI * RADIUS / SCALING_C)   # D = scaling/radius = XI
    sim.AddForce(f)                                       # ONLY force: no springs
    _KEEP.extend([nodes, pop, sim, f, cells])

    D = f.GetDiffusionScalingConstant() / RADIUS

    # initial positions keyed by cell id (ids stable; cells neither divide nor die)
    def positions_by_id():
        out = {}
        for i in range(pop.GetNumNodes() + 8):
            if pop.IsCellAttachedToLocationIndex(i):
                c = pop.GetCellUsingLocationIndex(i)
                loc = pop.GetLocationOfCellCentre(c)
                out[int(c.GetCellId())] = (float(loc[0]), float(loc[1]))
        return out

    p0 = positions_by_id()
    sim.SetEndTime(DT * NSTEPS)
    sim.Solve()
    p1 = positions_by_id()

    disps = []
    for cid, (x0, y0) in p0.items():
        if cid in p1:
            x1, y1 = p1[cid]
            disps.append((x1 - x0) ** 2 + (y1 - y0) ** 2)
    n = len(disps)
    t = DT * NSTEPS
    msd = sum(disps) / n
    var = sum((d - msd) ** 2 for d in disps) / (n - 1)
    sem = math.sqrt(var / n)
    expected = 4.0 * D * t
    z = (msd - expected) / sem
    print("XI=%.4g D=%.4g DT=%.4g NSTEPS=%d t=%.3g walkers=%d" % (XI, D, DT, NSTEPS, t, n))
    print("expected MSD (4*D*t) = %.5g" % expected)
    print("measured MSD         = %.5g  (SEM %.3g)" % (msd, sem))
    print("z = (measured-expected)/SEM = %.2f" % z)
    print("VERDICT:", "MATCH (|z|<3): DiffusionForce reproduces free diffusion at D=xi"
          if abs(z) < 3 else "MISMATCH (|z|>=3)")


if __name__ == "__main__":
    main()
