# Hinge-slot leg

Source: [Onshape Hinge Slot Leg](https://cad.onshape.com/documents/4b6fd83d4ef915bc8da1e93f/w/38814d255f0d64578653c02a/e/db1dc0bcdac152a853d83f7c), exported 2026-09-27. The three STEP files in `assets/leg/` are modeling references; runtime geometry is procedural.

## Interface

`HingeLeg(LegParameters(...), CavityParameters(...), angular_range=(-180, 180), rod_retention=None)` in `parts/leg/hinge_leg.py` implements the `Leg[HingeLegInstallation]` protocol. All of its geometry is in the source frame:

- `part`: the printable `HingeLegPart`, for export. It carries rigid `rod_joint` (at the origin, Z along the rod), `screw_joint` (the nominal screw entry on the bottom face) and `nut_joint` (the nut seat center) frames.
- `rod`: the metal rod. `assembly` holds `part` and `rod` as separate children. It carries copies of the rod, screw and nut joints, `mount_joint` at `mount_location`, and the `hinge` revolute joint about the rod. The hinge axis points along source -X, so placing a leg through it turns positive angles about mount +X. `angular_range` sets the hinge limits.
- `tool`: the cavity cutter, including the rod insertion slots.
- `housing`: a symmetric guide of surrounding material, with the cavity removed. It is a modeling guide, not a strength guarantee, and is never added to a rest automatically.
- `mount_location`: the mount frame in the source frame.
- `install(body, at=frame)`: returns a copy of `body` with `tool` cut at the mount frame `at`, plus a `HingeLegInstallation`. The body must be in its local frame, and `at` is in those coordinates. Installation keeps the body's label and color. It raises `ValueError` if the cutter misses the body, leaves more than one solid, or would leave retention bumps outside the body.

`HingeLegInstallation(template, location)` is a frozen record of one site. Everything it returns is in the body's local frame:

- `placement`: the leg's source frame at the site, `location * template.mount_location.inverse()`.
- `leg(angle=0)`: a fresh copy of the rod-and-leg assembly, joints included, at the site, swung `angle` degrees about mount +X (the rod). This matches placing the copy through its `hinge` joint. The angle must lie within the hinge's `angular_range`, which must be finite and include zero. The limits describe kinematics, not a collision-free range.
- `housing`: a fresh housing guide at the site, independent of angle.

Each call returns an independent component; add it to a rest with `rest.add(...)`.

## Frames

Source frame: rod along X through the origin, nut housing toward +Y, screw along Z. The mount is centered on the nut-seat edge of the mounting face, matching the origin of Onshape's **Mate connector 1**: `(0, 10.425, 3.1)` by default. Its X axis follows source +X and its Z axis source -Z (toward the rest), so the rounded nose (source -Y) faces mount +Y. Angle zero reproduces the cutting pose.

## Geometry and references

The printed leg and cavity share the lower side profile (rounded nose, underside, and rear relief). The printed leg adds the raised nut housing. The cavity adds a rectangular nose movement allowance, extends the underside by `bottom_clearance`, then offsets the perimeter by `clearance` with sharp corners. Rod insertion slots are added after extrusion; holes and chamfers do not affect the shared profile.

Private `BuildSketch` helpers construct the side profiles in local XY, where horizontal corresponds to body Y and vertical to body Z. `BuildPart` places them on the YZ plane for extrusion. The exterior is chamfered first. The bore, a full-width `Box` nut slot and the screw opening are cut afterward, which keeps the seats and passages sharp.

The rod channel combines a diamond seat with horizontal and upright rectangles, then rounds the two turning corners. The Kun screw opening (`parts/leg/kun.py`, `screw_hole_face`) starts with an offset circle and replaces its +X side with a rectangle at the X=0 chord. A tangent roof on -X follows the circle's tangent with a `PolarLine` to the roof's clipping plane, and mirroring the upper roof across X completes the symmetric opening. The face lies in XY at the nominal screw axis, for extrusion along Z, and already includes the intended fit.

Hardware and fits are configured separately:

```python
from shoulder_rest.parts.leg.hinge_leg import CavityParameters, HingeLeg, LegParameters, RodParameters
from shoulder_rest.parts.leg.kun import KunParameters

parameters = LegParameters(
    rod=RodParameters(diameter=2, length=20),
    kun=KunParameters(nut_slot_width=8.65, nut_slot_height=3.4),
    rod_bore_clearance=0.2,
)
leg = HingeLeg(parameters, CavityParameters(rod_length_clearance=1))
```

The default bore is rod diameter + 0.3 mm, and the insertion-slot width is diameter + 0.1 mm. The slot's outer corner radius is rod radius + 0.1 mm, and the tool is rod length + 1 mm (0.5 mm per end). These allowances are independent fields, so changing the metal stock updates all dependent geometry without conflating radial and diametral fits. The displayed rod uses the actual stock dimensions.

- Printed leg: 12 mm wide; 6.2 mm rod housing; 2.3 mm default bore; 1.5 mm nose radii. Nut slot: 8.65 × 3.4 mm, with 2 mm walls. Rear relief: 20° from vertical. Outside chamfers: 0.3 mm.
- Screw passage: 4 mm circular sides offset 0.1 mm along X, flat at X=1.9, roof tangent contact radius at 40° from -X, clipped 0.2 mm beyond the circle. This retains the source's printable profile.
- Cutter: 0.1 mm general clearance plus 0.1 mm extra underside clearance. Rod insertion channel: 2.1 mm wide, 3 mm run, 0.2/1.1 mm corner radii, extruded across 21 mm.
- Guide: 2 mm nominal body margin and 1 mm rod-end caps. Its symmetric underside fills the source Dummy Housing's one-sided notch, adding approximately 183.355308 mm³; it otherwise contains the source guide exactly.

The leg with `rod_bore_clearance=0.2` and the default cutter match their Onshape solids by volume and two-way Boolean difference. The current leg default uses 0.3 mm bore clearance.

Preview: `uv run python -m shoulder_rest.parts.leg.hinge_leg`.

## Optional rod retention

`HingeLeg(rod_retention=RodRetentionParameters())` keeps two solid rounded ribs on the +Z walls of the rod channels (their ceilings in the source frame). The option defaults to `None`; the parameters and private builder live in `parts/leg/rod_retention.py`. Installation checks that the receiving body contains the bumps.

Each bump is 0.8 mm wide along X, with a 0.45 mm radius centered at Y=0.75 mm, midway along each rod overhang. Both diamond bearing faces and the axial end walls remain intact. `interference=0.10` sets a 1.90 mm throat for the 2 mm rod. The bumps project 0.20 mm toward -Z into the original 2.10 mm channel. The seated rod clears them; reverse travel meets them after approximately 0.11 mm at nominal Z=0.

The rest's flat mounting face is always printed against the bed. In the hinge source frame that face is Z=`rod_house_half` (+3.1 mm by default), with source +Z pointing toward the bed. The channel's +Z wall therefore becomes its printed floor, supporting the bumps as they grow upward. See the [rest print convention](rest_spec.md#print-orientation).

This is a local deformation fit. Insertion force, wear and retention require a PETG print trial; tune the interference in steps of about 0.05 mm. `uv run python examples/rod_retention_coupon.py --export` writes the housing coupon, printed leg and assembly to `exports/rod_retention/`. The coupon STL is flipped 180° about X onto its mounting face, and the leg STL lies on its broad side; STEP files keep the source pose. There are no added angular detents, springs, foam pockets or foam components.

## Nose recess clearance

`CavityParameters(nose_clearance=0.2)` enlarges the existing rectangular nose allowance by 0.2 mm toward both -Y and -Z. The default is zero. Its rear step stays at Y=`rod_house_half` before the general fit offset; the raised rear cavity floor, printed leg, rod seats and mounting frame stay unchanged. The allowance has the full cavity width. This single dimension can provide extra space for a user-cut piece of thin foam without modeling a separate pocket or changing the leg. Preview it with `uv run python examples/rod_retention_coupon.py --nose-clearance 0.2`.

With `h = rod_house_half`, `r = nose_swing_radius`, and `n = nose_clearance`, the nose floor is at Z=`-r - n - bottom_clearance - clearance`; the rear floor is at Z=`-h - bottom_clearance - clearance`. Their level difference is `r - h + n`. The nose wall is at Y=`-r - n - clearance`.

For the original 6.2 mm hinge block, the default step is about 0.663 mm. Adding 0.2 mm makes the step about 0.863 mm and lowers the nose floor from Z=-3.963 to -4.163 mm. The housing guide remains Z=-5.1 to +3.1 mm, leaving about 0.937 mm under the enlarged recess. Its outside dimensions do not grow; additional clearance consumes front and bottom wall material. Settings that cut through the guide are rejected. Check the actual remaining material in the final rest and choose the clearance for the foam's compressed fit; this parameter does not prescribe foam thickness or detent force.
