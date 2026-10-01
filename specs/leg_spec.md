# Hinge-slot leg

Source: [Onshape Hinge Slot Leg](https://cad.onshape.com/documents/4b6fd83d4ef915bc8da1e93f/w/38814d255f0d64578653c02a/e/db1dc0bcdac152a853d83f7c), exported 2026-09-27. The three STEP files in `assets/leg/` are test references; runtime geometry is procedural.

## Interface

`build_hinge_leg(LegParameters(...), CavityParameters(...), angle=0, angular_range=(-180, 180))` returns `HingeLeg`, implementing the `Leg` protocol:

- `assembly`: printable leg and metal rod as separate children. Use the typed `rod_joint`, `screw_joint`, `nut_joint`, and `mount_joint` properties to position the complete assembly. `HingeLegPart` also exposes `rod_joint`, `screw_joint`, and `nut_joint` on the printable child.
- `part`: printable `HingeLegPart` child, for export. `HingeLeg.rod` exposes the metal hardware child.
- `tool`: cavity and rod insertion slots, as an independent snapshot.
- `housing`: symmetric surrounding-material guide with the cavity removed. It is a modeling guide, not a strength guarantee.
- `mount_joint`: installation frame on `assembly`. Positioning this assembly also positions subsequently retrieved tool/guide snapshots; leave the individual children in their local frames.
- `install(body, at=local_frame, joint_label=...)`: returns `HingeLegInstallation`, implementing `LegInstallation`. It contains the new cut `rest`, independent `leg` assembly, and positioned `tool`/`housing` snapshots. Its `attach_to(final_body)` creates a hinge on the final body using a retained local rod axis, then connects the rod at the configured angle. Neither installation input is modified.
- `angle` and `angular_range` are template constructor options in degrees. The range must be finite and include zero; the angle must be finite and within that range. These settings are captured by each installation. `rod_joint`, `joint_label`, and `angle` are hinge-specific result details, outside the generic interface.

Installation cuts a single-solid `Part` or `Solid`, preserving its modeling frame and placement. The returned body contains geometry only, without the source's joint or connection metadata. The Boolean result leaves the input body unchanged; the generic `Leg` contract also permits implementations that modify the body in place. Installation does not add housing material. A missing intersection or disconnected result raises `ValueError`. Final attachment rejects a duplicate hinge label or nested body/leg.

## Frames and use

Source frame: rod along X through the origin, nut housing toward +Y, screw along Z. The mount is centered on the nut-seat edge, matching the origin of Onshape's **Mate connector 1**: `(0, 10.425, 3.1)` by default. Its explicit axes are X along source +X and Z along source -Z (toward the rest).

For a rest modeled below its XY mounting surface, the rest implementation supplies mounts with Z pointing downward. `Rest` consumes these joints through `RestGeometry`, installs the templates at both frames and delegates final attachment to their installation results:

```python
from shoulder_rest.parts.leg.hinge_leg import build_hinge_leg
from shoulder_rest.parts.simple_rest import build_simple_rest

rest = build_simple_rest(
    violin, build_hinge_leg(angle=15), right_leg=build_hinge_leg(angle=-10),
)
rest.position_on(violin)
assembly = rest.assembly
```

For lower-level modeling, `Leg.install(body, at=...)` accepts a `Location` in the un-nested body's local modeling frame. For an existing rigid mount, pass `mount.relative_location`, not its world location. Complete all cuts, then call each installation's `attach_to(final_body)` before nesting the body or legs. The method creates its revolute joint on the final body and applies the configured angle; the caller does not need to retrieve or connect that joint. Each installed rod frame is clocked so angle zero reproduces its cutting pose; positive angles follow the right-hand rule about mount +X. Angle limits describe kinematics, not a collision-free range. Tool and housing snapshots remain in the installation pose when the leg rotates.

## Geometry and references

The printed leg and cavity share the lower side profile (rounded nose, underside, and rear relief). The printed body adds the raised nut housing. The cavity adds a rectangular nose movement allowance, extends the underside by `bottom_clearance`, then offsets the perimeter by `clearance` with sharp corners. Rod insertion slots are added after extrusion; holes and chamfers do not affect the shared profile.

Private `BuildSketch` helpers construct the side profiles in local XY, where horizontal corresponds to body Y and vertical to body Z. `BuildPart` places them on YZ planes for extrusion. Kun helpers retain their public XY screw-hole and YZ nut-slot frames. Helpers do not add geometry to a caller's active builder; the caller explicitly inserts their output.

The rod channel combines a diamond seat with horizontal and upright rectangles, then rounds the two turning corners. The Kun screw opening constructs its upper boundary from a circular arc and straight segments, then mirrors it across the screw centerline.

Hardware and fits are configured separately:

```python
from shoulder_rest.parts.kun import KunParameters, screw_hole_face, nut_slot_face
from shoulder_rest.parts.leg.hinge_leg import RodParameters, LegParameters, CavityParameters

parameters = LegParameters(
    rod=RodParameters(diameter=2, length=20),
    kun=KunParameters(nut_slot_width=8.65, nut_slot_height=3.4),
    rod_bore_clearance=0.2,
)
leg = build_hinge_leg(parameters, CavityParameters(rod_length_clearance=1))
```

The default bore is rod diameter + 0.3 mm; insertion-slot width is diameter + 0.1 mm; its outer corner radius is rod radius + 0.1 mm; tool length is rod length + 1 mm total (0.5 mm per end). These allowances are independent fields so changing metal stock updates all dependent geometry without conflating radial and diametral fits. The displayed rod uses the actual stock dimensions. Its axial spin is visually indistinguishable, so it moves with the printed leg as a single assembly.

The reusable Kun profiles return fresh `Face` objects: `screw_hole_face(kun)` lies in XY at the nominal screw axis, for extrusion along Z; `nut_slot_face(kun)` is centered in YZ, with width along Y and height along Z, for extrusion along X. Position/rotate the faces with build123d `Location` before extruding. Their fitted opening dimensions already include the intended fit; they do not model the metal nut or Kun foot.

- Printed leg: 12 mm wide; 6.2 mm rod housing; 2.3 mm default bore; 1.5 mm nose radii. Nut slot: 8.65 × 3.4 mm, with 2 mm walls. Rear relief: 20° from vertical. Outside chamfers: 0.3 mm.
- Screw passage: 4 mm circular sides offset 0.1 mm along X, flat at X=1.9, tangent roof segments at 40° from -X, clipped 0.2 mm beyond the circle. This retains the source's printable profile.
- Cutter: 0.1 mm general clearance plus 0.1 mm extra underside clearance. Rod insertion channel: 2.1 mm wide, 3 mm run, 0.2/1.1 mm corner radii, extruded across 21 mm.
- Guide: 2 mm nominal body margin and 1 mm rod-end caps. Its symmetric underside fills the source Dummy Housing's one-sided notch, adding approximately 183.355308 mm³; it otherwise contains the source guide exactly.

The leg with `rod_bore_clearance=0.2` and the default cutter match their Onshape solids by volume and two-way Boolean difference. The current leg default uses 0.3 mm bore clearance.

Preview: `uv run python -m shoulder_rest.parts.leg.hinge_leg`. Tests: `uv run python -m unittest discover -s tests`.
