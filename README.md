# pbg-chaste

Process-bigraph wrapper for **[Chaste](https://github.com/Chaste/Chaste)** —
the Cancer, Heart And Soft Tissue Environment simulator. This package exposes
Chaste's **multi-cellular** simulation methods and **sub-cellular** cell-cycle
models as a single, parametrized process-bigraph `Process`, so you can compose
any *sub-cellular × multi-cellular* combination and run it inside a larger
bigraph.

The wrapper drives the **real Chaste C++ engine** — it does not reimplement
any of Chaste's mechanics or ODEs. Chaste is notoriously hard to build from
source (PETSc, VTK, HDF5, Boost, a long CMake build), so this package runs the
genuine engine through the **official `chaste/pychaste` Docker image**
(PyChaste = Python bindings over the same C++ library). Docker is the only host
requirement.

## What it wraps

Chaste couples a **population geometry method** with a **per-cell cycle model**
inside one `OffLatticeSimulation`. `pbg-chaste` surfaces both axes as config on
a single `ChasteSimulationProcess`:

| Axis | Choices | Chaste machinery |
|---|---|---|
| **Multi-cellular** (`population`) | `mesh` · `vertex` · `node` | `MeshBasedCellPopulation` + `GeneralisedLinearSpringForce`; `VertexBasedCellPopulation` + `NagaiHondaForce` + `SimpleTargetAreaModifier`; `NodeBasedCellPopulation` (`NodesOnlyMesh`) + `GeneralisedLinearSpringForce` |
| **Sub-cellular** (`cell_cycle`) | `uniform` · `stochastic` · `tyson_novak` · `delta_notch` | Uniform/StochasticDuration cell-cycle models; Tyson–Novak ODE model; Delta–Notch ODE sub-cellular reaction network (neighbour-coupled via `DeltaNotchTrackingModifier`) |

Any of the **3 × 4 = 12 combinations** is a valid simulation. The dashboard
Composites tab exposes a matrix of `@composite_generator` variants covering
them.

## Installation

```bash
# From PyPI (once published):
pip install pbg-chaste

# For development (editable):
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

Once installed, the process registers automatically via
`bigraph_schema.package.discover` — no manual `register_link()` calls needed.

### Docker prerequisite (the real engine)

The Chaste engine runs inside a container. Pull the image once:

```bash
docker pull --platform linux/amd64 chaste/pychaste
```

On Apple Silicon the amd64 image runs under Rosetta/QEMU emulation — correct,
but keep demo meshes and end-times small. A native amd64 Linux host runs it at
full speed (`PBG_CHASTE_PLATFORM=linux/amd64` is the default; override if
needed). No Docker daemon running? Start one, e.g. `colima start`.

Environment overrides:

| Variable | Default | Purpose |
|---|---|---|
| `PBG_CHASTE_IMAGE` | `chaste/pychaste` | Image name/tag |
| `PBG_CHASTE_PLATFORM` | `linux/amd64` | `docker run --platform` |
| `PBG_CHASTE_RUN_ROOT` | `<repo>/_chaste_runs` | Bind-mounted scratch dir |

## Quick start

```python
from process_bigraph import Composite, allocate_core
from pbg_chaste.composites import mesh_delta_notch  # a generator

core = allocate_core()
sim = Composite({"state": mesh_delta_notch(core)}, core=core)
sim.run(4.0)
```

Or drive the process directly:

```python
from pbg_chaste import ChasteSimulationProcess

core = allocate_core()
proc = ChasteSimulationProcess(
    config={"population": "node", "cell_cycle": "stochastic",
            "width": 3, "height": 3},
    core=core,
)
delta = proc.update(proc.initial_state(), interval=1.0)
print(delta["num_cells"], "cell-count change over the interval")
```

## API reference

### `ChasteSimulationProcess`

| Port | Dir | Schema | Meaning |
|---|---|---|---|
| `spring_stiffness` | in | `float` | Live tissue mechanical stiffness applied each step (Meineke spring stiffness for mesh/node, Nagai–Honda deformation energy for vertex). A sibling controller can drive it; `<= 0` leaves Chaste's default. |
| `num_cells` | out | `integer` | **Delta** in cell count over the interval (composes additively). |
| `positions` | out | `overwrite[list[list[float]]]` | Current cell centroid coordinates (sensor snapshot). |
| `phase_counts` | out | `overwrite[map[string,float]]` | Cells per proliferative phase (phase-based cycle models only). |
| `mean_delta` / `mean_notch` | out | `overwrite[float]` | Sub-cellular Delta/Notch means (delta_notch model only; `0` otherwise). |

`config_schema`: `population`, `cell_cycle`, `width`, `height`,
`spring_cutoff` (node), `sampling_multiple`, `seed`, `timeout`, `start_timeout`.

Inputs are deltas/controls the surrounding bigraph writes *into* Chaste each
step; outputs are composable — cell-count is emitted as a delta so a sibling
division/death process can also contribute (see the process-bigraph Port Design
convention).

## Architecture

This PyChaste build exposes no simulation archiver, so state cannot be saved
and reloaded between separate `docker run` invocations. Instead the wrapper
keeps **one resident container** holding the simulator in memory and steps it
via a tiny file-based command/response protocol — Chaste resumes correctly
across repeated `SetEndTime` + `Solve` calls, giving genuine per-interval
stepping with live inputs.

```
ChasteSimulationProcess                       chaste/pychaste container
  first update() ─► ChasteSession.start() ──► build real OffLatticeSimulation
                                              (held in memory), write ready.json
  update(state, interval):
    write cmd_i.json {interval, stiffness} ─► apply stiffness to the live force
                                              SetEndTime(t+interval); Solve()
    read out_i.json  ◄───────────────────────  extract cells/positions/Delta/Notch
    emit num_cells delta + observables
  __del__ ─► STOP ─────────────────────────►  container exits
```

Nothing is reimplemented — every number comes from the real Chaste solver.

## Demo

```bash
python demo/demo_report.py   # writes + opens demo/report.html
```

The report runs several *sub-cellular × multi-cellular* combinations and shows
cell-count growth, spatial layouts, and (for delta_notch) the salt-and-pepper
Delta/Notch patterning, alongside an interactive bigraph diagram.

## Supported combinations

11 of the 12 population × cell-cycle combinations run on the real engine:

|            | uniform | stochastic | tyson_novak | delta_notch |
|------------|:-------:|:----------:|:-----------:|:-----------:|
| **mesh**   | ✅ | ✅ | ✅ | ✅ |
| **node**   | ✅ | ✅ | ✅ | ✅ |
| **vertex** | ✅ | ✅ | ✅ | ⛔ |

`vertex + delta_notch` is not supported: vertex Delta-Notch requires Chaste's
separate **edge-based SRN framework** — a `DeltaNotchEdgeSrnModel` per cell
edge — whereas the wrapper uses the Voronoi-neighbour `DeltaNotchSrnModel`
(valid for mesh/node). Building the per-edge SRNs means enumerating each
element's edges via `mesh.GetElement(i)`, but this PyChaste build does not
register `VertexElement<2,2>` to Python, so element edges are unreachable and
the combination is genuinely blocked upstream. Constructing it raises a clear
`NotImplementedError`; use `mesh`/`node` for Delta-Notch.

## Limitations

- Requires Docker; the engine is not a pip dependency.
- Under amd64 emulation on Apple Silicon, keep meshes small — large populations
  are slow. Native amd64 hosts have no such limit.
- One resident container per process; the first step pays the build cost.
- 2D populations in v1 (Chaste's `_2` template instantiations).
- `vertex + delta_notch` unsupported (see above).

## License

BSD-3-Clause (matching Chaste's license). Chaste itself is © the Chaste
authors; see the [upstream repo](https://github.com/Chaste/Chaste).
