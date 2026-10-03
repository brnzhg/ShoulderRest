# Rest geometry and assembly

`parts/rest_geometry.py` defines the `RestGeometry` protocol. Its four properties are:

- `part`: a finished, un-nested, `Part` containing one solid before leg cuts. Its location records the intended pose relative to the shoulder and violin.
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

The blank receives a violin joint through `violin.add_mount_joint(blank, offset=Location((0, 0, violin_gap)))`. Connecting `violin.mount_joint` to this joint establishes the fitted pose. A private `BuildPart(pose)` inserts the blank at the local origin and subtracts `shoulder.extended` transformed into that same local frame. The builder returns a fresh body at the fitted pose without the blank's joint metadata. All three joints are created on that final body. Passing it to `Rest` retains this fit without `rest.position_on(...)`.

The cut must remove material and leave one valid solid. The example's right half is fully trimmed by the shoulder surface; other placements or dimensions can leave an untrimmed end or cut into the mounting region. Inspect the preview after changes. This is a contouring example, without padding allowance or automatic leg-housing protection. Rebuild after changing the fit; moving the assembled rest does not recompute its contour.

Preview: `uv run python -m shoulder_rest.parts.contoured_rest`.
