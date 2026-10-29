# releasesmoke

**Status: early development. The three checks below work; not yet on PyPI — install from source. See [Roadmap](#roadmap).**

Your tests pass. Your wheel builds. You publish. An hour later someone opens an issue:

```
ModuleNotFoundError: No module named 'myproject.templates'
```

The module is right there in your source tree. It just isn't in the wheel.

This is the gap `releasesmoke` is meant to close: **your test suite runs against your source tree, not against the artifact your users install.** Packaging bugs slip through every green CI run, because CI never installs the thing it just built.

## What it does

Before you publish, `releasesmoke` installs your built wheel into a clean virtual environment — no source directory on the path, no dev dependencies — and checks that it actually works:

1. **Imports.** Every module you list can be imported from the installed package.
2. **Console scripts.** Declared entry points exist and run (`mytool --help` exits 0).
3. **Package data.** Files you expect to ship (templates, schemas, default configs) are present on disk after install.

If any of that fails, you find out before the upload, not after.

## Why not an existing tool

There are good tools in this space and you may already want them:

- [`twine check`](https://twine.readthedocs.io/) validates metadata, not behaviour.
- [`check-wheel-contents`](https://github.com/jwodder/check-wheel-contents) inspects the wheel's file list without installing it.
- [`cibuildwheel`](https://cibuildwheel.pypa.io/) builds and tests wheels across many platforms, aimed mainly at compiled extensions.

`releasesmoke` is narrower on purpose: a pure-Python project, one config block, one command, one readable failure report. If you need a build matrix across 30 targets, use `cibuildwheel`.

## Usage

Install from source (there is no PyPI release yet):

```bash
pip install git+https://github.com/sathyadev-ui/releasesmoke
```

Configure the checks in your `pyproject.toml`:

```toml
[tool.releasesmoke]
imports = ["myproject", "myproject.cli"]
commands = ["mytool --help"]
files = ["myproject/templates/base.html"]
```

Then build and check:

```bash
python -m build
releasesmoke dist/myproject-1.2.0-py3-none-any.whl
```

It exits non-zero when a check fails, so it stops a release in CI:

```
  PASS  install
  PASS  import myproject
  FAIL  import myproject.templates
        ModuleNotFoundError: No module named 'myproject.templates'

1 check(s) failed - do not publish this wheel.
```

If [uv](https://github.com/astral-sh/uv) is installed it is used to build the
throwaway environment, which takes a run from roughly 4 seconds to under half a
second. Nothing needs configuring, and the checks are identical either way.
Pass `--no-uv` to force the stdlib `venv` module.

## Roadmap

- [x] Clean-venv install and import checks
- [x] Console-script checks
- [x] Package-data checks
- [ ] GitHub Actions example workflow others can copy
- [ ] First release on PyPI

## Contributing

Issues and ideas are welcome, particularly from maintainers who have shipped a broken release and remember how it happened. If you have a packaging failure that a tool like this would have caught, open an issue describing it  - real failure cases shape what gets built first.

## License

MIT — see [LICENSE](LICENSE).
