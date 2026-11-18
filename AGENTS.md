# Project context

This is a Python CAD project using build123d, managed by uv. Read [README.md](README.md) for the public interfaces, modeling workflow, and setup. `Shoulder`, `ViolinOutline`, `Leg`, and `RestGeometry` feed `Rest`, which assembles a fitted rest. Read the docstrings of the modules involved before changing geometry or coordinate conventions.

## Modeling and code style

- Prioritize readability. Compose recognizable shapes, use symmetry, and name dimensions by their role. Use coordinate-heavy outlines only when the geometry needs them.
- Use `BuildLine`, `BuildSketch`, and `BuildPart` where appropriate for procedural construction. Use direct shape operations for placement and joint connections.
- Keep reusable geometry helpers isolated with private builders. Return local geometry for explicit insertion, without inheriting a caller's placement or modifying its active builder.
- Keep each part interface in its same-named subpackage/module (for example, `parts/leg/leg.py`), and concrete geometry in a separate implementation module (such as `hinge_leg.py`). Package `__init__.py` files expose interfaces only.
- Use a protocol only where implementations genuinely vary (legs). When every variant produces the same data, make the interface a concrete class or record and let builders, loaders, or design functions produce it.
- Construction never moves its inputs. Return geometry in a documented local frame and pass frames between builders as `Location`s. Use joints to mark attachment frames on finished parts and assemblies, and to position top-level assemblies through `position_on`.
- Keep parts modular and parameterizable. Rest implementations should consume the interfaces without knowing how geometry is constructed or loaded.
- Express dimensions in millimeters and angles in degrees. Document coordinate frames and offsets at interface boundaries.
- Add tags only for a concrete downstream use. Prefer capturing geometry during construction when that simplifies later selection; avoid speculative face-classification code.
- Keep viewer calls outside reusable model code, in preview scripts or module main sections.

## Files and dependencies

- Keep reusable code in `src/shoulder_rest/parts/`. The library ships no player-specific data or fitted constants: shoulder scans, violin placements and tuned rest parameters belong to the project that uses the library, and enter through parameters and loaders.
- Example data and scripts live in `examples/`. `examples/example_shoulder.py` loads an example scan for previews and tests; scripts there import it directly.
- Keep non-runtime references in `assets/` and generated exports in the ignored `exports/` directory.
- `shoulder_rest.render` is a development tool shared with downstream projects; it needs the `render` extra (VTK).
- Use `uv sync --locked` for the environment. Add runtime dependencies with `uv add` and development tools with `uv add --dev`; keep `pyproject.toml` and `uv.lock` consistent.

## Validation

Run `uv run python -m unittest discover -s tests`, `uv run mypy src tests examples` and `uv run ruff check .` for model changes. Keep a small set of smoke checks for interface construction and placement. Inspect evolving geometry in CAD previews. Without a viewer, `uv run python -m shoulder_rest.render <module or script>` renders a preview's `show` call to a PNG of standard views in `exports/renders/`; see its `--help` for hiding, ghosting and part-aligned views. Do not add geometry-preservation or reference-solid regression tests unless requested. Documentation-only changes need accurate API examples and links, not a CAD test run.

## Documentation

- Keep README.md focused on using the interfaces and assembling a rest. Put contributor instructions here. Record design rationale the code cannot show (sources, print and fit constraints, known limits) in the relevant module or class docstring, without restating parameter defaults.
- Keep documentation brief. README.md and code comments describe the current state, not the history of edits. Record change history in `changelog/` when useful.
