import chaste; chaste.init()
import chaste.cell_based as cb, chaste.mesh as me
cb.SetupNotebookTest()
gen = me.HoneycombMeshGenerator(3,3,0); gm = gen.GetMesh()
mesh = me.NodesOnlyMesh["2"](); mesh.ConstructNodesWithoutMesh(gm, 1.5)
cg = cb.CellsGenerator["UniformG1GenerationalCellCycleModel","2"]()
cells = cg.GenerateBasicRandom(mesh.GetNumNodes(), cb.DifferentiatedCellProliferativeType())
pop = cb.NodeBasedCellPopulation["2"](mesh, cells)

print("=== ALL AddPopulationWriter* methods (exact) ===")
for m in sorted(m for m in dir(pop) if m.startswith("AddPopulationWriter")): print("   ", m)
print("\n=== is there a generic AddPopulationWriter? ===")
print("   ", "YES" if hasattr(pop, "AddPopulationWriter") else "*** NO ***")

print("\n=== can we attach HeterotypicBoundaryLengthWriter at all? ===")
w = cb.HeterotypicBoundaryLengthWriter["2","2"]()
attempts = [
    ("AddPopulationWriter(instance)", lambda: pop.AddPopulationWriter(w)),
    ("AddPopulationWriter[T]() subscript", lambda: pop.AddPopulationWriter["HeterotypicBoundaryLengthWriter"]()),
    ("AddPopulationWriterHeterotypicBoundaryLengthWriter()", lambda: pop.AddPopulationWriterHeterotypicBoundaryLengthWriter()),
    ("AddCellPopulationCountWriter(instance)", lambda: pop.AddCellPopulationCountWriter(w)),
    ("AddCellWriter(instance)", lambda: pop.AddCellWriter(w)),
]
for name, fn in attempts:
    try:
        fn(); print("   OK   ", name)
    except Exception as e:
        print("   fail ", name, "->", type(e).__name__, str(e)[:90])
