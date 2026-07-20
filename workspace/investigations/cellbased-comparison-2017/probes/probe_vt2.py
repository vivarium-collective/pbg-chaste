import chaste; chaste.init()
import chaste.cell_based as cb, chaste.mesh as me
cb.SetupNotebookTest(); chaste.core.RandomNumberGenerator.Instance().Reseed(0)
gen = me.HoneycombMeshGenerator(4,4,2)
mesh = gen.GetMesh(); loc = gen.GetCellLocationIndices()
cg = cb.CellsGenerator["UniformG1GenerationalCellCycleModel","2"]()
cells = cg.GenerateBasicRandom(len(loc), cb.DifferentiatedCellProliferativeType())
pop = cb.MeshBasedCellPopulationWithGhostNodes["2"](mesh, cells, loc)
pm = pop.rGetMesh()
print("gen mesh is pop mesh?", pm is mesh, "| pop mesh nodes:", pm.GetNumNodes())
# set via pop's own mesh
for i in range(pm.GetNumNodes()):
    try: pm.GetNode(i).SetRadius(0.5)
    except Exception as e: print("fail", i, e)
sim = cb.OffLatticeSimulation["2","2"](pop)
sim.SetDt(1/200.); sim.SetOutputDirectory("probe_vt2"); sim.SetSamplingTimestepMultiple(200)
f = cb.DiffusionForce["2"](); f.SetViscosity(1.0); f.SetAbsoluteTemperature(0.05*0.5/2.636845e-08)
sim.AddForce(f); sim.SetEndTime(0.05)
try:
    sim.Solve(); print("SOLVE OK via pop.rGetMesh()")
except Exception as e:
    print("STILL FAILED:", str(e)[:110])
