# pbg-chaste

<!-- BEGIN dashboard -->
> ## 🔬 [Read-only workbench →](https://vivarium-collective.github.io/pbg-chaste/dashboard/)
>
> **The full vivarium-workbench, live in your browser — no install.** Every investigation, study, composite and simulation, browsable with no server. Prefer a written write-up? See the [investigation reports](https://vivarium-collective.github.io/pbg-chaste/). Auto-published from `main` on every merge.
<!-- END dashboard -->

Process-bigraph wrapper for **[Chaste](https://github.com/Chaste/Chaste)** — the
Cancer, Heart And Soft Tissue Environment simulator. It exposes Chaste's
**multi-cellular** population methods and **sub-cellular** cell-cycle models as a
single parametrized process-bigraph `Process`, composable inside any larger
bigraph. It reimplements nothing — the real Chaste C++ engine runs inside the
official `chaste/pychaste` Docker image (Docker is the only host requirement).

## Explore — no install

| | |
|---|---|
| **[🔬 Read-only workbench](https://vivarium-collective.github.io/pbg-chaste/dashboard/)** | The full vivarium-workbench as a static site: Sources · Registry · Composites · Investigations · Simulations DB · Analyses. |
| **[📄 Investigation — reproducing Osborne et al. 2017](https://vivarium-collective.github.io/pbg-chaste/investigations/cellbased-comparison-2017.html)** | The cell-sorting case study reproduced and checked, model by model, against the authors' [own C++ code](https://github.com/Chaste/CellBasedComparison2017). Four of five model classes match to **Pearson r 0.93–0.999**; CA is documented as out of reach of the Python bindings. |
| **[▶ Demo report](https://vivarium-collective.github.io/pbg-chaste/)** | Real Chaste runs across the population × cell-cycle matrix, with play/pause cell-shape animations, growth curves, and interactive bigraph diagrams. |

## What it wraps

Chaste couples a **population geometry method** with a **per-cell cycle model**
inside one simulation. `pbg-chaste` surfaces both axes as config on a single
`ChasteSimulationProcess`:

| Axis | Choices | Chaste machinery |
|---|---|---|
| **Multi-cellular** (`population`) | `mesh` · `vertex` · `node` | `MeshBasedCellPopulation` + `GeneralisedLinearSpringForce`; `VertexBasedCellPopulation` + `NagaiHondaForce` + `SimpleTargetAreaModifier`; `NodeBasedCellPopulation` (`NodesOnlyMesh`) + `GeneralisedLinearSpringForce` |
| **Sub-cellular** (`cell_cycle`) | `uniform` · `stochastic` · `tyson_novak` · `delta_notch` | Uniform / StochasticDuration cell-cycle models; Tyson–Novak ODE; Delta–Notch ODE reaction network (neighbour-coupled via `DeltaNotchTrackingModifier`) |

11 of the 12 combinations run on the real engine. `vertex + delta_notch` is
blocked upstream (it needs Chaste's edge-based SRN framework, and this PyChaste
build doesn't expose `VertexElement<2,2>` to Python); constructing it raises a
clear `NotImplementedError`.

A second process, `ChasteCellSortingProcess`, reproduces the Osborne et al. 2017
differential-adhesion cell-sorting study for the four reachable model classes
(CP, OS, VT, VM) — see the investigation workbench above.

## Install & run

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
docker pull --platform linux/amd64 chaste/pychaste   # the real engine, once
```

The process registers automatically via `bigraph_schema.package.discover` — no
manual `register_link()`.

```python
from process_bigraph import Composite, allocate_core
from pbg_chaste.composites import mesh_delta_notch

core = allocate_core()
sim = Composite({"state": mesh_delta_notch(core)}, core=core)
sim.run(4.0)
```

On Apple Silicon the amd64 image runs under Rosetta/QEMU emulation (correct, but
keep meshes small); native amd64 hosts run at full speed. Overrides:
`PBG_CHASTE_IMAGE`, `PBG_CHASTE_PLATFORM` (default `linux/amd64`),
`PBG_CHASTE_RUN_ROOT` (default `<repo>/_chaste_runs`).

## How it works

This PyChaste build ships no archiver, so state can't be saved/reloaded between
`docker run` invocations. Instead the wrapper keeps **one resident container**
holding the simulator in memory and steps it over a tiny file-based
command/response protocol — Chaste resumes across repeated `SetEndTime` +
`Solve` calls, giving genuine per-interval stepping with live inputs. Every
number comes from the real solver.

`ChasteSimulationProcess` ports: input `spring_stiffness` (live mechanical
stiffness); outputs `num_cells` (delta, composes additively), `positions`,
`phase_counts`, and `mean_delta` / `mean_notch` (delta_notch only). Config:
`population`, `cell_cycle`, `width`, `height`, `spring_cutoff`,
`sampling_multiple`, `seed`, `timeout`, `start_timeout`.

## Reproducing this locally

```bash
scripts/serve.sh                    # run the interactive workbench (needs vivarium-workbench)
scripts/publish_dashboard.sh /tmp/dash && python -m http.server -d /tmp/dash 8080   # preview the read-only build
```

## License

BSD-3-Clause (matching Chaste). Chaste itself is © the Chaste authors — see the
[upstream repo](https://github.com/Chaste/Chaste).
