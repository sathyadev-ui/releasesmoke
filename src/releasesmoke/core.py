"""Install a built wheel into a clean environment and check that it works.

The whole point of this module is that the checks run somewhere your source
tree is NOT importable. A test suite run from the project root imports your
source directory, not the artifact you are about to publish, so packaging
mistakes (a subpackage left out of the wheel, missing package data) pass every
green CI run and only surface after upload.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from dataclasses import dataclass
from pathlib import Path

__all__ = ["Result", "run_checks"]


@dataclass
class Result:
    """Outcome of a single check."""

    check: str
    ok: bool
    detail: str = ""


def _venv_python(root: Path) -> Path:
    """Path to the interpreter inside a created virtual environment."""
    if sys.platform == "win32":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def _last_line(text: str) -> str:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _find_uv() -> str | None:
    """Path to the uv executable, if it is installed."""
    return shutil.which("uv")


def _create_env(
    env_dir: Path, wheel: Path, uv: str | None
) -> tuple[Path, subprocess.CompletedProcess]:
    """Create a clean environment and install `wheel` into it.

    uv creates environments several times faster than the stdlib `venv`
    module, so it is used when present. The checks that follow are identical
    either way: only the setup speed differs.

    A uv environment ships no pip, so installation goes through
    `uv pip install --python`. If uv cannot create the environment at all we
    fall back to the stdlib rather than failing, since that is uv's problem
    and not the wheel's. An install failure is reported as-is, because that
    one really is about the wheel.
    """
    if uv is not None:
        try:
            created = subprocess.run(
                [uv, "venv", str(env_dir)], capture_output=True, text=True
            )
        except OSError:
            # uv vanished between detection and use, or cannot be executed.
            created = None
        if created is not None and created.returncode == 0:
            py = _venv_python(env_dir)
            install = subprocess.run(
                [uv, "pip", "install", "--quiet", "--python", str(py), str(wheel)],
                capture_output=True,
                text=True,
            )
            return py, install
        # uv is present but unusable here; fall through to the stdlib.

    venv.create(env_dir, with_pip=True)
    py = _venv_python(env_dir)
    install = subprocess.run(
        [str(py), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", str(wheel)],
        capture_output=True,
        text=True,
    )
    return py, install


def _check_imports(py: Path, cwd: Path, imports: list[str]) -> list[Result]:
    results = []
    for module in imports:
        proc = subprocess.run(
            [str(py), "-c", f"import {module}"],
            capture_output=True,
            text=True,
            # Critical: run from a scratch directory, NOT the project root.
            # Otherwise the source tree lands on sys.path and every import
            # passes whether or not it made it into the wheel.
            cwd=cwd,
        )
        ok = proc.returncode == 0
        results.append(
            Result(f"import {module}", ok, "" if ok else _last_line(proc.stderr))
        )
    return results


def _check_commands(py: Path, env_dir: Path, cwd: Path, commands: list[str]) -> list[Result]:
    results = []
    bin_dir = _venv_python(env_dir).parent
    for command in commands:
        try:
            # shlex.split honours quoting, so a command such as
            #   mytool --name "two words"
            # is passed as one argument rather than two.
            parts = shlex.split(command)
        except ValueError as exc:
            results.append(Result(f"command {command}", False, f"could not parse: {exc}"))
            continue
        if not parts:
            results.append(Result(f"command {command}", False, "empty command"))
            continue
        exe = bin_dir / parts[0]
        if sys.platform == "win32" and not exe.exists():
            exe = exe.with_suffix(".exe")
        if not exe.exists():
            results.append(
                Result(f"command {command}", False, f"console script not installed: {parts[0]}")
            )
            continue
        proc = subprocess.run(
            [str(exe), *parts[1:]], capture_output=True, text=True, cwd=cwd
        )
        ok = proc.returncode == 0
        detail = "" if ok else f"exited {proc.returncode}: {_last_line(proc.stderr or proc.stdout)}"
        results.append(Result(f"command {command}", ok, detail))
    return results


def _check_files(wheel: Path, files: list[str]) -> list[Result]:
    with zipfile.ZipFile(wheel) as zf:
        names = set(zf.namelist())
    results = []
    for expected in files:
        ok = expected in names
        results.append(
            Result(f"file {expected}", ok, "" if ok else "not present in wheel")
        )
    return results


def run_checks(
    wheel: Path,
    imports: list[str] | None = None,
    commands: list[str] | None = None,
    files: list[str] | None = None,
    use_uv: bool | None = None,
) -> list[Result]:
    """Install `wheel` in a throwaway venv and run the configured checks."""
    imports = imports or []
    commands = commands or []
    files = files or []

    results: list[Result] = []

    # Wheel contents can be inspected without installing anything.
    results.extend(_check_files(wheel, files))

    if not imports and not commands:
        return results

    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        env_dir = tmp / "env"
        scratch = tmp / "scratch"
        scratch.mkdir()

        uv = None if use_uv is False else _find_uv()
        py, install = _create_env(env_dir, wheel, uv)
        if install.returncode != 0:
            results.append(Result("install", False, _last_line(install.stderr)))
            return results
        results.append(Result("install", True))

        results.extend(_check_imports(py, scratch, imports))
        results.extend(_check_commands(py, env_dir, scratch, commands))

    return results
