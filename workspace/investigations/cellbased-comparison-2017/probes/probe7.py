import chaste; chaste.init()
import chaste.cell_based as cb, chaste.mesh as me
cb.SetupNotebookTest()
gen = me.HoneycombMeshGenerator(3,3,0); gm = gen.GetMesh()
mesh = me.NodesOnlyMesh["2"](); mesh.ConstructNodesWithoutMesh(gm, 1.5)
cg = cb.CellsGenerator["UniformG1GenerationalCellCycleModel","2"]()
cells = cg.GenerateBasicRandom(mesh.GetNumNodes(), cb.DifferentiatedCellProliferativeType())
pop = cb.NodeBasedCellPopulation["2"](mesh, cells)

print("=== cell-access methods on the population ===")
print([m for m in dir(pop) if any(k in m for k in ("Cell","Iter","Begin","End","Cells"))])
print()
print("=== is the population itself iterable? ===")
try:
    it = iter(pop); first = next(it)
    print("  YES -> iter(pop) yields", type(first).__name__)
except Exception as e:
    print("  no:", type(e).__name__, e)
print()
print("=== what does the CellsGenerator return? ===")
print("  type:", type(cells).__name__, "len:", len(cells) if hasattr(cells,'__len__') else "?")
try:
    print("  cells[0] ->", type(cells[0]).__name__)
    print("  AddCellProperty on it?", hasattr(cells[0], "AddCellProperty"))
except Exception as e:
    print("  index failed:", e)
print()
print("=== CellLabel + AddCellProperty round-trip on a generator cell ===")
try:
    lab = cb.CellLabel()
    cells[0].AddCellProperty(lab)
    print("  labelled ok; HasCellProperty:", cells[0].HasCellProperty["CellLabel"]() if hasattr(cells[0],'HasCellProperty') else "n/a")
except Exception as e:
    print("  FAILED:", type(e).__name__, e)
print()
print("=== GetCellUsingLocationIndex path (what the existing wrapper uses) ===")
try:
    c = pop.GetCellUsingLocationIndex(0)
    print("  ok ->", type(c).__name__, "| AddCellProperty:", hasattr(c,"AddCellProperty"))
except Exception as e:
    print("  failed:", type(e).__name__, e)
