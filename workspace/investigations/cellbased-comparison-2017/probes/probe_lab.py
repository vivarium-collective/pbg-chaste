import chaste; chaste.init()
import chaste.cell_based as cb, chaste.mesh as me
cb.SetupNotebookTest()
gen = me.HoneycombMeshGenerator(3,3,0); gm = gen.GetMesh()
mesh = me.NodesOnlyMesh["2"](); mesh.ConstructNodesWithoutMesh(gm,1.5)
cg = cb.CellsGenerator["UniformG1GenerationalCellCycleModel","2"]()
cells = cg.GenerateBasicRandom(mesh.GetNumNodes(), cb.DifferentiatedCellProliferativeType())
c = cells[0]; other = cells[1]
lab = cb.CellLabel(); c.AddCellProperty(lab)
print("Cell methods with 'Coll' or 'Propert' or 'Mutation' or 'Data':",
      [m for m in dir(c) if any(k in m for k in ('Coll','Propert','Mutation'))])
# property collection route
try:
    coll = c.rGetCellPropertyCollection()
    print("collection type:", type(coll).__name__, "| methods:", [m for m in dir(coll) if not m.startswith('_')][:20])
    try:
        print("labelled cell HasProperty[CellLabel]:", coll.HasProperty["CellLabel"]())
        print("plain cell HasProperty[CellLabel]:", other.rGetCellPropertyCollection().HasProperty["CellLabel"]())
    except Exception as e:
        print("HasProperty subscript failed:", type(e).__name__, e)
    try:
        print("GetSize labelled:", coll.GetSize(), "plain:", other.rGetCellPropertyCollection().GetSize())
    except Exception as e:
        print("GetSize failed:", e)
except Exception as e:
    print("no rGetCellPropertyCollection:", type(e).__name__, e)
# population-level route
pop = cb.NodeBasedCellPopulation["2"](mesh, cells)
print("\npop methods with 'Label' or 'Mutation':", [m for m in dir(pop) if any(k in m for k in ('Label','Mutation'))][:15])
