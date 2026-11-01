# Rest geometry and assembly

## Interface

`parts/rest/rest.py` defines the interface:

- `RestGeometry(part, left_mount, right_mount, violin_mount)`: a frozen record of a finished body, before leg cavities. `part` is one valid, un-nested solid in its local modeling frame. That frame shares XY with the violin outline, with the flat leg-mounting face at Z=0 and material toward -Z. The three frames are `Location`s in the same coordinates.
- `leg_mount(center, facing)`: a mount frame at `center` on Z=0, with Z into the body (-Z) and mount +Y along `facing`. Hinge legs put their rod on mount X and their nose toward +Y, so passing the inward direction turns both noses inward.
- `Rest(geometry, leg, right_leg=None)`: calls `leg.install(body, at=mount)` for the left side, then the right side, on the result. Each install returns a new body; nothing is modified in place. `right_leg` defaults to `leg`.

`Rest` owns the cut body (`part`) and an `assembly` holding it. The assembly's frame is the body's local frame. `left` and `right` are the installations returned by the legs, typed as the leg's installation type. They produce components in the body's frame, such as `rest.left.leg(angle=15)` or `rest.left.housing`, and `rest.add(component)` puts each into the assembly. Components can be added before or after positioning or nesting the rest. build123d rebuilds a compound at the origin when its children change, so `add` restores the pose of the assembly and of each ancestor.

`rest.left_mount_joint` and `rest.right_mount_joint` are rigid joints on the cut `part` at the two leg mount frames. Because they belong to the body, they follow it through positioning and nesting. `rest.violin_joint` lies on the whole assembly at `geometry.violin_mount`. `rest.position_on(violin)` connects `violin.mount_joint` to it, moving the whole rest once. Call it after `violin.position_on(shoulder)` and before nesting either in a scene, and again if the violin moves.

## Fitting to the shoulder

A rest design never moves the shoulder or violin. `Shoulder.cutter(violin_mount)` returns the extended cast in the body's local frame. It is placed so that the shoulder's `violin_location` coincides with the body's `violin_mount`, which is exactly where the body lands after positioning. Subtract it from an oversized blank, then build the `RestGeometry` from the result.

`violin.mount_location * Pos(0, 0, gap)` places the rest `gap` mm below the violin, with identical XY alignment. A general offset, including tilt, moves the rest by its inverse relative to the violin. The fit is fixed at construction: rebuild the geometry after changing the shoulder's violin placement or the gap.

## Print orientation

The rest body is PETG and is always printed with the flat leg-mounting face against the bed. Preserve this plane when shaping the body. In the local modeling frame this face is Z=0 and material extends toward -Z, so the print build direction is local -Z. Export `rest.part` in its local frame, turn it over, and place the mounting face on the bed; the fitted scene is not a print pose.

The hinge coupon export follows the same convention: it rotates the source geometry 180° about X and translates its mounting face to print Z=0. STEP exports keep the modeling pose; coupon STLs are oriented for printing.

## Bar rests

`parts/rest/bar_rest.py` builds rounded bars between two leg centers. `BarRestParameters` sets `width` (30), `thickness` (12), `violin_gap` (12) and the arc-length fractions `left_fraction` and `right_fraction` (0.4 each) on the attachment curves.

- `bar_rest_geometry(violin, parameters)`: a `SlotCenterToCenter` footprint joining the leg centers, extruded from Z=0 to `-thickness`. It has no shoulder contour.
- `contoured_bar_rest_geometry(violin, shoulder, parameters)`: `ContouredBarRestParameters` adds `contact_depth` (80) and `contact_side` (`"right"`). A plane through the midpoint, perpendicular to the line between leg centers, splits the footprint. The contact half is extruded to `-contact_depth`, and the shoulder cutter trims it. The cut must remove material and leave one valid solid; other placements or dimensions can leave an untrimmed end or cut into the mounting region.

In both, the legs face each other along the bar. The default dimensions retain the hinge legs' full housing guides; check the remaining material after other changes.

## W rest

`parts/rest/w_rest.py` builds a W-shaped body with `w_rest_geometry(violin, shoulder, parameters)`. `WRestParameters` groups its settings as `path`, `head` and `tail`, plus `top_radius` (1), `violin_gap` (12) and the leg-center fractions `left_fraction` (0.46) and `right_fraction` (0.4).

### Centerline (`WPathParameters`)

The centerline runs right to left in violin-local XY. It starts at the right leg center and follows `strokes`, by default `Stroke(40, 10)`, `Stroke(56, -20)` and `Stroke(36, 10)`. Each stroke has a length and an absolute angle measured from leftward (-X): zero points left, positive slopes toward -Y and negative toward +Y. A final straight tail stroke reaches the left leg center. `right_extend` (20) and `left_extend` (10) continue the first stroke and the tail stroke past their leg centers, so both centers lie on straight runs.

`bend_radii` (40, 10) round the bends between consecutive head strokes, in travel order; zero keeps a bend sharp. The bend into the tail is always sharp. `FilletPolyline` builds the whole path.

Front is the left side of the right-to-left travel, usually -Y; back is the right side.

### Head (`WHeadParameters`)

The head is a band around the head strokes, `front_width` (18) to the front and `back_width` (16) to the back, closed flat at both ends. Its left end is the sharp bend into the tail. It is extruded to the oversized `depth` (80), which must exceed the tail thickness, and cut with the shoulder cutter. Every head side wall reaches Z=0, so until the tail joins, the head's bottom (contact, caps and blends) is exactly the set of faces lying entirely below Z=0.

`left_cap` and `right_cap` optionally trim each end with a `WHeadCapParameters` after the shoulder cut, before the tail is joined:

- The cap line crosses the end's centerline at Z=`-height` (12). At signed distance `s` toward the front, it is at Z=`-height - s*tan(angle)`. Zero `angle` (default 10°) is level, and a positive angle lowers the front. The angle must be strictly between -90° and 90°, and the line must stay below the mounting face.
- The cutting plane contains that line and the end's inward tangent. A box below the plane removes material up to a stop plane `depth` (20) mm inward. The left cap follows stroke 3 inward, independent of the tail angle.
- `blend_radius` (10) first rounds the cap-to-step join, if the cut left a step, then the seam where the trim (cap, step and step blend, the last selected with `Select.LAST`) meets the rest of the bottom. Zero leaves the cut sharp.

A cap that misses the head, reaches Z=0, disconnects the head, has no shoulder join to blend, or cannot take its blend radius raises an error naming its end. The radius is never reduced automatically.

### Tail (`WTailParameters`)

The tail is `width` (24) wide in total and `thickness` (12) deep. Its sides leave the head's end corners along two cubic Bézier curves that reach the straight tail sides `taper_length` (30) mm along the tail; the taper must be shorter than the tail stroke. Each curve is tangent to the head stroke at its start and to the tail stroke at its end. `taper_handle_ratio` (1/3) sets both handles as a fraction of the taper length; larger values hold the end directions longer. The free end closes flat, perpendicular to the tail, with `corner_radius` (4) rounding its two corners in the footprint sketch.

### Joining and rounding

After capping, the head's bottom faces are collected and the tail is joined. The join and the head corner fillets leave remnants of the head's end walls below Z=0, so shape history carries the bottom through those two steps. Rounding follows, in this order:

1. `head.corner_radius` (4) rounds the upright corners at both head ends. At the left end the tail covers the corners down to its underside, where head and tail meet tangentially, so only the edges below it are rounded.
2. `head.bottom_radius` (2) rounds the outline where the bottom faces meet the side walls, excluding seams within the bottom.
3. `tail.bottom_radius` (1) rounds the outline of the faces on the tail's underside plane, including its concave junction with the deeper head.
4. `top_radius` (1) rounds the outline of the Z=0 mounting face.

Zero disables any of these fillets. Whether a fillet succeeds depends on the fit: the capped preview supports a 2 mm head bottom radius, while the uncapped fit needs a contour or cap adjustment, or `head.bottom_radius=0`. Material outside the shoulder cutter keeps the full oversized depth, so inspect the fit where the head extends beyond the cast.

### Frames

Both leg mounts sit at their leg centers on Z=0 and face inward along their outer strokes, so their rod axes are perpendicular to those strokes. Because the outer strokes have different angles, the two mount X directions differ. The violin mount is `violin.mount_location` raised by `violin_gap`.
