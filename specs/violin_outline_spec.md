# Violin Outline
Create a spline from the points below. Mirror this. 
Then we want a class representing the left and right curves. 
There should also be versions of these curves both offset inwards by a configurable offset.
The class should additional have part extruded from a face created from the orignal two curves with horizontal lines attaching the top and bottom.
This is extruded 38mm to create a simplified "Violin Block" to aid in visualizing the violin loation.

There should also be an abstract version of this, that is holding a Violin Block and the 4 curves (2 of which are for constraining attachment to the rest).

## Spline Points:
(87.175, -56.570)
(91.220, -49.3)
(96.473, -37.724)
(101.728, -15.76)
(102.605, 0)
(101.12, 15.165)
(94.784, 32.802)
(84.79, 46.767)
(65.910, 61.558)
(43.630, 69.918)
(18.865, 73.536)

## Modeling interface and coordinate conventions

- `ViolinOutline` is the interface; `SplineViolinOutline` interpolates the supplied right-hand points and mirrors across YZ. Custom points must have positive X and strictly increasing Y.
- `left`, `right`, `left_attachment`, and `right_attachment` return independent open wires in local XY. All run from the lower-Y endpoint to the upper-Y endpoint.
- `attachment_offset` is the normal inward distance in mm (class default 3; `build_violin_outline()` uses 6); zero uses the original curves. Offsets that fail or leave the footprint/cross the centerline are rejected. Open offset endpoints are not extended back to the horizontal end caps.
- `block` uses the original curves and horizontal end caps, extruded from Z=0 toward +Z by `block_thickness` (default 38 mm). Its `shoulder_joint: RigidJoint` property uses `mount_location` and follows block placement.
- `attachment_point(side, fraction)` chooses a leg center by normalized arc length, 0 through 1, on an attachment curve. Use these points as endpoints of a downstream `Polyline`; interior guide points remain parameters of the shoulder-rest design. Changing parameters requires rebuilding the guide; there is no persistent sketch constraint solver.
- Construction curves stay in local XY when the visualization block moves. Model the rest in that frame and apply the block's placement to the finished rest for assembly. To place a local guide for display, use `guide.moved(violin.block.global_location)`.

## Shared shoulder / violin / rest mount

`mount_location` is a local `Location` at the midpoint of the original upper-Y closing line, on Z=0, with the outline's XYZ axes. For the bundled tracing this is `(0, 73.536, 0)`. It does not depend on attachment-curve inset or block thickness, and does not move when the block is placed.

`add_mount_joint(part, label="violin", offset=None)` creates and returns a `RigidJoint` on a Solid or Compound whose local modeling frame matches the outline. Its local joint frame is `mount_location * offset` (identity when omitted). The helper accounts for the part's existing placement and rejects duplicate joint labels. The block uses this same helper with label `shoulder` and no offset.

To keep the shoulder fixed, connect `shoulder.violin_joint` to `violin.shoulder_joint`, then connect that block joint to the rest's `violin` joint. Either fixed joint can also position the rest directly. As usual, `connect_to` moves its argument. Connect before nesting assemblies.

A pure +Z joint offset of `h` mm places the rest at -Z by `h` relative to the violin, retaining identical XY alignment. General `Location` offsets are allowed, including tilt; these affect the resulting rest placement inversely when the joints are aligned. This represents a rigid adjustment only, not individual screw or leg geometry.

Run `uv run python -m shoulder_rest.parts.violin_outline.spline_violin_outline` to preview the block, four curves, and an example guide polyline in OCP CAD Viewer.
