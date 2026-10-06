# Hinge-slot leg

Source: [Onshape Hinge Slot Leg](https://cad.onshape.com/documents/4b6fd83d4ef915bc8da1e93f/w/38814d255f0d64578653c02a/e/db1dc0bcdac152a853d83f7c), exported 2026-09-27. The three STEP files in `assets/leg/` are modeling references; runtime geometry is procedural.

## Interface

`build_hinge_leg(LegParameters(...), CavityParameters(...), angular_range=(-180, 180))` returns `HingeLeg`, implementing `Leg[HingeLegInstallation]`:

- `assembly`: printable leg and metal rod as separate children. Use the typed `rod_joint`, `screw_joint`, `nut_joint`, and `mount_joint` properties to position the complete assembly. `HingeLegPart` also exposes `rod_joint`, `screw_joint`, and `nut_joint` on the printable child.
- `part`: printable `HingeLegPart` child, for export. `HingeLeg.rod` exposes the metal hardware child.
- `tool`: cavity and rod insertion slots, as an independent snapshot.
- `housing`: symmetric surrounding-material guide with the cavity removed. It is a modeling guide, not a strength guarantee.
- `mount_joint`: installation frame on `assembly`. Positioning this assembly also positions subsequently retrieved tool/guide snapshots; leave the individual children in their local frames.
- `install(body, at=local_frame, joint_label=...)`: cuts the supplied body in place and returns a frozen `HingeLegInstallation` site descriptor. Its public `body` and `local_placement` satisfy `LegInstallation`. It retains a rigid site joint and references to the component templates; installation does not add a leg assembly.
- `angular_range` is a template constructor option in degrees. The range must be finite and include zero. The template's rod-and-leg assembly has its revolute joint from construction.

`attach_to(assembly, angle=0)` adds and returns a fresh rod-and-leg `Compound`, enforcing the angular range. `attach_housing_to(assembly)` independently adds and returns a housing guide `Part` at the neutral site. Both methods account for the body's and destination's world placements, including nested assemblies. Repeated calls add independent components. The descriptor has no angle state or attachment lifecycle; its referenced CAD objects remain mutable. Components subsequently follow their destination assembly, so use the rest assembly when they should move with the body.

`tool` and `housing` also return fresh world-positioned snapshots using `body.global_location * local_placement`. Previously retrieved snapshots do not track movement. Neither these properties nor the attachment methods are required by the common installation protocol.

Installation cuts a `Part` containing one solid, preserving its modeling frame and placement. A private `BuildPart(body.location)` uses `Locations` to insert the body in its local frame and subtract the cavity at the local installation placement. After validation, the cut geometry replaces the body's `wrapped` shape in place. The body retains its label, color, and existing joints. Installation does not add housing material. A missing intersection or disconnected result raises `ValueError`. Installation requires an un-nested body and a new nonempty site joint label.

## Frames and use

Source frame: rod along X through the origin, nut housing toward +Y, screw along Z. The mount is centered on the nut-seat edge, matching the origin of Onshape's **Mate connector 1**: `(0, 10.425, 3.1)` by default. Its explicit axes are X along source +X and Z along source -Z (toward the rest).

For a rest modeled below its XY mounting surface, the rest implementation supplies mounts with Z pointing downward. `Rest` prepares both sites; the caller chooses attachments:

```python
from shoulder_rest.parts.leg.hinge_leg import build_hinge_leg
from shoulder_rest.parts.simple_rest import build_simple_rest

rest = build_simple_rest(violin, build_hinge_leg())
rest.left.attach_to(rest.assembly, angle=15)
rest.right.attach_to(rest.assembly, angle=-10)
rest.left.attach_housing_to(rest.assembly)
rest.position_on(violin)
assembly = rest.assembly
```

For lower-level modeling, `Leg.install(body, at=...)` accepts a `Location` in the un-nested body's local modeling frame. For an existing rigid mount, pass `mount.relative_location`, not its world location. The rigid site joint matches the template hinge's actual zero frame, so angle zero reproduces the cutting pose. The moving revolute joint points along source -X: placement from the fixed rigid joint then makes positive attachment angles turn about mount +X. `relative_to` computes the joint placement without repositioning the body or modifying the descriptor. Angle limits describe kinematics, not a collision-free range.

Adding a build123d child reconstructs its parent compound at the origin. The attachment helper preserves the destination and ancestor placements and refreshes their compounds so nested scene geometry includes the added component.

## Geometry and references

The printed leg and cavity share the lower side profile (rounded nose, underside, and rear relief). The printed body adds the raised nut housing. The cavity adds a rectangular nose movement allowance, extends the underside by `bottom_clearance`, then offsets the perimeter by `clearance` with sharp corners. Rod insertion slots are added after extrusion; holes and chamfers do not affect the shared profile.

Private `BuildSketch` helpers construct the side profiles in local XY, where horizontal corresponds to body Y and vertical to body Z. `BuildPart` places them on YZ planes for extrusion. Kun helpers retain their public XY screw-hole and YZ nut-slot frames. Helpers do not add geometry to a caller's active builder; the caller explicitly inserts their output.

The rod channel combines a diamond seat with horizontal and upright rectangles, then rounds the two turning corners. The Kun screw opening starts with an offset circle, replaces its +X side with a rectangle at the X=0 chord, and adds a tangent roof on -X. A `PolarLine` follows the circle's tangent to the roof's clipping plane; mirroring the upper roof across X completes the symmetric opening.

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
- Screw passage: 4 mm circular sides offset 0.1 mm along X, flat at X=1.9, roof tangent contact radius at 40° from -X, clipped 0.2 mm beyond the circle. This retains the source's printable profile.
- Cutter: 0.1 mm general clearance plus 0.1 mm extra underside clearance. Rod insertion channel: 2.1 mm wide, 3 mm run, 0.2/1.1 mm corner radii, extruded across 21 mm.
- Guide: 2 mm nominal body margin and 1 mm rod-end caps. Its symmetric underside fills the source Dummy Housing's one-sided notch, adding approximately 183.355308 mm³; it otherwise contains the source guide exactly.

The leg with `rod_bore_clearance=0.2` and the default cutter match their Onshape solids by volume and two-way Boolean difference. The current leg default uses 0.3 mm bore clearance.

Preview: `uv run python -m shoulder_rest.parts.leg.hinge_leg`. Tests: `uv run python -m unittest discover -s tests`.

## Optional rod retention

`build_hinge_leg(..., rod_retention=RodRetentionParameters())` retains two solid rounded ribs in the floors of the rod channels. The option defaults to `None`; parameters are available from `hinge_leg` and private builders live in `hinge_snaps.py`. Installation checks that the receiving body contains the bumps and leaves one connected solid.

Each bump is 0.8 mm wide along X, with a 0.45 mm radius centered at Y=0.75 mm, midway along each rod overhang. Both diamond bearing faces and the axial end walls remain intact. `interference=0.10` sets a 1.90 mm throat for the 2 mm rod. The bumps rise 0.20 mm above the original 2.10 mm channel floor. The seated rod clears them; reverse travel encounters them after approximately 0.11 mm at nominal Z=0.

This is a local deformation fit. Insertion force, wear and retention require a PETG print trial; tune interference in approximately 0.05 mm steps. `uv run python examples/hinge_snaps.py --export` writes the housing coupon, original leg and assembly to `exports/hinge_snaps/`. There are no added angular detents, springs, foam pockets or foam components.

## Nose recess clearance

`CavityParameters(nose_clearance=0.2)` enlarges the existing rectangular nose allowance by 0.2 mm toward both -Y and -Z. The default is zero. Its rear step stays at Y=`rod_house_half` before the general fit offset; the raised rear cavity floor, printed leg, rod seats and mounting frame stay unchanged. The allowance has the full cavity width. This single dimension can provide extra space for a user-cut piece of thin foam without modeling a separate pocket or changing the leg.

With `h = rod_house_half`, `r = nose_swing_radius`, and `n = nose_clearance`, the nose floor is at Z=`-r - n - bottom_clearance - clearance`; the rear floor is at Z=`-h - bottom_clearance - clearance`. Their level difference is `r - h + n`. The nose wall is at Y=`-r - n - clearance`.

For the original 6.2 mm hinge block, the default step is about 0.663 mm. Adding 0.2 mm makes the step about 0.863 mm and lowers the nose floor from Z=-3.963 to -4.163 mm. The housing guide remains Z=-5.1 to +3.1 mm, leaving about 0.937 mm under the enlarged recess. Its outside dimensions do not grow; additional clearance consumes front and bottom wall material. Settings that cut through the guide are rejected. Check actual remaining material in the final rest and choose the clearance for the foam's compressed fit; this parameter does not prescribe foam thickness or detent force.
