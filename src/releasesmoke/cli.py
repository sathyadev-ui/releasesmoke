"""Command line interface for releasesmoke."""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

from .core import Result, run_checks

__all__ = ["main"]


def load_config(pyproject: Path) -> dict:
    """Read the [tool.releasesmoke] table, if there is one."""
    if not pyproject.exists():
        return {}
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return data.get("tool", {}).get("releasesmoke", {})


def report(results: list[Result]) -> int:
    """Print results, return the number that failed."""
    failed = 0
    for r in results:
        if r.ok:
            print(f"  PASS  {r.check}")
        else:
            failed += 1
            print(f"  FAIL  {r.check}")
            if r.detail:
                print(f"        {r.detail}")
    return failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="releasesmoke",
        description="Install a built wheel in a clean environment and check that it works.",
    )
    parser.add_argument("wheel", type=Path, help="path to the built .whl file")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("pyproject.toml"),
        help="pyproject.toml holding [tool.releasesmoke] (default: ./pyproject.toml)",
    )
    parser.add_argument(
        "--no-uv",
        action="store_true",
        help="always use the stdlib venv module, even if uv is installed",
    )
    args = parser.parse_args(argv)

    if not args.wheel.exists():
        print(f"error: no such file: {args.wheel}", file=sys.stderr)
        return 2

    config = load_config(args.config)
    imports = config.get("imports", [])
    commands = config.get("commands", [])
    files = config.get("files", [])

    if not (imports or commands or files):
        print(
            f"error: no [tool.releasesmoke] configuration found in {args.config}",
            file=sys.stderr,
        )
        return 2

    print(f"Checking {args.wheel.name}")
    results = run_checks(
        args.wheel,
        imports=imports,
        commands=commands,
        files=files,
        use_uv=not args.no_uv,
    )
    failed = report(results)

    print()
    if failed:
        print(f"{failed} check(s) failed - do not publish this wheel.")
        return 1
    print(f"All {len(results)} checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
