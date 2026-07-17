import chaste; chaste.init()
import chaste.cell_based as cb, chaste.mesh as me, math
cb.SetupNotebookTest()

# ---- (1) DiffusionForce scaling = C * T / viscosity : find C ----
f = cb.DiffusionForce["2"]()
print("defaults: T=%.4g visc=%.6g scaling=%.6g" % (
    f.GetAbsoluteTemperature(), f.GetViscosity(), f.GetDiffusionScalingConstant()))
f.SetAbsoluteTemperature(1.0); f.SetViscosity(1.0)
C = f.GetDiffusionScalingConstant()
print("C (scaling at T=1,visc=1) = %.8g" % C)
# target: scaling = xi * radius, with xi=0.05, radius=0.5 -> S=0.025
S = 0.05 * 0.5
f.SetViscosity(1.0); f.SetAbsoluteTemperature(S / C)
print("to hit S=%.4g: set T=%.6g visc=1 -> scaling=%.6g" % (S, S/C, f.GetDiffusionScalingConstant()))

# ---- (2) how to read back a CellLabel on a cell ----
gen = me.HoneycombMeshGenerator(3,3,0); gm = gen.GetMesh()
mesh = me.NodesOnlyMesh["2"](); mesh.ConstructNodesWithoutMesh(gm,1.5)
cg = cb.CellsGenerator["UniformG1GenerationalCellCycleModel","2"]()
cells = cg.GenerateBasicRandom(mesh.GetNumNodes(), cb.DifferentiatedCellProliferativeType())
lab = cb.CellLabel()
cells[0].AddCellProperty(lab)
c = cells[0]
print("\nCellLabel readback attempts on a labelled cell:")
for name, fn in [
    ('HasCellProperty["CellLabel"]()', lambda: c.HasCellProperty["CellLabel"]()),
    ('HasCellPropertyCellLabel()', lambda: c.HasCellPropertyCellLabel()),
    ('GetCellData has label? via mutation', lambda: None),
]:
    try:
        print("  %-40s -> %r" % (name, fn()))
    except Exception as e:
        print("  %-40s -> %s: %s" % (name, type(e).__name__, str(e)[:60]))
print("  methods with 'Property':", [m for m in dir(c) if "Propert" in m][:12])
print("  methods with 'Label':", [m for m in dir(c) if "Label" in m])
# unlabelled cell for contrast
print("  unlabelled HasCellPropertyCellLabel():", cells[1].HasCellPropertyCellLabel() if hasattr(cells[1],'HasCellPropertyCellLabel') else "n/a")
