# Rest geometry and assembly

`parts/rest_geometry.py` defines the `RestGeometry` protocol. Its four properties are:

- `part`: a finished, un-nested, `Part` containing one solid before leg cuts. It may remain in its local modeling frame or already carry its fitted pose.
- `left_mount_joint`, `right_mount_joint`: rigid installation joints registered on `part`. Mount X follows the rod; mount Z points into the material.
- `violin_joint`: a rigid joint registered on the same `part`, defining its violin attachment, including any spacing and tilt.

The three joints must be distinct and belong to the final body, including after Boolean operations. Implementations choose their labels; `Rest` reads local frames directly from the typed properties before installation. `Rest` passes distinct installation labels (`left_leg` and `right_leg`) to the leg implementations; those implementations own any attachment joints and resolve label conflicts. Implementations can subclass `RestGeometry` or satisfy the protocol structurally by supplying its four properties.

`SimpleRestGeometry` in `parts/simple_rest.py` builds an inspectable rounded blank and its joints, without a leg dependency. `Rest(geometry, leg, right_leg=None)` consumes that interface. The supplied template is used independently for both sides unless a separate `right_leg` is supplied. Attachment settings such as angles and limits belong to the leg implementation.

`Rest[InstallationT]` accepts `Leg[InstallationT]` for either side. Its `left` and `right` properties return `InstallationT`, and `installations` returns a tuple of those two results. `build_simple_rest` preserves the same parameter. Hinge templates infer `Rest[HingeLegInstallation]` without annotations or casts; different installation types require a shared interface or union. The common installation protocol describes only `body` and the neutral leg source frame `local_placement`; attachment methods belong to concrete implementations.

## Contouring and placement

A geometry implementation owns the relationship between its body, shoulder, and violin. It can position the references, subtract the shoulder from an oversized blank, then define the three joints on the finished body. For a blank modeled locally and positioned by `pose`, transform the shoulder's world-space cutter into the blank frame:

```python
local_tool = shoulder.extended.moved(pose.inverse())
body = (local_blank - local_tool).moved(pose)
# Define final joints with world locations pose * local_attachment_frame.
```

Alternatively, perform the Boolean in a common world frame and define joints in that same frame. The resulting part and its registered joints must describe the same placement. The geometry implementation can use those joints to position reference parts before handing the body to `Rest`. Construction does not rely on carrying those joints or connections through Boolean cuts.

`Rest` snapshots the three `relative_location` frames and passes the original body to `leg.install(body, at=local_frame, joint_label=...)`. Both installations modify the same `Part`, retaining its modeling frame and placement. There is no defensive body copy, joint-dictionary lookup, or type cast in `Rest`.

After both installations, `Rest` creates its public mount joints on the final body. Installations preserve existing site joints through subsequent cuts. `Rest` does not call attachment methods; the caller selects components and parameters through the concrete descriptors, for example `rest.left.attach_to(rest.assembly, angle=15)` and optionally `rest.left.attach_housing_to(rest.assembly)`.

Supplying a geometry transfers its body for construction and final assembly nesting. Leg implementations modify the supplied `Part` in place.

The `assembly` initially contains only the cut `part`; attachment calls add components explicitly. Its typed `violin_joint` reproduces the geometry's violin frame on the **whole assembly**, preserving the initial fit. No additional placement step is needed when the geometry was already positioned.

Typed joint properties retain references created after the final cut. Later placement updates the existing joints through their owning parts.

Use `violin.position_on(shoulder)` to establish the violin pose and `rest.position_on(violin)` to align the completed rest. Any fitting needed before leg installation belongs inside the concrete geometry implementation. The placement methods connect the matching joints internally and move only their receiver. Call them before scene nesting; they can be repeated while the parts remain top-level. Connections do not continuously track later movement. Move the whole rest assembly to keep its children together.

`left_mount_joint` and `right_mount_joint` belong to the printable body child. Their build123d locations are in rest assembly coordinates; apply the assembly's global placement for world coordinates. `installations` retains the concrete site descriptors; use `rest.part` for the final body. Hinge descriptors are frozen and provide repeatable leg/housing attachment methods plus world-positioned tool/housing snapshots.

## Print orientation

The rest body is PETG and is always printed with the flat leg-mounting face against the bed. Preserve this plane when shaping the body. In the body's local modeling frame this face is Z=0 and the material extends toward -Z, so the print build direction is local -Z. Undo any fitted assembly placement, then turn the body over and place the mounting face on the bed; the shoulder-fitting preview is not a print pose.

The hinge coupon export follows the same convention: rotate its source geometry 180° about X and translate its mounting face to print Z=0. STEP exports retain the modeling pose; coupon STLs are oriented for printing.

## Rounded bar geometry

`build_simple_rest(violin, leg, parameters, right_leg=None)` returns a `Rest` body and installation sites in the outline's local frame, ready for attachment and positioning:

- Leg centers are sampled at arc-length fractions 0.25 on the left attachment curve and 0.60 on the right.
- A straight slot profile joins the centers with semicircular ends, extruded from Z=0 toward -Z. Default width is 44 mm and thickness is 12 mm.
- Left and right mounts lie at the sampled centers on Z=0. Mount Z points into the body (-Z); opposite X directions across the bar orient both leg noses inward.
- The violin mount uses the outline's shared frame with a +12 mm local Z offset, placing the bar's top 12 mm below the violin when positioned.

The default bar retains the bundled hinge legs' complete housing guides after cutting. Other dimensions or leg implementations require checking remaining material. Angle limits describe kinematics, not collision-free articulation.

The body has neither an S-shaped path nor a shoulder contact contour. The preview positions it relative to the bundled shoulder but does not fit the bar to the cast. For a contoured implementation, transform the positioned shoulder's `extended` cutter into the body's modeling frame and finish shaping before handing the finished geometry to `Rest`.

Preview: `uv run python -m shoulder_rest.parts.simple_rest`.

## Half-bar shoulder contour

`ContouredRestGeometry(violin, shoulder, parameters)` in `parts/contoured_rest.py` is a second implementation of the same four-property interface. It calls `violin.position_on(shoulder)` during construction, so both references must remain un-nested. No leg implementation is involved in shaping.

`ContouredRestParameters` extends `SimpleRestParameters` with `contact_depth=80` mm and `contact_side="right"`. The whole slot footprint is extruded to the base thickness. A plane through the midpoint, perpendicular to the line between leg centers, divides the footprint into equal halves. The selected half is extruded from Z=0 to `-contact_depth` and united with the bar.

The blank receives a violin joint through `violin.add_mount_joint(blank, offset=Location((0, 0, violin_gap)))`. Connecting `violin.mount_joint` to this joint establishes the fitted pose. A private `BuildPart` inserts the blank at the local origin and subtracts `shoulder.extended` transformed into that same local frame. All three joints are created on the cut body in local coordinates, then the body is placed at the fitted pose. Passing it to `Rest` retains this fit without `rest.position_on(...)`.

The cut must remove material and leave one valid solid. The example's right half is fully trimmed by the shoulder surface; other placements or dimensions can leave an untrimmed end or cut into the mounting region. Inspect the preview after changes. This is a contouring example, without padding allowance or automatic leg-housing protection. Rebuild after changing the fit; moving the assembled rest does not recompute its contour.

Preview: `uv run python -m shoulder_rest.parts.contoured_rest`.

## W rest geometry

`parts/wrest.py` builds a W centerline in the violin's local XY plane from the right attachment toward the left. `w1`, `w2`, and `w3` are the lengths of its three middle strokes. Each signed angle is an absolute offset from `(-1, 0)`, independent of the preceding stroke: zero points left, positive slopes down, and negative slopes up. A final straight stroke reaches the left attachment. `right_extend` continues the first stroke past the right attachment, and `left_extend` continues the final stroke past the left attachment.

`first_radius`, `second_radius`, and `third_radius` round the three centerline bends in travel order. Each can differ; zero keeps a sharp bend. The attachments lie on straight portions of the outer strokes.

The final straight stroke is the tail: a rounded bar with total width `tail_width`, extruded from Z=0 to `-tail_thickness`. The head contains the remaining strokes and the joining fillet. Its front and back boundaries are offset from the centerline by `head_front_width` and `head_back_width`, respectively, with straight closing ends. Front is the left side of the right-to-left path, usually lower Y; back is the right side, usually upper Y. `head_depth` is the total oversized head depth below Z=0 and must exceed `tail_thickness`.

`WRestGeometry` places the violin on the shoulder, cuts only the head with `shoulder.extended` in the blank's local frame, then joins the untouched tail. The two footprints overlap at the joining fillet's end. Inspect the fit where the head extends beyond the shoulder cutter: material outside its footprint retains the full oversized depth.

Both leg mounts are created on the finished body at their respective violin attachment points on Z=0 (left fraction 0.46, right fraction 0.4). Mount X is perpendicular to that side's outward centerline tangent, matching the rod direction used by the straight bar; mount Z points into the body. The two X directions differ because the outer strokes have different angles. The violin joint and both leg mounts belong to the body, which stays in violin-local XY for inspection. `Rest` installs the legs using those local frames; `rest.position_on(violin)` then connects the assembly's violin joint and moves the whole rest to the fitted pose. Call it before nesting the rest and violin in a scene.

### Optional head caps

`WRestParameters.left_cap` and `right_cap` accept separate frozen `WHeadCapParameters` instances; `None` disables that end. The left head end is the transition to the tail, after the third centerline fillet. The right head end is the extended tip of the first stroke. Caps are applied after shoulder contouring and before joining the tail.

Each cap defines `angle` (default 10°), `height` (12 mm), `depth` (20 mm), and `blend_radius` (1 mm). Its end-face line passes through the end centerline at Z=`-height`. At signed distance `s` toward the front, it is Z=`-height - s*tan(angle)`. Thus zero is parallel to the Z=0 bottom segment, and a positive angle places the front at a more negative Z than the back. The angle must be strictly between -90° and 90°, and the line and cut must stay clear of the mounting face.

The cutting plane contains that line and the head's inward end tangent; its normal lies in the end face. A straight extrusion removes material toward -Z for the fixed `depth`, measured along that tangent. This uses the local tangent at the rounded head/tail transition on the left. The cut can create a step at its depth limit. Fillets round both the cap-to-step join and the step-to-shoulder join, or the direct cap-to-shoulder intersection when the planes meet without a step. Shoulder faces are captured from the contouring operation and followed through subsequent cuts and fillets. The tail is added afterward.

Setting `blend_radius=0` leaves sharp cuts for inspection. A cap that misses the head, reaches Z=0, disconnects the head, has no shoulder join to blend, or cannot accommodate the requested radius raises an error identifying the end. Adjust the dimensions and inspect the CAD preview; the radius is not reduced automatically.
