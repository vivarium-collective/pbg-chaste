import chaste; chaste.init()
import chaste.cell_based as cb, chaste.mesh as me
cb.SetupNotebookTest()
cg = cb.CellsGenerator["UniformG1GenerationalCellCycleModel","2"]()

# VT mesh (MeshBasedCellPopulationWithGhostNodes)
gen = me.HoneycombMeshGenerator(4,4,2)
mesh = gen.GetMesh()
print("VT mesh:", type(mesh).__name__)
print("  GetNumNodes:", mesh.GetNumNodes(), "GetNumAllNodes:", mesh.GetNumAllNodes() if hasattr(mesh,'GetNumAllNodes') else 'n/a')
n0 = mesh.GetNode(0)
print("  node0 methods radius:", [m for m in dir(n0) if 'Radius' in m])
print("  node0 default radius:", n0.GetRadius())
n0.SetRadius(0.5); print("  after SetRadius:", n0.GetRadius())

# VM mesh (MutableVertexMesh)
gen2 = me.HoneycombVertexMeshGenerator(4,4)
mesh2 = gen2.GetMesh()
print("VM mesh:", type(mesh2).__name__)
print("  GetNumNodes:", mesh2.GetNumNodes())
v0 = mesh2.GetNode(0)
print("  vertex0 radius methods:", [m for m in dir(v0) if 'Radius' in m])
try:
    print("  vertex0 default radius:", v0.GetRadius())
    v0.SetRadius(0.5); print("  after:", v0.GetRadius())
except Exception as e:
    print("  radius on vertex FAILED:", type(e).__name__, e)
