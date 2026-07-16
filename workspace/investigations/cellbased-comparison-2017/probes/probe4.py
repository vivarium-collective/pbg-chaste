import chaste.cell_based as cb
f = cb.GeneralisedLinearSpringForce2_2()
print("=== MRO of GeneralisedLinearSpringForce2_2 ===")
for k in type(f).__mro__: print("   ", k.__module__, "::", k.__name__)

print("\n=== Try grabbing the AbstractForce base off the MRO and subclassing it ===")
bases = [k for k in type(f).__mro__ if "AbstractForce" in k.__name__]
if not bases:
    print("  *** no AbstractForce anywhere in MRO ***")
else:
    B = bases[0]
    print("  found base via MRO:", B.__name__)
    try:
        class PyRandomMotionForce(B):
            def __init__(self):
                B.__init__(self)
                self.calls = 0
            def AddForceContribution(self, rCellPopulation):
                self.calls += 1
            def OutputForceParameters(self, rParamsFile):
                pass
        pf = PyRandomMotionForce()
        print("  SUCCESS: instantiated Python subclass of", B.__name__)
        print("  -> RandomMotionForce IS implementable in Python")
    except Exception as e:
        print("  *** FAILED:", type(e).__name__, e)

print("\n=== Same question for the CA switching rule ===")
r = cb.RandomCaSwitchingUpdateRule2()
for k in type(r).__mro__: print("   ", k.__module__, "::", k.__name__)
sw = [k for k in type(r).__mro__ if "Switching" in k.__name__ and k is not type(r)]
if sw:
    B2 = sw[0]
    print("  base:", B2.__name__)
    try:
        class PyDiffAdhesionCaSwitch(B2):
            def __init__(self): B2.__init__(self)
            def EvaluateSwitchingProbability(self, *a): return 0.0
        x = PyDiffAdhesionCaSwitch()
        print("  SUCCESS: CA switching rule subclassable")
    except Exception as e:
        print("  *** FAILED:", type(e).__name__, e)
else:
    print("  *** no switching base in MRO ***")
