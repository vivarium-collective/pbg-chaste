"""Docker-backed execution runtime for the real Chaste engine.

Chaste cannot be built natively on most laptops (it needs PETSc, VTK, HDF5,
Boost and a long CMake build). The sanctioned real-tool path is the official
``chaste/pychaste`` Docker image, which ships the genuine Chaste C++ library
exposed through its PyChaste Python bindings.

Because this PyChaste build exposes no simulation archiver, we cannot save and
reload a simulation between separate ``docker run`` invocations. Instead a
:class:`ChasteSession` keeps ONE long-lived container resident, holding the
simulator in memory, and steps it via a tiny file-based command/response
protocol against a bind-mounted work directory (see ``_chaste_server.py``).
Chaste resumes correctly across repeated ``SetEndTime`` + ``Solve`` calls, so
this yields genuine per-interval stepping with live inputs.

Nothing here reimplements any Chaste science — it only marshals a real
simulation in and its real observables out.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

#: Official image carrying the genuine Chaste C++ engine + PyChaste bindings.
CHASTE_IMAGE = os.environ.get("PBG_CHASTE_IMAGE", "chaste/pychaste")

#: The container images are published for linux/amd64; on Apple Silicon they
#: run under Rosetta/QEMU emulation. Overridable for native-amd64 hosts.
CHASTE_PLATFORM = os.environ.get("PBG_CHASTE_PLATFORM", "linux/amd64")

#: Environment forced into every container run. Chaste's OpenBLAS/OpenMP stack
#: segfaults querying CPU topology under Rosetta/QEMU emulation on Apple
#: Silicon ("OMP: Error #13 ... kmp_affinity"); pinning single-threaded BLAS/OMP
#: and disabling thread affinity avoids the crash. Harmless on native hosts.
EMULATION_ENV = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "GOTO_NUM_THREADS": "1",
    "OMP_DYNAMIC": "FALSE",
    "OMP_WAITPOLICY": "passive",
    "KMP_AFFINITY": "disabled",
}

#: Where per-run scratch (server script + IPC files + Chaste output) lives.
DEFAULT_RUN_ROOT = Path(
    os.environ.get(
        "PBG_CHASTE_RUN_ROOT",
        str(Path(__file__).resolve().parent.parent / "_chaste_runs"),
    )
)

_SERVER_SRC = (Path(__file__).resolve().parent / "_chaste_server.py").read_text()


class ChasteDockerError(RuntimeError):
    """Raised when the Chaste container is unavailable or a run fails."""


def _docker() -> str:
    exe = shutil.which("docker")
    if not exe:
        raise ChasteDockerError(
            "docker executable not found. Chaste runs inside the "
            "chaste/pychaste container; install Docker (or colima) first."
        )
    return exe


def docker_available() -> bool:
    """True if the docker daemon is reachable (server responds)."""
    try:
        exe = shutil.which("docker")
        if not exe:
            return False
        out = subprocess.run(
            [exe, "version", "--format", "{{.Server.Version}}"],
            capture_output=True, text=True, timeout=15,
        )
        return out.returncode == 0 and bool(out.stdout.strip())
    except Exception:
        return False


def image_present(image: str = CHASTE_IMAGE) -> bool:
    """True if the Chaste image is already pulled locally."""
    try:
        out = subprocess.run(
            [_docker(), "image", "inspect", image],
            capture_output=True, text=True, timeout=30,
        )
        return out.returncode == 0
    except Exception:
        return False


def chaste_ready(image: str = CHASTE_IMAGE) -> bool:
    """True when both the daemon is up and the Chaste image is available."""
    return docker_available() and image_present(image)


def new_run_dir(prefix: str = "run") -> Path:
    """Create a fresh scratch directory that will be bind-mounted at /work."""
    DEFAULT_RUN_ROOT.mkdir(parents=True, exist_ok=True)
    d = DEFAULT_RUN_ROOT / f"{prefix}-{uuid.uuid4().hex[:10]}"
    d.mkdir(parents=True)
    return d


class ChasteSession:
    """A resident Chaste container that steps a simulation on command.

    Usage::

        s = ChasteSession({"population": "mesh", "cell_cycle": "uniform",
                           "width": 4, "height": 4})
        initial = s.start()                  # builds the sim, returns state
        state = s.step(interval=1.0, stiffness=15.0)
        ...
        s.close()

    ``state`` dicts carry: num_cells, positions, phase_counts, mean_delta,
    mean_notch, time. All values come from the real Chaste solver.
    """

    def __init__(self, params: dict, *, image: str = CHASTE_IMAGE,
                 step_timeout: float = 120.0, start_timeout: float = 300.0):
        self.params = dict(params)
        self.image = image
        self.step_timeout = step_timeout
        self.start_timeout = start_timeout
        self.workdir: Path | None = None
        self.container: str | None = None
        self._i = 0
        self._t = 0.0

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> dict:
        if not docker_available():
            raise ChasteDockerError(
                "Docker daemon is not reachable. Start it (e.g. `colima start`)."
            )
        if not image_present(self.image):
            raise ChasteDockerError(
                f"Chaste image '{self.image}' not present. Pull it once:\n"
                f"    docker pull --platform {CHASTE_PLATFORM} {self.image}"
            )
        self.workdir = new_run_dir(
            prefix=f"{self.params.get('population','sim')}-"
                   f"{self.params.get('cell_cycle','cc')}"
        )
        (self.workdir / "params.json").write_text(json.dumps(self.params))
        (self.workdir / "server.py").write_text(_SERVER_SRC)

        env_args = []
        for k, v in EMULATION_ENV.items():
            env_args += ["-e", f"{k}={v}"]
        cmd = [
            _docker(), "run", "-d", "--rm", "--platform", CHASTE_PLATFORM,
            *env_args, "-v", f"{self.workdir}:/work", "-w", "/work",
            self.image, "python", "/work/server.py",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            raise ChasteDockerError(
                f"failed to start Chaste container: {proc.stderr.strip()}"
            )
        self.container = proc.stdout.strip()
        ready = self._await("ready.json", self.start_timeout)
        if not ready.get("ok"):
            self.close()
            raise ChasteDockerError(
                "Chaste sim failed to build:\n"
                + ready.get("error", "?") + "\n" + ready.get("tb", "")
            )
        self._t = ready["state"].get("time", 0.0)
        return ready["state"]

    def step(self, interval: float, stiffness: float | None = None) -> dict:
        if self.container is None:
            raise ChasteDockerError("session not started; call start() first")
        self._i += 1
        (self.workdir / f"cmd_{self._i}.json").write_text(
            json.dumps({"interval": float(interval), "stiffness": stiffness})
        )
        res = self._await(f"out_{self._i}.json", self.step_timeout)
        if not res.get("ok"):
            raise ChasteDockerError(
                f"Chaste step {self._i} failed:\n"
                + res.get("error", "?") + "\n" + res.get("tb", "")
            )
        self._t = res["state"].get("time", self._t + interval)
        return res["state"]

    def close(self):
        try:
            if self.workdir is not None:
                (self.workdir / "STOP").write_text("1")
        except Exception:
            pass
        if self.container:
            try:
                subprocess.run([_docker(), "stop", "-t", "2", self.container],
                               capture_output=True, text=True, timeout=30)
            except Exception:
                pass
            self.container = None

    # -- helpers ------------------------------------------------------------
    def _await(self, name: str, timeout: float) -> dict:
        path = self.workdir / name
        deadline = time.time() + timeout
        while time.time() < deadline:
            if path.exists():
                # written atomically via os.replace on the container side
                try:
                    return json.loads(path.read_text())
                except json.JSONDecodeError:
                    time.sleep(0.02)
                    continue
            if not self._container_alive():
                logs = self._container_logs()
                raise ChasteDockerError(
                    f"Chaste container exited before writing {name}.\n{logs}"
                )
            time.sleep(0.05)
        raise ChasteDockerError(
            f"timed out after {timeout:.0f}s waiting for {name} "
            "(reduce mesh size / end time, or raise the timeout)."
        )

    def _container_alive(self) -> bool:
        if not self.container:
            return False
        try:
            out = subprocess.run(
                [_docker(), "inspect", "-f", "{{.State.Running}}", self.container],
                capture_output=True, text=True, timeout=15,
            )
            return out.stdout.strip() == "true"
        except Exception:
            return False

    def _container_logs(self) -> str:
        if not self.container:
            return ""
        try:
            out = subprocess.run(
                [_docker(), "logs", "--tail", "40", self.container],
                capture_output=True, text=True, timeout=15,
            )
            return (out.stdout or "") + (out.stderr or "")
        except Exception:
            return ""

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.close()
