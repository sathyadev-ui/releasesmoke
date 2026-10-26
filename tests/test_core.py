"""End-to-end tests: build the example package and check releasesmoke's verdict."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from releasesmoke.core import run_checks

EXAMPLE = Path(__file__).parent.parent / "examples" / "broken_pkg"


def build_wheel(project: Path) -> Path:
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel"],
        cwd=project,
        check=True,
        capture_output=True,
    )
    return next((project / "dist").glob("*.whl"))


@pytest.fixture(scope="module")
def broken_wheel(tmp_path_factory) -> Path:
    project = tmp_path_factory.mktemp("broken") / "pkg"
    shutil.copytree(EXAMPLE, project)
    return build_wheel(project)


@pytest.fixture(scope="module")
def fixed_wheel(tmp_path_factory) -> Path:
    project = tmp_path_factory.mktemp("fixed") / "pkg"
    shutil.copytree(EXAMPLE, project)
    pyproject = project / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text().replace(
            'packages = ["brokenpkg"]', 'packages = ["brokenpkg", "brokenpkg.extra"]'
        )
    )
    return build_wheel(project)


def test_missing_subpackage_is_caught(broken_wheel: Path) -> None:
    results = run_checks(broken_wheel, imports=["brokenpkg", "brokenpkg.extra"])
    by_check = {r.check: r for r in results}

    assert by_check["install"].ok
    assert by_check["import brokenpkg"].ok
    assert not by_check["import brokenpkg.extra"].ok
    assert "ModuleNotFoundError" in by_check["import brokenpkg.extra"].detail


def test_fixed_package_passes(fixed_wheel: Path) -> None:
    results = run_checks(fixed_wheel, imports=["brokenpkg", "brokenpkg.extra"])
    assert all(r.ok for r in results), [r for r in results if not r.ok]


def test_console_script_runs(fixed_wheel: Path) -> None:
    results = run_checks(fixed_wheel, commands=["brokentool --help"])
    assert all(r.ok for r in results), [r for r in results if not r.ok]


def test_missing_file_is_reported(broken_wheel: Path) -> None:
    results = run_checks(broken_wheel, files=["brokenpkg/templates/base.html"])
    assert len(results) == 1
    assert not results[0].ok


def test_quoted_argument_is_one_argument(fixed_wheel: Path) -> None:
    """A quoted value must reach the command as a single argument.

    With a naive command.split() this fails: argparse receives '"two' and
    'words"' as separate tokens and exits non-zero.
    """
    results = run_checks(fixed_wheel, commands=['brokentool --name "two words"'])
    assert all(r.ok for r in results), [r for r in results if not r.ok]


def test_unbalanced_quote_is_reported(fixed_wheel: Path) -> None:
    results = run_checks(fixed_wheel, commands=['brokentool --name "unclosed'])
    command_results = [r for r in results if r.check.startswith("command ")]

    assert len(command_results) == 1
    assert not command_results[0].ok
    assert "could not parse" in command_results[0].detail
