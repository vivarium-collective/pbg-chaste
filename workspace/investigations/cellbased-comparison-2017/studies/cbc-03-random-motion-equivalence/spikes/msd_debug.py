import chaste; chaste.init()
import chaste.cell_based as cb, chaste.mesh as me, math
cb.SetupNotebookTest(); chaste.core.RandomNumberGenerator.Instance().Reseed(1)
XI, RADIUS, DT, C = 0.1, 0.5, 0.005, 2.636845e-08
base = me.HoneycombMeshGenerator(1,1,0)
nodes = me.NodesOnlyMesh["2"](); nodes.ConstructNodesWithoutMesh(base.GetMesh(), 1.5)
cg = cb.CellsGenerator["UniformG1GenerationalCellCycleModel","2"]()
cells = cg.GenerateBasicRandom(nodes.GetNumNodes(), cb.DifferentiatedCellProliferativeType())
pop = cb.NodeBasedCellPopulation["2"](nodes, cells)
for i in range(nodes.GetNumNodes()): nodes.GetNode(i).SetRadius(RADIUS)
print("num cells:", pop.GetNumRealCells(), "| node radius:", pop.GetNode(0).GetRadius())
# damping constant
try:
    print("damping normal:", pop.GetDampingConstant(0))
except Exception as e:
    print("GetDampingConstant err:", e)
f = cb.DiffusionForce["2"](); f.SetViscosity(1.0); f.SetAbsoluteTemperature(XI*RADIUS/C)
print("requested scaling:", XI*RADIUS, "| actual scaling readback:", f.GetDiffusionScalingConstant())
print("=> implied D = scaling/radius =", f.GetDiffusionScalingConstant()/RADIUS)
# measure displacement over N steps of a bare sim
sim = cb.OffLatticeSimulation["2","2"](pop); sim.SetDt(DT); sim.SetSamplingTimestepMultiple(1000)
sim.SetOutputDirectory("msd_dbg"); sim.AddForce(f)
c0 = pop.GetCellUsingLocationIndex(0); p0 = pop.GetLocationOfCellCentre(c0)
x0,y0 = float(p0[0]), float(p0[1])
N=200
sim.SetEndTime(DT*N); sim.Solve()
# find the cell again
for i in range(pop.GetNumNodes()+4):
    if pop.IsCellAttachedToLocationIndex(i):
        loc = pop.GetLocationOfCellCentre(pop.GetCellUsingLocationIndex(i))
        d2 = (float(loc[0])-x0)**2 + (float(loc[1])-y0)**2
        print("after %d steps (t=%.3f): displacement^2 = %.5g (start (%.3f,%.3f) -> (%.3f,%.3f))" % (
            N, DT*N, d2, x0,y0, float(loc[0]), float(loc[1])))
        break
print("expected single-walk E[disp^2] = 4*D*t =", 4*(f.GetDiffusionScalingConstant()/RADIUS)*DT*N)
