# Shoulder Rest

## Parts
This is a build123d project for a 3D-printed violin shoulder rest. The shoulder casts, violin outline, and hinge-slot leg housing are implemented; the rest body is planned.

### Leg Housing
This is a part that connects the Kun leg (a rubber foot attached to a machine screw) to the rest. It has a hole for a metal rod which slots into the rest body. It also has holes for holding a nut and for the leg screw into.

`build_hinge_leg()` implements the `Leg` interface: `assembly` contains the printable `part` and a 2 × 20 mm metal rod, `tool` cuts its cavity and rod insertion slots, and `housing` shows the surrounding material to retain. Position the assembly; use `part` alone for printing.

`LegParameters(rod=RodParameters(...), kun=KunParameters(...))` separates stock hardware from the printed body's dimensions. Bore and cavity clearances are added to the rod dimensions. Reusable Kun screw-hole and nut-slot faces, with their own parameters, live in `shoulder_rest.parts.kun`.

```python
from shoulder_rest.parts.leg import Leg, build_hinge_leg

leg: Leg = build_hinge_leg()
installed = leg.install(rest.joints["leg_mount"], joint_label="left_leg")
rest = installed.rest  # New cut solid; existing rest joints are preserved.
rest.joints["left_leg"].connect_to(installed.rod_joint, angle=15)
# Include rest and installed.leg (printed body + metal rod) in the final assembly.
```

The rest's rigid mount matches the center of the nut-seat edge. Mount X follows the hinge rod; mount Z points into the rest. Complete all installations before connecting assembly joints, using joints from the latest returned rest. Neither the input rest nor the leg template is modified. See [the leg spec](specs/leg_spec.md) for placement and repeated installations. Preview the assembly and tools with `uv run python -m shoulder_rest.parts.leg`.

### Rest Body
This is the main part defining the shoulder rest body. It is roughly a bar shape curved something like an S. The top of the bar has a complex contour to fit the player body, whereas the bottom facing the violin is totally flat for better printing.

### Violin Outline
This is a sketch of a tracing of the violin, with a small offset. In the modelling of the Rest Body, the center of the holes for the Kun legs are constrained to sit on this curve. 

`SplineViolinOutline` implements the `ViolinOutline` interface with mirrored outlines, inward attachment curves, and a 38 mm visualization block. Choose points on the attachment curves to define a parametric guide:

```python
from build123d import Polyline
from shoulder_rest.parts.violin_outline import build_violin_outline, ViolinOutline

violin: ViolinOutline = build_violin_outline(attachment_offset=3.0)
guide = Polyline(
    violin.attachment_point("left", 0.25),
    (0, 10),
    violin.attachment_point("right", 0.60),
)
```

Fractions measure arc length from the lower-Y end (0) to the upper-Y end (1). Rebuild the guide when parameters change. Curves stay in local XY while `violin.block` can be positioned through its `shoulder` joint; the block extends toward +Z. See [the spec](specs/violin_outline_spec.md) for frame conventions. Preview with `uv run python -m shoulder_rest.parts.violin_outline`.

`violin.mount_location` is the shared local attachment frame at the midpoint of the upper-Y closing line: `(0, 73.536, 0)` for the bundled tracing, with the outline's XYZ axes. The block's `shoulder` joint uses this frame. A rest modeled in the same local coordinate system can define its joint with `violin.add_mount_joint(rest)`; the default joint name is `violin`.

For an assembly with the shoulder fixed, give the rest an optional joint offset and connect both parts:

```python
from build123d import Location

# rest is a Solid or Compound built in the outline's local frame.
rest_joint = violin.add_mount_joint(rest, offset=Location((0, 0, 12)))
shoulder.violin_joint.connect_to(violin.block.joints["shoulder"])
violin.block.joints["shoulder"].connect_to(rest_joint)
```

The offset changes the rest's joint relative to the shared frame. A +12 mm Z offset positions the rest 12 mm toward -Z relative to the violin, preserving its XY alignment; zero offset gives identical placements. Rotational offsets can model tilt about the mount point. Connect before nesting assemblies. The same rest joint can instead connect directly to `shoulder.violin_joint`.

### Shoulder Model
This is a part created by a different project that is loaded here. It is a model of the violin player's shoulder/collarbone area where the rest sits. This is used to cut out the contour of the Rest Body on the face contacting the player. 

`load_shoulder_cast()` returns the `Shoulder` interface: `reference` and `extended` provide independent shapes for modeling, `assembly` contains the reference cast for display, and `violin_joint` is a rigid attachment named `violin`. The extended cast is a cutting tool and is excluded from the assembly.

```python
from build123d import Location
from shoulder_rest.parts.shoulder import Shoulder, load_shoulder_cast

shoulder: Shoulder = load_shoulder_cast(
    cast_location=Location((0, 0, 0), (30, 30, -5)),
    violin_location=Location((0, 0, 20)),
)
violin.block.joints["shoulder"].connect_to(shoulder.violin_joint)
cutting_tool = shoulder.extended
```

The bundled STEP files and their loading are hidden by `load_shoulder_cast()`. For other casts, use `StepShoulder(reference_file, extended_file, cast_location=..., violin_location=...)` with build123d `Location` objects. The cast location reorients both files together; the violin location is defined in the corrected shoulder frame, so the cast transform is not applied to it again.

Adjust the `cast_location` and `violin_location` arguments in the main section of `src/shoulder_rest/parts/shoulder.py` for the bundled example. Position the completed shoulder with `shoulder.assembly.locate(...)`; retrieve tool shapes afterward to get their current world placement. Connect joints before nesting assemblies. With OCP CAD Viewer open, preview both casts and the joint using:

```powershell
uv run python -m shoulder_rest.parts.shoulder
```

## Project Guidelines
Keep parts modular and parameterizable, with readable, idiomatic build123d code. Use classes and build123d base classes where appropriate. Model dimensions are in millimeters.

Use `BuildLine`, `BuildSketch`, and `BuildPart` for procedural geometry. Reusable geometry helpers use private builders and return local shapes for explicit insertion; assembly placement and joint connections use direct shape operations.

Prioritize readable construction: compose recognizable shapes and use symmetry where it expresses the design clearly. Keep coordinate-heavy outlines for geometry that needs them, and name dimensions by their role in the part. Add tags only when a concrete downstream use benefits from them; prefer capturing geometry during construction when that simplifies later selection.

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
