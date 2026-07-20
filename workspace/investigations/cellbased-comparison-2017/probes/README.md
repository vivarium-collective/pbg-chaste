# PyChaste binding probes

Feasibility probes run against `chaste/pychaste:latest` (image `ab209bc1be9e`) on
2026-07-16, before any wrapper code was written. They establish what the Osborne
et al. 2017 reproduction can and cannot reach through the shipped bindings.

Run any of them with:

```bash
docker run --rm --platform linux/amd64 \
  -e OMP_NUM_THREADS=1 -e OPENBLAS_NUM_THREADS=1 \
  -e KMP_AFFINITY=disabled -e OMP_WAITPOLICY=passive \
  -v "$PWD":/w -w /w chaste/pychaste python3 /w/probe6.py
```

Note: Docker Desktop does not share `/private/tmp` — mount from a path under
`$HOME` or the probe directory appears empty inside the container.

| Probe | What it establishes |
|---|---|
| `probe.py` | Names present in `chaste.cell_based` (646 total). Confirms `CaBasedCellPopulation`, `PottsBasedCellPopulation`, `OnLatticeSimulation`, `MeshBasedCellPopulationWithGhostNodes`, all Potts update rules incl. `DifferentialAdhesionPottsUpdateRule`, both differential-adhesion forces, `CellLabel`, `DiffusionForce`. **Its "MISS" lines for mesh generators are wrong** — see `probe2.py`. |
| `probe2.py` | Corrects the above: mesh generators (`PottsMeshGenerator`, `HoneycombMeshGenerator`, …) live in **`chaste.mesh`**, not `chaste.cell_based`. Confirms the paper's own metric writer `HeterotypicBoundaryLengthWriter` **is** bound. Shows no abstract bases in the module namespace. |
| `probe3.py` | Exhaustive: only 2 names containing "Abstract" are exported, both test suites. The only bound `*SwitchingUpdateRule` is `RandomCaSwitchingUpdateRule` — the paper's `DifferentialAdhesionCaSwitchingUpdateRule` has no mainline equivalent. |
| `probe4.py` | The abstract bases **do** exist, reachable via MRO as `AbstractForce_2_2` etc. in `chaste._pychaste_all`. A Python subclass of `AbstractForce_2_2` **instantiates**. `AbstractCaSwitchingUpdateRule_2` does **not** — "No constructor defined" → CA's switching rule is not subclassable. |
| `probe5.py` | Instantiating ≠ working. A Python-defined force in a real `Solve()` fails: `Unable to convert std::shared_ptr<T> to Python when the bound type does not use std::shared_ptr or py::smart_holder as its holder type`. |
| `probe6.py` | **The decisive control.** A mainline-only sim solves cleanly; an identical sim with a *no-op* Python force that never touches its argument fails the same way. The fault is trampoline argument marshalling, not user code. **Python-subclassed forces are unusable in this image.** |

## Consequences

- **`RandomMotionForce` cannot be ported as a Python subclass.** OS, VT and VM
  sorting all need it. Mainline `DiffusionForce` is algebraically identical
  (`F = ν·sqrt(2·(scaling/radius)·dt)/dt·ξ` vs `F = sqrt(2·D·dt)/dt·ξ`) and
  coincides when ν = 1 and `scaling = D·radius`. Study `cbc-03` tests that
  substitution rather than assuming it.
- **CA is blocked** on `DifferentialAdhesionCaSwitchingUpdateRule`. Unblocking it
  means a custom PyChaste image with correct pybind holder types — which would
  also fix the trampoline and thus `RandomMotionForce`.
- **CP, OS, VT, VM are reachable** with mainline classes only.

## Round 2 — API discovery (probes 7-9)

| Probe | What it establishes |
|---|---|
| `probe7.py` | `rGetCells()` is **not** bound; `CellsGenerator.GenerateBasicRandom` returns a plain Python `list` of `Cell`, and `AddCellProperty` works on them. `SetupNotebookTest()` must precede cell generation or `Cell` throws "SimulationTime has not been set up". |
| `probe8.py` | The metric writer **is attachable** — both the generic `AddPopulationWriter(instance)` and the name-mangled `AddPopulationWriterHeterotypicBoundaryLengthWriter()` work. (Probe 7's method filter hid the generic form; it was never actually missing.) |
| `probe9.py` | `NodesOnlyMesh` default node radius is 0.5 and honeycomb spacing is 1.0 → neighbours exactly **tangent** (`2r - d = 0.0000`), so the OS shared-edge chord is zero-length. Explains the ~1e-7 lengths in the OS spike output. |

## `spike_sorting.py` (in `studies/cbc-02-.../spikes/`)

Builds the paper's CP/OS/VT/VM sorting configuration and runs each briefly.
**Result: all four construct and emit `heterotypicboundary.dat`** using mainline
classes only. Raw output archived alongside it under `spikes/raw/`.

Caveat worth remembering: `%.4f` renders the OS lengths (~3e-7) as `0.0000`,
which looks like a failure and is not. Read the raw `.dat`, not a formatted print.
