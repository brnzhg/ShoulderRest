# Shoulder Rest

Parametric build123d models for a 3D-printed violin shoulder rest. The `Shoulder`, `ViolinOutline`, and `Leg` interfaces provide geometry and attachment frames for a rest implementation. The rest body itself is planned: an approximately S-shaped bar with a shoulder contact contour and a flat face toward the violin for printing. Dimensions are in millimeters; angles are in degrees.

## Setup and previews

Use Python 3.12 and [uv](https://docs.astral.sh/uv/):

```powershell
uv sync --locked
```

This installs the package and its dependencies into `.venv`. In VS Code, select `.venv/Scripts/python.exe` and start the OCP CAD Viewer extension. Preview individual components with:

```powershell
uv run python -m shoulder_rest.parts.shoulder
uv run python -m shoulder_rest.parts.violin_outline
uv run python -m shoulder_rest.parts.leg
```

## Interfaces for building a rest

### ViolinOutline: layout and shared attachment frame

`ViolinOutline` supplies local XY geometry for laying out the rest and its leg centers:

- `left` and `right`: violin outline curves.
- `left_attachment` and `right_attachment`: inward-offset curves for leg centers.
- `attachment_point(side, fraction)`: a point at a fraction of a curve's arc length, from its lower-Y end (0) to its upper-Y end (1).
- `block`: a positionable violin visualization with a rigid joint named `shoulder`.
- `mount_location`: the shared attachment frame at the midpoint of the outline's top (upper-Y) closing line, on Z=0.
- `add_mount_joint(rest, offset=...)`: adds a rigid joint named `violin` to a rest built in the outline's local frame.

Use sampled attachment points to define a parametric guide; rebuild it when parameters change:

```python
from build123d import Polyline
from shoulder_rest.parts.violin_outline import ViolinOutline, build_violin_outline

violin: ViolinOutline = build_violin_outline(attachment_offset=3.0)
guide = Polyline(
    violin.attachment_point("left", 0.25),
    (0, 10),
    violin.attachment_point("right", 0.60),
)
```

The curves stay in local XY even when the block moves. The block and rest share the same attachment point in this plane. An optional joint offset represents spacing or tilt relative to the violin. See the [outline spec](specs/violin_outline_spec.md) for tracing and frame details.

### Shoulder: contact geometry and violin placement

`Shoulder` supplies `reference` geometry for inspection, an `extended` cutting tool for shaping the contact surface, and an `assembly` containing the reference cast for display. Its `violin_joint` positions the violin relative to the shoulder.

Position the shoulder assembly before retrieving `reference` or `extended`: each is an independent snapshot at the current world placement. Use the extended shape in a Boolean cut after placing the rest in the same frame.

The bundled implementation is loaded with `load_shoulder_cast(cast_location=..., violin_location=...)`. `cast_location` reorients both input casts; `violin_location` defines the joint in that corrected shoulder frame. File loading is hidden from rest implementations.

Once the rest's cuts and leg installations are complete, connect the shared frames with the shoulder fixed:

```python
from build123d import Location

# shoulder implements Shoulder; rest was built in the outline's local frame.
rest_joint = violin.add_mount_joint(rest, offset=Location((0, 0, 12)))
shoulder.violin_joint.connect_to(violin.block.joints["shoulder"])
violin.block.joints["shoulder"].connect_to(rest_joint)
```

A +12 mm Z joint offset places the rest 12 mm toward -Z relative to the violin. Zero offset aligns their modeling frames. The rest joint can also connect directly to `shoulder.violin_joint`.

### Leg: installation and final attachment

`Leg` provides a printable `part`, an `assembly` including its metal hardware, a cavity-cutting `tool`, and a `housing` guide showing the surrounding material the rest should retain. Position the whole assembly; retrieve tool and housing snapshots afterward. The housing is a design guide and is not automatically added to the rest.

Installation uses three attachment frames:

| Frame | Owner | Purpose |
| --- | --- | --- |
| A rigid mount, e.g. `leg_mount` | Rest, defined by its implementation | Specifies the leg-hole center and orientation on the rest's mounting plane. |
| `leg.mount_joint` | Leg template assembly | Installation reference that `install()` aligns to the rest's rigid mount. |
| A revolute joint, e.g. `left_leg` | Returned rest, created by `install()` | Final hinge at the installed rod axis; connects to `installed.rod_joint` on the returned leg assembly. |

**X and Z describe axes of the rigid installation mount.** Its X direction follows the hinge rod; its Z direction points into the rest. The hinge pivot is offset from this mount to the rod's position by the leg implementation. For a rest extending below its XY mounting plane, mount Z points toward global -Z.

```python
from shoulder_rest.parts.leg import Leg, build_hinge_leg

leg: Leg = build_hinge_leg()
# rest already has a rigid joint named "leg_mount" at the desired leg-hole center.
installed = leg.install(rest.joints["leg_mount"], joint_label="left_leg")
rest = installed.rest

# After all cuts/installations and positioning the rest against the violin:
rest.joints["left_leg"].connect_to(installed.rod_joint, angle=15)
# Include rest and installed.leg in the final assembly.
```

`install()` returns a new cut rest with its existing joints preserved, an independent leg assembly, and positioned tool/housing snapshots. Inputs are unchanged. Angle zero reproduces the installation pose; rotating the leg leaves the cutter and housing snapshots fixed.

Complete all cuts and installations before connecting assembly joints, always using the latest returned rest's joints. Connect parts before nesting them in the final assembly. The current hinge-slot implementation receives a Kun screw leg and metal rod; its dimensions, mount construction, and repeated-installation example are in the [leg spec](specs/leg_spec.md).

## Repository layout

- `src/shoulder_rest/parts/`: interfaces and reusable model implementations.
- `src/shoulder_rest/assets/`: input geometry bundled with the package.
- `assets/`: reference material, including STEP solids used by tests.
- `tests/`: geometry and interface checks; run `uv run python -m unittest discover -s tests`.
- `specs/`: feature geometry, frame conventions, and implementation details.
- `exports/`: generated STEP/STL files, ignored by Git.
- `changelog/`: optional change history.

See [AGENTS.md](AGENTS.md) for contributor and coding guidance.
