# Rest geometry and assembly

`parts/rest_geometry.py` defines the `RestGeometry` protocol. Its four properties are:

- `part`: a finished, un-nested, single-solid Part or Solid before leg cuts. Its location records the intended pose relative to the shoulder and violin.
- `left_mount_joint`, `right_mount_joint`: rigid installation joints registered on `part`. Mount X follows the rod; mount Z points into the material.
- `violin_joint`: a rigid joint registered on the same `part`, defining its violin attachment, including any spacing and tilt.

The three joints must be distinct and belong to the final body, including after Boolean operations. Implementations choose their labels; `Rest` reads local frames directly from the typed properties before installation. `Rest` passes distinct installation labels (`left_leg` and `right_leg`) to the leg implementations; those implementations own any attachment joints and resolve label conflicts. A geometry implementation can satisfy the protocol structurally; it need not inherit from `Rest` or `RestGeometry`.

`SimpleRestGeometry` in `parts/simple_rest.py` builds an inspectable rounded blank and its joints, without a leg dependency. `Rest(geometry, leg, right_leg=None)` consumes that interface. The supplied template is used independently for both sides unless a separate `right_leg` is supplied. Attachment settings such as angles and limits belong to the leg implementation.

## Contouring and placement

A geometry implementation owns the relationship between its body, shoulder, and violin. It can position the references, subtract the shoulder from an oversized blank, then define the three joints on the finished body. For a blank modeled locally and positioned by `pose`, transform the shoulder's world-space cutter into the blank frame:

```python
local_tool = shoulder.extended.moved(pose.inverse())
body = (local_blank - local_tool).moved(pose)
# Define final joints with world locations pose * local_attachment_frame.
```

Alternatively, perform the Boolean in a common world frame and define joints in that same frame. The resulting part and its registered joints must describe the same placement. The geometry implementation can use those joints to position reference parts before handing the body to `Rest`. Construction does not rely on carrying those joints or connections through Boolean cuts.

`Rest` snapshots the three `relative_location` frames and passes the original body to `leg.install(body, at=local_frame, joint_label=...)`. Each result supplies the body for the next installation, retaining the same modeling frame and placement. There is no defensive body copy, joint-dictionary lookup, or type cast in `Rest`.

After both installations, `Rest` creates its public mount joints on the final body and calls both results' `attach_to(final_body)`. Each result uses retained local placement data to create its own attachment joints or directly position its leg. No attachment joint must survive an intermediate cut. `Rest` has no knowledge of those joint types or connection settings.

Supplying a geometry transfers its body for construction and final assembly nesting. A leg implementation may modify it in place or return a new shape; callers should not rely on input immutability. The bundled hinge implementation uses Boolean results and leaves the input body unchanged, but this is not an orchestration requirement.

The completed `assembly` is a persistent Compound containing the final `part` and both installed leg assemblies. Its typed `violin_joint` reproduces the geometry's violin frame on the **whole assembly**, preserving the initial fit. No additional placement step is needed when the geometry was already positioned.

Typed joint properties retain references created after the final cut. Later placement updates the existing joints through their owning parts.

`position_on(violin)` is available for subsequent alignment to a violin. Call it before nesting the rest and violin in a scene; it can be repeated while they remain top-level. Connections do not continuously track later violin movement. Move the whole assembly to keep its children together.

`left_mount_joint` and `right_mount_joint` belong to the printable body child. Their build123d locations are in rest assembly coordinates; apply the assembly's global placement for world coordinates. `installations` retains cutting tools and housing guides as construction snapshots; its `rest` fields refer to the respective intermediate cut results. Use `rest.part` for the final body.

## Rounded bar geometry

`build_simple_rest(violin, leg, parameters, right_leg=None)` returns a fully assembled `Rest` in the outline's local frame, ready for positioning:

- Leg centers are sampled at arc-length fractions 0.25 on the left attachment curve and 0.60 on the right.
- A straight slot profile joins the centers with semicircular ends, extruded from Z=0 toward -Z. Default width is 44 mm and thickness is 12 mm.
- Left and right mounts lie at the sampled centers on Z=0. Mount Z points into the body (-Z); opposite X directions across the bar orient both leg noses inward.
- The violin mount uses the outline's shared frame with a +12 mm local Z offset, placing the bar's top 12 mm below the violin when positioned.

The default bar retains the bundled hinge legs' complete housing guides after cutting. Other dimensions or leg implementations require checking remaining material. Angle limits describe kinematics, not collision-free articulation.

The body has neither an S-shaped path nor a shoulder contact contour. The preview positions it relative to the bundled shoulder but does not fit the bar to the cast. For a contoured implementation, transform the positioned shoulder's `extended` cutter into the body's modeling frame and finish shaping before handing the finished geometry to `Rest`.

Preview: `uv run python -m shoulder_rest.parts.rest`.
