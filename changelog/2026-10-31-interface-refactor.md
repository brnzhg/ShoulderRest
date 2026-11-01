# 2026-10-31: Interface and construction refactor

Geometry is unchanged. Bar rests and legs are bit-identical; the W rest coincides within modeling tolerance.

## Ownership changes

- Rest designs no longer move the violin. They contour with `shoulder.cutter(violin_mount)` and always return bodies in the violin outline's local frame; `rest.position_on(violin)` is the only placement step.
- `RestGeometry` is a frozen record of a body and three `Location` frames, not a protocol of joints. Designs are functions that return one.
- `Leg.install(body, at=...)` returns `(new_body, installation)` instead of modifying the body in place. Installations produce components in the body's frame; `Rest.add(component)` owns adding them to the assembly.
- `Shoulder` and `ViolinOutline` are concrete classes. The STEP and spline modules now only load or trace input data. Shoulder shapes stay in the shoulder's local frame instead of following its assembly.
- Joints mark attachment frames on finished parts and assemblies. `HingeLegPart`'s rod, screw and nut joints, the hinge template's assembly joints (including `mount_joint` and the `hinge` revolute joint) and `Rest`'s mount joints are unchanged. Leg components copied by `leg()` keep their joints. Builders pass frames to one another as `Location`s.

## API map

| Before | After |
|---|---|
| `parts.rest`, `parts.rest_geometry` | `parts.rest` package (`Rest`, `RestGeometry`, `leg_mount`) |
| `SimpleRestGeometry(violin, SimpleRestParameters())`, `build_simple_rest` | `bar_rest_geometry(violin, BarRestParameters())` in `parts.rest.bar_rest` |
| `ContouredRestGeometry(violin, shoulder, ContouredRestParameters())` | `contoured_bar_rest_geometry(violin, shoulder, ContouredBarRestParameters())` |
| `WRestGeometry(violin, shoulder, WRestParameters(...))` in `parts.wrest` | `w_rest_geometry(...)` in `parts.rest.w_rest`, with grouped `WPathParameters` (`strokes`, `bend_radii`), `WHeadParameters` (incl. caps) and `WTailParameters`; the fixed leg fractions 0.46/0.4 became parameters |
| `build_hinge_leg(...)` | `HingeLeg(...)` |
| `rest.left.attach_to(rest.assembly, angle=a)` | `rest.add(rest.left.leg(angle=a))` |
| `rest.left.attach_housing_to(rest.assembly)` | `rest.add(rest.left.housing)` |
| `installation.local_placement`, `.tool` | `installation.placement`; `template.tool.moved(placement)` |
| `geometry.left_mount_joint` etc. | `geometry.left_mount` etc. (`Location`); `rest.left_mount_joint` is unchanged |
| `HingeLeg(angular_range=...)` range read from the template | `leg.hinge.angular_range` |
| `violin.add_mount_joint(part, offset=o)` | `violin.mount_location * o` as `RestGeometry.violin_mount` |
| `SplineViolinOutline(points)` | `ViolinOutline(curve)`, or `build_violin_outline(points)` |
| `StepShoulder(...)` | `Shoulder(reference, extended, violin_location)`, or `load_shoulder_cast()` with the current fit as default |
| `parts.kun`, `nut_slot_face` | `parts.leg.kun`; the nut slot is a `Box` in the hinge leg |
| `parts.leg.hinge_snaps`, `examples/hinge_snaps.py` | `parts.leg.rod_retention`, `examples/rod_retention_coupon.py` |
| `mypy` runtime dependency | dev dependency |
