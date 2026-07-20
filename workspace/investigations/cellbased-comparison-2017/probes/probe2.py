import chaste, importlib
mods = {}
for m in ["cell_based","mesh","core","ode","pde","visualization"]:
    try:
        mods[m] = importlib.import_module("chaste."+m)
    except Exception as e:
        print("cannot import chaste.%s: %s" % (m, e))

def find(name):
    hits = [m for m,mod in mods.items() if any(n==name or n.startswith(name) for n in dir(mod))]
    return hits

print("=== 1. MESH GENERATORS (paper needs these) ===")
for t in ["PottsMeshGenerator","HoneycombMeshGenerator","HoneycombVertexMeshGenerator",
          "CylindricalHoneycombMeshGenerator","CylindricalHoneycombVertexMeshGenerator",
          "NodesOnlyMesh","Cylindrical2dNodesOnlyMesh","PottsMesh"]:
    print("  %-42s %s" % (t, find(t) or "*** MISSING ***"))

print("=== 2. THE PAPER'S SORTING METRIC WRITERS ===")
for t in ["HeterotypicBoundaryLengthWriter","CellPopulationAdjacencyMatrixWriter",
          "CellIdWriter","CellMutationStatesWriter","CellLabelWriter"]:
    print("  %-42s %s" % (t, find(t) or "*** MISSING ***"))

print("=== 3. ABSTRACT BASES — can we subclass from Python? ===")
for t in ["AbstractForce","AbstractCaSwitchingUpdateRule","AbstractCellBasedSimulationModifier",
          "AbstractCellKiller","AbstractCaUpdateRule","AbstractPottsUpdateRule"]:
    print("  %-42s %s" % (t, find(t) or "*** MISSING ***"))

print("=== 4. TRAMPOLINE CHECK: subclass AbstractForce2_2 in Python ===")
import chaste.cell_based as cb
base = None
for cand in ["AbstractForce2_2","AbstractForce2"]:
    if hasattr(cb, cand):
        base = getattr(cb, cand); print("  base found:", cand); break
if base is None:
    print("  *** no AbstractForce base exported -> RandomMotionForce NOT subclassable ***")
else:
    try:
        class PyRandomMotionForce(base):
            def __init__(self): super().__init__()
            def AddForceContribution(self, pop): pass
            def OutputForceParameters(self, f): pass
        f = PyRandomMotionForce()
        print("  SUCCESS: instantiated Python subclass ->", type(f).__mro__[1].__name__)
    except Exception as e:
        print("  *** FAILED to subclass:", type(e).__name__, e)
