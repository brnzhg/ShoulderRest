# Shoulder Rest

Parametric [build123d](https://build123d.readthedocs.io) models for a 3D-printed violin shoulder rest. Dimensions are in millimeters and angles in degrees.

## Setup

Use Python 3.12 and [uv](https://docs.astral.sh/uv/):

```sh
uv sync --locked
```

Select the project's `.venv` interpreter in VS Code and start the OCP CAD Viewer extension. Each implementation module previews itself when run, for example `uv run python -m shoulder_rest.parts.rest.w_rest`. Run the smoke checks with `uv run python -m unittest discover -s tests`.

## How the pieces fit together

A rest is fitted to one player. The shoulder fixes where the violin sits, the violin outline fixes where the rest body and its legs go, and `Rest` joins the body and legs into one assembly that hangs under the violin.

| Class | Responsibility | Main members |
|---|---|---|
| `Shoulder` | Shoulder casts and where the violin sits on them | `assembly`, `violin_joint`, `cutter(violin_mount)` |
| `ViolinOutline` | The violin's outline, the curves leg centers are picked from, and the mount frame shared with shoulder and rest | `attachment_point(side, fraction)`, `mount_location`, `block`, `position_on(shoulder)` |
| `RestGeometry` | A finished rest body, before leg cavities, with its attachment frames | `part`, `left_mount`, `right_mount`, `violin_mount` |
| `Leg` | A leg mechanism: a printable part and the cavity it needs | `part`, `install(body, at=frame)` |
| `LegInstallation` | One leg site cut into a body | `location`, `housing`, `leg()` |
| `Rest` | The body with both cavities cut, as one positionable assembly | `part`, `assembly`, `left`, `right`, `add(component)`, `position_on(violin)` |

`Shoulder`, `ViolinOutline`, `RestGeometry` and `Rest` are concrete classes. Loaders and builders provide specific instances: a STEP cast, a traced spline outline, or a rest design function. `Leg` and `LegInstallation` are protocols because each leg mechanism has its own cavity and attachment controls. `Rest[InstallationT]` keeps the concrete installation type, so `rest.left` exposes controls such as a hinge leg's angle.

### Frames

- **The violin outline's local XY is the common modeling frame.** `mount_location` is the midpoint of the outline's upper-Y closing line, on Z=0.
- **Rest bodies** are modeled in that frame, with the flat leg-mounting face at Z=0 and material toward -Z.
- **`Shoulder.violin_location`** says where the violin's mount frame sits on the shoulder. **`RestGeometry.violin_mount`** says which body frame meets it, usually the mount frame raised by a gap so the rest hangs below the violin.
- **Leg mount frames** sit on the mounting face with Z pointing into the body. `leg_mount(center, facing)` builds one.
- **Construction never moves anything.** A rest design contours its body with `shoulder.cutter(violin_mount)`, which places the cast in the body's frame. Placement happens only through `position_on`, which connects joints once, before the parts are nested in a scene.

## Building a rest

```python
from build123d import Compound

from shoulder_rest.parts.leg.hinge_leg import HingeLeg
from shoulder_rest.parts.rest import Rest
from shoulder_rest.parts.rest.w_rest import (
    WHeadCapParameters, WHeadParameters, WRestParameters, w_rest_geometry,
)
from shoulder_rest.parts.shoulder.step_shoulder import load_shoulder_cast
from shoulder_rest.parts.violin_outline.spline_violin_outline import build_violin_outline

shoulder = load_shoulder_cast()
violin = build_violin_outline()
violin.position_on(shoulder)

geometry = w_rest_geometry(violin, shoulder, WRestParameters(head=WHeadParameters(
    left_cap=WHeadCapParameters(angle=24, height=34, depth=30),
    right_cap=WHeadCapParameters(angle=10, height=30, depth=20),
)))
rest = Rest(geometry, HingeLeg())
rest.add(rest.left.leg(angle=20))
rest.add(rest.right.leg())
rest.add(rest.left.housing)
rest.position_on(violin)

scene = Compound(children=[shoulder.assembly, violin.block, rest.assembly])
```

`rest.part` is the printable body. It is printed with its flat mounting face on the bed, so export it in its local frame and turn it over.

## Extending

- **A new rest shape** is a function that returns a `RestGeometry`. Subtract `shoulder.cutter(violin_mount)` to fit the shoulder.
- **A new leg mechanism** implements the `Leg` and `LegInstallation` protocols.
- **A different violin or shoulder** is a `ViolinOutline` built from any right-hand outline curve, or a `Shoulder` built from cast shapes and a violin location.

## Repository layout

- `src/shoulder_rest/parts/`: one subpackage per interface (`shoulder/`, `violin_outline/`, `leg/`, `rest/`). Each package's `__init__` exposes its interface; implementation modules sit beside it.
- `src/shoulder_rest/assets/`: input geometry bundled with the package.
- `assets/`: reference material, such as the original STEP solids.
- `examples/`: standalone scripts, such as the rod-retention test coupon.
- `tests/`: smoke checks for construction and placement.
- `changelog/`: notable changes.
- `exports/`: generated STEP and STL files, ignored by Git.

See [AGENTS.md](AGENTS.md) for contributor guidance.
