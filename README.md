# Shoulder Rest

## Parts
This is a build123d project for a 3D-printed violin shoulder rest. The shoulder casts can be imported and positioned; the remaining components below are planned.

### Leg Housing
This is a part that connects the Kun leg (a rubber foot attached to a machine screw) to the rest. It has a hole for a metal rod which slots into the rest body. It also has holes for holding a nut and for the leg screw into.

### Rest Body
This is the main part defining the shoulder rest body. It is roughly a bar shape curved something like an S. The top of the bar has a complex contour to fit the player body, whereas the bottom facing the violin is totally flat for better printing.

### Violin Outline
This is a sketch of a tracing of the violin, with a small offset. In the modelling of the Rest Body, the center of the holes for the Kun legs are constrained to sit on this curve. 

### Shoulder Model
This is a part created by a different project that is loaded here. It is a model of the violin player's shoulder/collarbone area where the rest sits. This is used to cut out the contour of the Rest Body on the face contacting the player. 

`load_shoulder()` returns the `Shoulder` interface: `reference` and `extended` provide independent shapes for modeling, `assembly` contains the reference cast for display, and `violin_joint` is a rigid attachment named `violin`. The extended cast is a cutting tool and is excluded from the assembly.

```python
from shoulder_rest.parts.shoulder import Shoulder, load_shoulder

shoulder: Shoulder = load_shoulder()
cutting_tool = shoulder.extended
# shoulder.violin_joint.connect_to(violin.joints["shoulder"])
```

The bundled STEP files and their loading are hidden by `load_shoulder()`. For other casts, use `StepShoulder(reference_file, extended_file, cast_location=..., violin_location=...)` with build123d `Location` objects. The cast location reorients both files together; the violin location is defined in the corrected shoulder frame, so the cast transform is not applied to it again.

Adjust `POSITION` / `ROTATION` and `VIOLIN_POSITION` / `VIOLIN_ROTATION` in `src/shoulder_rest/parts/shoulder.py` for the bundled example. Position the completed shoulder with `shoulder.assembly.locate(...)`; retrieve tool shapes afterward to get their current world placement. Connect joints before nesting assemblies. With OCP CAD Viewer open, preview both casts and the joint using:

```powershell
uv run python -m shoulder_rest.parts.shoulder
```

## Project Guidelines
Keep parts modular and parameterizable, with readable, idiomatic build123d code. Use classes and build123d base classes where appropriate. Model dimensions are in millimeters.

## Tooling
Use Python 3.12 and [uv](https://docs.astral.sh/uv/) to install the locked environment:

```powershell
uv sync --locked
```

This creates `.venv` and installs build123d, this package, and the `ocp-vscode` development dependency. Commit `uv.lock` to keep installations reproducible. Add runtime dependencies with `uv add` and development tools with `uv add --dev`.

In VS Code, select `.venv/Scripts/python.exe` as the Python interpreter and install the OCP CAD Viewer extension. Start its viewer, then use `from ocp_vscode import show` and `show(part)` in a preview script. Keep viewer calls outside reusable model code. Run scripts with `uv run python path/to/script.py`; environment activation is optional.

Check the CAD environment without opening the viewer:

```powershell
uv run python -c "from build123d import Box; print(Box(10, 20, 30).volume)"
```

The expected volume is approximately `6000` cubic millimeters.

## Layout

- `src/shoulder_rest/parts/`: reusable part and sketch modules.
- `src/shoulder_rest/assets/`: model input geometry bundled in the package, loaded with `importlib.resources`.
- `assets/`: optional reference material that is not bundled in the package.
- `exports/`: generated STEP/STL files; contents are ignored by Git.
- `changelog/`: optional change history.
