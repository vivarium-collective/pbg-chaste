import chaste; chaste.init()
import chaste.cell_based as cb, chaste.mesh as me
cb.SetupNotebookTest(); chaste.core.RandomNumberGenerator.Instance().Reseed(0)
gen = me.HoneycombMeshGenerator(4,4,2)
mesh = gen.GetMesh(); loc = gen.GetCellLocationIndices()
cg = cb.CellsGenerator["UniformG1GenerationalCellCycleModel","2"]()
cells = cg.GenerateBasicRandom(len(loc), cb.DifferentiatedCellProliferativeType())
pop = cb.MeshBasedCellPopulationWithGhostNodes["2"](mesh, cells, loc)
for i in range(mesh.GetNumNodes()):
    try: mesh.GetNode(i).SetRadius(0.5)
    except Exception: pass
# solve with ONLY a spring force (no DiffusionForce)
sim = cb.OffLatticeSimulation["2","2"](pop)
sim.SetDt(1/200.); sim.SetOutputDirectory("probe_vt3"); sim.SetSamplingTimestepMultiple(200)
sp = cb.GeneralisedLinearSpringForce["2","2"](); sp.SetMeinekeSpringStiffness(50.0)
sim.AddForce(sp); sim.SetEndTime(0.05)
sim.Solve()
print("plain solve OK")
# now check radii AFTER solve on the same mesh handle
m2 = pop.rGetMesh()
miss = 0
for i in range(m2.GetNumNodes()):
    try:
        if m2.GetNode(i).GetRadius() <= 0: miss += 1
    except Exception:
        miss += 1
print("after plain solve: nodes with missing/zero radius =", miss, "of", m2.GetNumNodes())
