import chaste; chaste.init()
def _try(m,i):
    try:
        return m.GetNode(i).GetRadius()<=0
    except Exception:
        return True
import chaste.cell_based as cb, chaste.mesh as me
cb.SetupNotebookTest()
chaste.core.RandomNumberGenerator.Instance().Reseed(0)
gen = me.HoneycombMeshGenerator(4,4,2)
mesh = gen.GetMesh()
loc = gen.GetCellLocationIndices()
cg = cb.CellsGenerator["UniformG1GenerationalCellCycleModel","2"]()
cells = cg.GenerateBasicRandom(len(loc), cb.DifferentiatedCellProliferativeType())
pop = cb.MeshBasedCellPopulationWithGhostNodes["2"](mesh, cells, loc)
print("mesh.GetNumNodes:", mesh.GetNumNodes())
# set radius on all
set_ok = 0
for i in range(mesh.GetNumNodes()):
    try:
        mesh.GetNode(i).SetRadius(0.5); set_ok += 1
    except Exception as e:
        print("  set fail at", i, e)
print("radii set on", set_ok, "nodes")
# verify all readable now
bad = []
for i in range(mesh.GetNumNodes()):
    try:
        if mesh.GetNode(i).GetRadius() <= 0: bad.append(i)
    except Exception as e:
        bad.append((i, str(e)[:30]))
print("nodes still missing radius BEFORE solve:", bad[:10], "..." if len(bad)>10 else "")
sim = cb.OffLatticeSimulation["2","2"](pop)
sim.SetDt(1/200.); sim.SetOutputDirectory("probe_vt_r"); sim.SetSamplingTimestepMultiple(200)
f = cb.DiffusionForce["2"](); f.SetViscosity(1.0); f.SetAbsoluteTemperature(0.05*0.5/2.636845e-08)
sim.AddForce(f)
sim.SetEndTime(0.05)
try:
    sim.Solve()
    print("SOLVE OK")
    # after solve, recount nodes and radii
    print("after solve mesh.GetNumNodes:", mesh.GetNumNodes())
    bad2 = [i for i in range(mesh.GetNumNodes()) if _try(mesh,i)]
except Exception as e:
    print("SOLVE FAILED:", str(e)[:120])
    print("after-fail mesh.GetNumNodes:", mesh.GetNumNodes())
    miss = []
    for i in range(mesh.GetNumNodes()):
        try:
            mesh.GetNode(i).GetRadius()
        except Exception:
            miss.append(i)
    print("nodes missing radius AFTER failed solve:", len(miss), miss[:8])
