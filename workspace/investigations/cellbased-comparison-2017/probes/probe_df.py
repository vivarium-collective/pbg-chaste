import chaste; chaste.init()
import chaste.cell_based as cb
f = cb.DiffusionForce["2"]()
print("Set* methods:", [m for m in dir(f) if m.startswith("Set")])
print("Get* methods:", [m for m in dir(f) if m.startswith("Get")])
print("default scaling:", f.GetDiffusionScalingConstant())
