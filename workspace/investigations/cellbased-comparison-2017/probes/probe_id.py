import chaste; chaste.init()
import chaste.cell_based as cb, chaste.mesh as me
cb.SetupNotebookTest()
cg = cb.CellsGenerator["UniformG1GenerationalCellCycleModel","2"]()
gen = me.HoneycombMeshGenerator(3,3,0)
mesh = me.NodesOnlyMesh["2"](); mesh.ConstructNodesWithoutMesh(gen.GetMesh(),1.5)
cells = cg.GenerateBasicRandom(mesh.GetNumNodes(), cb.DifferentiatedCellProliferativeType())
print("GetCellId on cell:", cells[0].GetCellId(), "unique:", len({c.GetCellId() for c in cells})==len(cells))
