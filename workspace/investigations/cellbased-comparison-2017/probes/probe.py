import chaste, chaste.cell_based as cb, pkgutil, inspect
names = sorted(n for n in dir(cb) if not n.startswith('_'))
print("TOTAL chaste.cell_based names:", len(names))
targets = ["CaBasedCellPopulation","PottsBasedCellPopulation","PottsMeshGenerator",
"VolumeConstraintPottsUpdateRule","SurfaceAreaConstraintPottsUpdateRule",
"AdhesionPottsUpdateRule","DifferentialAdhesionPottsUpdateRule",
"DiffusionCaUpdateRule","ShovingCaBasedDivisionRule","RandomCaSwitchingUpdateRule",
"OnLatticeSimulation","MeshBasedCellPopulationWithGhostNodes","NodeBasedCellPopulation",
"VertexBasedCellPopulation","MeshBasedCellPopulation","NagaiHondaForce",
"NagaiHondaDifferentialAdhesionForce","DifferentialAdhesionGeneralisedLinearSpringForce",
"GeneralisedLinearSpringForce","RandomMotionForce","DiffusionForce",
"ContactInhibitionCellCycleModel","DeltaNotchSrnModel","DeltaNotchTrackingModifier",
"CellLabel","CellMutationState","VoronoiDataWriter","CylindricalHoneycombMeshGenerator",
"HoneycombMeshGenerator","HoneycombVertexMeshGenerator","CryptSimulation2d",
"WntConcentration","SimpleTargetAreaModifier","VolumeTrackingModifier",
"CellDataItemWriter","CellAncestor","CellAncestorWriter","SloughingCellKiller",
"PlaneBasedCellKiller","RandomCellKiller","TargetAreaLinearGrowthModifier",
"UniformCellCycleModel","UniformG1GenerationalCellCycleModel","OffLatticeSimulation"]
for t in targets:
    print(("OK  " if t in names else "MISS"), t)
