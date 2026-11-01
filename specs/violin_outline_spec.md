# Violin outline

## Requirements

Create a spline from the traced points below and mirror it. Represent the left and right curves, plus versions of both offset inward by a configurable distance for constraining leg attachment. Close the original two curves with horizontal lines at the top and bottom, and extrude the face 38 mm into a simplified violin block that helps visualize the violin's location.

Keep how the outline is traced separate from what the rest consumes: the block, the four curves and the mount frame.

## Traced points

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

## Interface and conventions

- `ViolinOutline(right, attachment_offset=6, block_thickness=38)` is built from any right-hand curve: an open `Edge` or `Wire` at positive X, running from its lower-Y end to its upper-Y end. It mirrors the curve across YZ. `build_violin_outline(points=TRACED_RIGHT_OUTLINE, ...)` in `spline_violin_outline.py` interpolates traced points, which must have positive X and strictly increasing Y.
- `left`, `right`, `left_attachment` and `right_attachment` are open wires in local XY, all running from the lower-Y end to the upper-Y end. They stay in the local frame when the block moves.
- `attachment_offset` is the normal inward distance in mm; zero uses the original curves. Offsets that fail, leave the footprint or cross the centerline are rejected. The open offset's endpoints are not extended back to the end caps.
- `attachment_point(side, fraction)` picks a leg center by normalized arc length, from 0 to 1, on an attachment curve. Use these points as the ends of downstream guides; interior guide points remain design parameters. Changing parameters requires rebuilding the guide, since there is no persistent constraint solver.
- `block` is the footprint (both halves closed by horizontal lines, built as a right half and mirrored) extruded from Z=0 toward +Z by `block_thickness`. To display a local guide with a placed block, use `guide.moved(violin.block.global_location)`.

## Shared mount

`mount_location` is a local `Location` at the midpoint of the original upper-Y closing line, on Z=0, with the outline's axes. For the bundled tracing it is `(0, 73.536, 0)`. It does not depend on the attachment offset or block thickness and does not move with the block. `mount_joint` is a rigid joint named `mount` on the block at that frame.

`violin.position_on(shoulder)` connects the shoulder's violin joint to `mount_joint`, moving the block once. Rest bodies are modeled in the same local XY and declare which of their frames meets `mount_location`; see the [rest spec](rest_spec.md#fitting-to-the-shoulder).

Preview: `uv run python -m shoulder_rest.parts.violin_outline.spline_violin_outline` shows the block, the four curves, an example guide polyline and the mount frame.
