"""cbc-04: run the pbg-chaste ChasteCellSortingProcess at the paper's config and
collect each model's heterotypicboundary.dat for comparison against the cbc-01
C++ baseline.

Matches cbc-01: 20x20 tissue, relax to t=10, label 50%, run to t=110. The
HeterotypicBoundaryLengthWriter records the full trajectory into the run dir at a
1.0-hour sampling interval, so one Solve per model suffices — we reduce the .dat,
not per-step outputs. The engine is the same C++ Chaste as cbc-01, driven through
PyChaste, so runtime is comparable.

VT runs deterministically (no random-motion substitute — see cbc-02/cbc-03); its
trajectory is still recorded and compared, with the caveat noted.

Usage:  python run_pychaste_baseline.py [model ...]   (default: cp os vt vm)
Outputs: pychaste-baseline/<model>-heterotypicboundary.dat + a copy of the run dir.
"""
import glob
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "pychaste-baseline")

# per-model sampling multiple so the writer samples every 1.0 h, matching cbc-01
#   CP: dt 0.01 -> 100 steps/h ;  OS/VT/VM: dt 0.005 -> 200 steps/h
SAMPLING = {"cp": 100, "os": 200, "vt": 200, "vm": 200}


def run_model(model: str):
    from process_bigraph import allocate_core
    from pbg_chaste import ChasteCellSortingProcess

    print(f"=== {model.upper()} : building + relaxing (t=10) + labelling ===", flush=True)
    proc = ChasteCellSortingProcess(
        config={
            "model": model,
            "width": 20, "height": 20,
            "k_pert": 1.0,
            "relax_time": 10.0,
            "label_fraction": 0.5,
            "ghost_layers": 20,
            "sampling_multiple": SAMPLING[model],
            "seed": 0,
            "timeout": 7200.0, "start_timeout": 7200.0,
        },
        core=allocate_core(),
    )
    t0 = time.time()
    # one step to t=110 (100 h of sorting); the writer records the trajectory
    out = proc.update({}, interval=100.0)
    dt = time.time() - t0
    print(f"    {model}: solved to t=110 in {dt:.0f}s | cells={out['num_cells']} "
          f"labelled={out['num_labelled']} random_motion={out['random_motion']} "
          f"frac_end={out['fractional_length']:.4f}", flush=True)

    # locate the run dir the session used and copy its heterotypicboundary.dat
    run_root = os.environ.get(
        "PBG_CHASTE_RUN_ROOT",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(HERE))))), "_chaste_runs"),
    )
    hits = sorted(
        glob.glob(os.path.join(run_root, f"sort-{model}-*", "out", "**",
                               "heterotypicboundary.dat"), recursive=True),
        key=os.path.getmtime,
    )
    os.makedirs(OUTDIR, exist_ok=True)
    if hits:
        # merge all phase files into one (the reduction expects the pbg_sort_<model> layout)
        dest_dir = os.path.join(OUTDIR, f"pbg_sort_{model}", "merged")
        os.makedirs(dest_dir, exist_ok=True)
        # copy every phase file preserving its results_from_time_* parent
        src_run = hits[-1].split(os.sep + "out" + os.sep)[0]
        for f in glob.glob(os.path.join(src_run, "out", "**",
                                        "heterotypicboundary.dat"), recursive=True):
            phase = os.path.basename(os.path.dirname(f))
            pd = os.path.join(OUTDIR, f"pbg_sort_{model}", phase)
            os.makedirs(pd, exist_ok=True)
            shutil.copy(f, pd)
        print(f"    {model}: copied .dat files under {OUTDIR}/pbg_sort_{model}/", flush=True)
    else:
        print(f"    {model}: WARNING no heterotypicboundary.dat found under {run_root}", flush=True)

    try:
        proc.__del__()
    except Exception:
        pass


def main():
    models = sys.argv[1:] or ["cp", "os", "vt", "vm"]
    for m in models:
        run_model(m)
    print("=== cbc-04 pychaste baseline DONE ===", flush=True)


if __name__ == "__main__":
    main()
