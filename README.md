# Shoulder Rest

Parametric build123d models for a 3D-printed violin shoulder rest. The `Shoulder`, `ViolinOutline`, and `Leg` interfaces provide geometry and attachment frames for a rest implementation. `Rest` handles leg installation and assembly, with flat and shoulder-contoured rounded bars as starting bodies. Dimensions are in millimeters; angles are in degrees.

## Setup and previews

Use Python 3.12 and [uv](https://docs.astral.sh/uv/):

```powershell
uv sync --locked
```

This installs the package and its dependencies into `.venv`. In VS Code, select `.venv/Scripts/python.exe` and start the OCP CAD Viewer extension. Preview individual components with:

```powershell
uv run python -m shoulder_rest.parts.shoulder.step_shoulder
uv run python -m shoulder_rest.parts.violin_outline.spline_violin_outline
uv run python -m shoulder_rest.parts.leg.hinge_leg
uv run python -m shoulder_rest.parts.rest
uv run python -m shoulder_rest.parts.contoured_rest
```

## Interfaces for building a rest

### ViolinOutline: layout and shared attachment frame

`ViolinOutline` supplies local XY geometry for laying out the rest and its leg centers:

- `left` and `right`: violin outline curves.
- `left_attachment` and `right_attachment`: inward-offset curves for leg centers.
- `attachment_point(side, fraction)`: a point at a fraction of a curve's arc length, from its lower-Y end (0) to its upper-Y end (1).
- `block`: a positionable violin visualization.
- `position_on(shoulder)`: places the block at the shoulder's violin attachment.
- `mount_location`: the shared attachment frame at the midpoint of the outline's top (upper-Y) closing line, on Z=0.
- `add_mount_joint(rest, offset=...)`: adds a rigid joint named `violin` to a rest built in the outline's local frame.

Use sampled attachment points to define a parametric guide; rebuild it when parameters change:

```python
from build123d import Polyline
from shoulder_rest.parts.violin_outline import ViolinOutline
from shoulder_rest.parts.violin_outline.spline_violin_outline import build_violin_outline

violin: ViolinOutline = build_violin_outline(attachment_offset=3.0)
guide = Polyline(
    violin.attachment_point("left", 0.25),
    (0, 10),
    violin.attachment_point("right", 0.60),
)
```

The curves stay in local XY even when the block moves. The block and rest share the same attachment point in this plane. An optional joint offset represents spacing or tilt relative to the violin. See the [outline spec](specs/violin_outline_spec.md) for tracing and frame details.

### Shoulder: contact geometry and violin placement

`Shoulder` supplies `reference` geometry for inspection, an `extended` cutting tool for shaping the contact surface, and an `assembly` containing the reference cast for display. Its implementation defines where the violin sits; call `violin.position_on(shoulder)` to apply that placement.

Position the shoulder assembly before retrieving `reference` or `extended`: each is an independent snapshot at the current world placement. Use the extended shape in a Boolean cut after placing the rest in the same frame.

The bundled implementation in `shoulder_rest.parts.shoulder.step_shoulder` is loaded with `load_shoulder_cast(cast_location=..., violin_location=...)`. `cast_location` reorients both input casts; `violin_location` defines the joint in that corrected shoulder frame. File loading is hidden from rest implementations.

Position the violin against the shoulder, then position the complete rest:

```python
# rest is constructed from a RestGeometry and a leg template.
violin.position_on(shoulder)
rest.position_on(violin)
```

Positioning a completed rest moves its body and both legs together. The rest geometry defines its spacing and tilt relative to the violin.

### Leg: installation and final attachment

`Leg` provides a printable `part`, an `assembly` including its metal hardware, a cavity-cutting `tool`, and a `housing` guide showing the surrounding material the rest should retain. Position the whole assembly; retrieve tool and housing snapshots afterward. The housing is a design guide and is not automatically added to the rest.

The rigid installation mount defines the leg's position and orientation. Its Z direction points into the rest; for the hinge implementation, X follows the rod axis. Final attachment details belong entirely to the leg implementation.

`leg.install(body, at=local_frame, joint_label=...)` modifies the supplied `Part` in place and returns a `LegInstallation`: an independent leg assembly, tool and housing snapshots, and an `attach_to(final_body)` method. `Rest` installs both legs, passes the final body to each result's `attach_to()`, and nests the finished components. `at` is a `Location` in the body's local modeling frame, such as `geometry.left_mount_joint.relative_location`. Attachment joints are created on the final body. An implementation can use hinges, rigid joints, multiple joints, or direct placement.

Configure attachment settings on the chosen leg implementation. For example, `build_hinge_leg(angle=15, angular_range=(-30, 30))` selects its final hinge angle and limits in degrees. See the [leg spec](specs/leg_spec.md) for its attachment behavior and cavity geometry.

### Rest: shared behavior and body implementations

`RestGeometry` supplies a finished `Part` containing one solid and three typed rigid joints on that body: `left_mount_joint`, `right_mount_joint`, and `violin_joint`. Concrete geometry implementations handle any positioning and shoulder contouring needed during construction. `Rest(geometry, leg)` installs both legs and creates the completed assembly at the body's pose. Supplying the geometry transfers its body for construction and nesting; leg implementations modify it in place.

```python
from shoulder_rest.parts.leg.hinge_leg import build_hinge_leg
from shoulder_rest.parts.rest import Rest
from shoulder_rest.parts.simple_rest import SimpleRestGeometry, SimpleRestParameters
from shoulder_rest.parts.violin_outline.spline_violin_outline import build_violin_outline

violin = build_violin_outline()
geometry = SimpleRestGeometry(violin, SimpleRestParameters(width=44, thickness=12))
rest = Rest(
    geometry, build_hinge_leg(angle=15),
    right_leg=build_hinge_leg(angle=-10),
)
rest.position_on(violin)
assembly = rest.assembly
```

`assembly` is ready for display or nesting; `part` is its printable body child. Omitting `right_leg` uses the supplied template independently for both sides; providing it allows different settings or attachment mechanisms.

If the geometry is already fitted to the shoulder and violin, its placement carries into `Rest` without another positioning step. Otherwise, position the violin first and call `rest.position_on(violin)`. All `position_on` methods move their receiver once, before scene nesting; call them again when their reference moves. Move `rest.assembly` to move the rest independently, keeping its children together.

Custom outlines can subclass `ViolinOutline` to inherit `position_on(shoulder)`. Custom rest geometry only needs to provide the body and three attachment properties, either by subclassing `RestGeometry` or satisfying it structurally. `Rest` provides placement of the completed assembly.

`SimpleRestGeometry` builds a flat rounded bar without a shoulder contact cut. Change `SimpleRestParameters` for dimensions and attachment fractions, or implement `RestGeometry` for a different body and contouring workflow. `build_simple_rest(violin, leg, parameters)` is a convenience factory for the rounded geometry and assembled rest. The [rest spec](specs/rest_spec.md) describes geometry ownership and coordinate conventions. Preview the complete fitting scene with `uv run python -m shoulder_rest.parts.rest`.

`ContouredRestGeometry` demonstrates fitting during construction. It positions the violin on the supplied shoulder, extends the right half of a rounded bar to an oversized depth, and subtracts `shoulder.extended`. It defines the joints on the finished body at its fitted pose:

```python
from shoulder_rest.parts.contoured_rest import ContouredRestGeometry, ContouredRestParameters

# shoulder defines the violin placement; violin is an un-nested outline.
geometry = ContouredRestGeometry(
    violin, shoulder, ContouredRestParameters(contact_depth=80),
)
rest = Rest(geometry, build_hinge_leg())
# Already fitted: display rest.assembly with shoulder.assembly and violin.block.
```

The other half stays at the base bar thickness. `contact_side="left"` selects the opposite half; `contact_depth` is the total blank depth below the leg mounting face, in mm. Width, thickness, attachment fractions, and violin gap use the same parameters as the simple bar. Adjust the shoulder's violin placement to change the fit, then rebuild the geometry and rest. Preview the example with `uv run python -m shoulder_rest.parts.contoured_rest`.

## Repository layout

- `src/shoulder_rest/parts/`: reusable models. Each of `leg/`, `shoulder/`, and `violin_outline/` contains a same-named interface module and a separate implementation (`hinge_leg.py`, `step_shoulder.py`, or `spline_violin_outline.py`). Package imports expose the interfaces; factories and parameters live with their implementations. Shared Kun geometry remains in `parts/kun.py`.
- `src/shoulder_rest/assets/`: input geometry bundled with the package.
- `assets/`: reference material, including original STEP solids.
- `tests/`: assembly and contouring workflow smoke checks; run `uv run python -m unittest discover -s tests`. Use the CAD previews to inspect evolving geometry.
- `specs/`: feature geometry, frame conventions, and implementation details.
- `exports/`: generated STEP/STL files, ignored by Git.
- `changelog/`: optional change history.

See [AGENTS.md](AGENTS.md) for contributor and coding guidance.
