# Contributing to pbg-chaste

## Development setup

uv is required. Install with `brew install uv` or `pip install uv`.

    uv venv .venv
    source .venv/bin/activate
    uv pip install -e ".[dev]"
    pytest

### Running the real engine

Chaste runs inside the official container. Once:

    docker pull --platform linux/amd64 chaste/pychaste

and make sure a Docker daemon is up (`colima start` if you use colima). Tests
that drive the real engine skip automatically when Docker or the image is
absent, so the suite stays green without it.

Under amd64 emulation on Apple Silicon the container works but is slow; keep
mesh sizes and end-times small. The wrapper forces single-threaded BLAS/OMP and
disables thread affinity (see `pbg_chaste/runtime.EMULATION_ENV`) to dodge an
OpenMP topology segfault under emulation.

## Architecture notes (learned from the live PyChaste build)

- No simulation archiver is exposed, so a `ChasteSession` keeps one resident
  container and steps the in-memory simulator via file IPC.
- Cells are a plain Python `list`; use the returning `GenerateBasicRandom`
  overload. `SimulationTime` must be set up (`SetupNotebookTest()`) first.
- Manually-built cells (needed for the Delta-Notch SRN) segfault unless the
  Python cell-cycle / SRN objects are kept alive — the server stashes them.
- `TearDownNotebookTest` segfaults after a real run; extract state first.
- `vertex + delta_notch` needs Chaste's edge-based SRN framework (a
  `DeltaNotchEdgeSrnModel` per cell edge). Building those requires
  `mesh.GetElement(i)` to enumerate edges, but this PyChaste build does not
  register `VertexElement<2,2>` to Python — so it is blocked upstream, not just
  unwired. If a future PyChaste exposes VertexElement, wire it in
  `_chaste_server._make_delta_notch_cells` behind a `population == "vertex"`
  branch using `CellSrnModel.AddEdgeSrn` + `DeltaNotchEdgeTrackingModifier2`.

## Releasing to PyPI

Tag a commit with `git tag v<VERSION>` and push the tag. The
`.github/workflows/release.yml` workflow publishes to PyPI automatically using
trusted publishing (no tokens needed after initial setup).

PyPI trusted publishing must be configured once per repo. See
https://docs.pypi.org/trusted-publishers/.
