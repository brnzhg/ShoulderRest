"""W-shaped rest: a deep head fitted to the shoulder, joined to a thin tail.

The centerline runs right to left in violin-local XY, from the right leg center
through the head strokes, then straight to the left leg center along the tail.
Front is the left side of that travel (usually -Y), back the right side.
Run to preview the rest on the bundled shoulder.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from math import cos, isfinite, radians, sin, tan

from build123d import (
    Align, Axis, Bezier, Box, BuildLine, BuildSketch, Compound, Edge, Face,
    FilletPolyline, GeomType, Line, Location, Mode, Part, Plane, Polyline, Pos,
    Select, Shape, Side, Sketch, Vector, Wire, extrude, fillet, make_face,
)
from build123d.topology import ShapeHistory

from shoulder_rest.parts._validation import single_solid
from shoulder_rest.parts.shoulder import Shoulder
from shoulder_rest.parts.violin_outline import ViolinOutline
from shoulder_rest.parts.rest import RestGeometry, leg_mount


@dataclass(frozen=True)
class Stroke:
    """A straight centerline run: length in mm, angle in degrees from leftward (-X).

    Zero points left, positive slopes toward -Y, negative toward +Y.
    """

    length: float
    angle: float

    def __post_init__(self) -> None:
        if not (isfinite(self.length) and self.length > 0 and isfinite(self.angle)):
            raise ValueError("Stroke length must be finite and positive, and its angle finite")

    @property
    def vector(self) -> Vector:
        angle = radians(self.angle)
        return Vector(-cos(angle), -sin(angle)) * self.length


@dataclass(frozen=True)
class WPathParameters:
    """Head strokes from the right leg center, and how far the ends extend.

    ``bend_radii`` round the bends between consecutive head strokes (zero keeps
    a bend sharp); the bend into the tail is always sharp. ``right_extend`` and
    ``left_extend`` continue the first head stroke and the tail stroke past
    their leg centers.
    """

    strokes: tuple[Stroke, ...] = (Stroke(40, 10), Stroke(56, -20), Stroke(36, 10))
    bend_radii: tuple[float, ...] = (40, 10)
    right_extend: float = 20
    left_extend: float = 10

    def __post_init__(self) -> None:
        if not self.strokes or len(self.bend_radii) != len(self.strokes) - 1:
            raise ValueError("Give at least one stroke and one bend radius between each pair")
        if not all(isfinite(r) and r >= 0 for r in self.bend_radii):
            raise ValueError("Bend radii must be finite and nonnegative")
        if not all(isfinite(v) and v > 0 for v in (self.right_extend, self.left_extend)):
            raise ValueError("End extensions must be finite and positive")


@dataclass(frozen=True)
class WHeadCapParameters:
    """Angled trim of one head end, in mm and degrees, applied after the shoulder cut.

    The cap line crosses the end's centerline ``height`` below Z=0; a positive
    ``angle`` lowers its front relative to its back. The trim reaches ``depth``
    inward along the head and ``blend_radius`` rounds it into the shoulder
    contour (zero leaves it sharp).
    """

    angle: float = 10
    height: float = 12
    depth: float = 20
    blend_radius: float = 10

    def __post_init__(self) -> None:
        if not isfinite(self.angle) or not -90 < self.angle < 90:
            raise ValueError("Cap angle must be finite and between -90 and 90 degrees")
        if not all(isfinite(v) and v > 0 for v in (self.height, self.depth)):
            raise ValueError("Cap height and depth must be finite and positive")
        if not isfinite(self.blend_radius) or self.blend_radius < 0:
            raise ValueError("Cap blend radius must be finite and nonnegative")


@dataclass(frozen=True)
class WHeadParameters:
    """The head band around the head strokes, cut to the shoulder.

    Widths are measured from the centerline. ``depth`` is the oversized depth
    below Z=0 before the shoulder cut. ``corner_radius`` rounds the upright end
    corners and ``bottom_radius`` the outline of the shoulder and cap surfaces.
    """

    front_width: float = 18
    back_width: float = 16
    depth: float = 80
    corner_radius: float = 4
    bottom_radius: float = 2
    left_cap: WHeadCapParameters | None = None
    right_cap: WHeadCapParameters | None = None

    def __post_init__(self) -> None:
        if not all(isfinite(v) and v > 0 for v in (self.front_width, self.back_width, self.depth)):
            raise ValueError("Head widths and depth must be finite and positive")
        if not all(isfinite(v) and v >= 0 for v in (self.corner_radius, self.bottom_radius)):
            raise ValueError("Head radii must be finite and nonnegative")
        for cap in (self.left_cap, self.right_cap):
            if cap is not None:
                drop = tan(radians(cap.angle))  # Cap line's fall per mm toward the front.
                if cap.height <= max(-self.front_width * drop, self.back_width * drop):
                    raise ValueError("Cap line must stay below the Z=0 mounting face")


@dataclass(frozen=True)
class WTailParameters:
    """The straight tail band, ``width`` wide in total and ``thickness`` deep.

    Its sides leave the head's end corners along cubic Bézier curves for
    ``taper_length`` mm along the tail; ``taper_handle_ratio`` sets their
    tangent handles as a fraction of that length. ``corner_radius`` rounds the
    free end's corners and ``bottom_radius`` the underside outline.
    """

    width: float = 24
    thickness: float = 12
    taper_length: float = 30
    taper_handle_ratio: float = 1 / 3
    corner_radius: float = 4
    bottom_radius: float = 1

    def __post_init__(self) -> None:
        if not all(isfinite(v) and v > 0 for v in (self.width, self.thickness, self.taper_length)):
            raise ValueError("Tail width, thickness and taper length must be finite and positive")
        if not isfinite(self.taper_handle_ratio) or not 0 < self.taper_handle_ratio <= 1:
            raise ValueError("Tail taper handle ratio must be in (0, 1]")
        if not all(isfinite(v) and v >= 0 for v in (self.corner_radius, self.bottom_radius)):
            raise ValueError("Tail radii must be finite and nonnegative")


@dataclass(frozen=True)
class WRestParameters:
    """Leg-center fractions along the attachment curves, gaps and top fillet in mm."""

    path: WPathParameters = WPathParameters()
    head: WHeadParameters = WHeadParameters()
    tail: WTailParameters = WTailParameters()
    top_radius: float = 1
    left_fraction: float = 0.46
    right_fraction: float = 0.4
    violin_gap: float = 12

    def __post_init__(self) -> None:
        if self.head.depth <= self.tail.thickness:
            raise ValueError("Head depth must be greater than tail thickness")
        if not all(isfinite(v) and v >= 0 for v in (self.top_radius, self.violin_gap)):
            raise ValueError("Top radius and violin gap must be finite and nonnegative")


def w_rest_geometry(
    violin: ViolinOutline, shoulder: Shoulder, p: WRestParameters = WRestParameters(),
) -> RestGeometry:
    """Cut the head to the shoulder and cap its ends, join the tail, then round edges.

    Whether the fillets succeed depends on the fit; radii are never reduced
    automatically. For example, the uncapped default fit cannot take the head
    bottom fillet. Material outside the shoulder cutter keeps the full
    oversized head depth, so inspect the fit where the head passes the cast.
    """
    left = violin.attachment_point("left", p.left_fraction)
    right = violin.attachment_point("right", p.right_fraction)
    violin_mount = violin.mount_location * Pos(0, 0, p.violin_gap)
    centerline = _centerline(right, left, p.path)
    *head_edges, tail_edge = centerline.order_edges()
    head_path, tail_path = Wire(head_edges), Wire([tail_edge])

    blank = extrude(_head_footprint(head_path, p.head), amount=-p.head.depth)
    head = single_solid(
        blank - shoulder.cutter(violin_mount), "Shoulder cut must leave one valid W head solid",
    )
    for end, cap in (("left", p.head.left_cap), ("right", p.head.right_cap)):
        if cap is not None:
            try:
                head = _cap(head, head_path, end, cap)
            except ValueError as error:
                raise ValueError(f"{end.capitalize()} head cap: {error}") from error

    # Joining the tail and rounding the head corners leave remnants of the head's
    # end walls below Z=0, so follow the bottom through them by history.
    bottom = _head_bottom(head)
    tail = extrude(_tail_footprint(head_path, tail_path, p), amount=-p.tail.thickness)
    body = head + tail
    bottom = _descendants(bottom, body)
    single_solid(body, "Joining the tail must leave one valid W rest solid")

    body, bottom = _round_head_corners(body, bottom, head_path, p)
    body = _fillet_outline(body, bottom, p.head.bottom_radius, "Head bottom fillet")
    tail_bottom = _faces_on(body, Plane.XY.offset(-p.tail.thickness))
    body = _fillet_outline(body, tail_bottom, p.tail.bottom_radius, "Tail bottom fillet")
    body = _fillet_outline(body, _faces_on(body, Plane.XY), p.top_radius, "Top fillet")
    body = single_solid(body, "W rest body must be one valid solid")
    body.label = "W rest body"

    # Each leg faces inward along its outer stroke.
    return RestGeometry(
        body,
        left_mount=leg_mount(left, facing=-(centerline % 1)),
        right_mount=leg_mount(right, facing=centerline % 0),
        violin_mount=violin_mount,
    )


def _front(direction: Vector) -> Vector:
    """Unit normal to the left of a direction in XY."""
    return Vector(-direction.Y, direction.X, 0).normalized()


def _centerline(right: Vector, left: Vector, path: WPathParameters) -> Wire:
    """Head strokes from the right center, then the tail to the left center, extended past both."""
    if right.X <= left.X:
        raise ValueError("Right leg center must lie to the right of the left leg center")
    corners = []
    point = right
    for stroke in path.strokes:
        point = point + stroke.vector
        corners.append(point)
    tail = left - corners[-1]
    if tail.length < 1e-7:
        raise ValueError("Tail stroke must reach a distinct left leg center")
    right_tip = right - path.strokes[0].vector.normalized() * path.right_extend
    left_tip = left + tail.normalized() * path.left_extend
    return FilletPolyline(right_tip, *corners, left_tip, radius=(*path.bend_radii, 0))


def _head_footprint(head_path: Wire, head: WHeadParameters) -> Sketch:
    """Band from front_width left of the head path to back_width right of it."""
    with BuildSketch(mode=Mode.PRIVATE) as footprint:
        make_face(head_path.offset_2d(head.front_width, side=Side.LEFT))
        make_face(head_path.offset_2d(head.back_width, side=Side.RIGHT))
    return footprint.sketch


def _tail_footprint(head_path: Wire, tail_path: Wire, p: WRestParameters) -> Sketch:
    """Tail band tapering from the head's end corners, with rounded free-end corners."""
    tail = p.tail
    if tail.taper_length >= tail_path.length:
        raise ValueError("Tail taper length must be shorter than the tail stroke")
    junction, head_direction = head_path @ 1, head_path % 1
    tip, tail_direction = tail_path @ 1, tail_path % 0
    head_front, tail_front = _front(head_direction), _front(tail_direction)
    taper_end = junction + tail_direction * tail.taper_length
    handle = tail.taper_length * tail.taper_handle_ratio
    half_width = tail.width / 2

    front_start = junction + head_front * p.head.front_width
    back_start = junction - head_front * p.head.back_width
    front_end = taper_end + tail_front * half_width
    back_end = taper_end - tail_front * half_width
    with BuildSketch(mode=Mode.PRIVATE) as footprint:
        with BuildLine():
            for start, end in ((front_start, front_end), (back_start, back_end)):
                Bezier(start, start + head_direction * handle, end - tail_direction * handle, end)
            Polyline(front_end, tip + tail_front * half_width, tip - tail_front * half_width, back_end)
            Line(back_start, front_start)
        make_face()
        if tail.corner_radius:
            free_end = footprint.vertices().sort_by(Axis(tip, tail_direction))[-2:]
            fillet(free_end, tail.corner_radius)
    return footprint.sketch


def _head_bottom(head: Part) -> list[Face]:
    """Shoulder contact, cap and blend faces of the head before the tail joins.

    Every head side wall reaches the Z=0 mounting face; the bottom lies entirely below it.
    """
    return [face for face in head.faces() if face.bounding_box().max.Z < -1e-6]


def _cap(head: Part, head_path: Wire, end: str, cap: WHeadCapParameters) -> Part:
    """Trim the "left" or "right" head end below an angled plane, then blend it into the contour."""
    t = 1 if end == "left" else 0
    tip, tangent = head_path @ t, head_path % t
    inward = -tangent if end == "left" else tangent
    front = _front(tangent)
    angle = radians(cap.angle)
    # The cap plane holds the inward direction and falls toward the front by
    # the cap angle. Its normal points down into the material to remove.
    cap_plane = Plane(
        origin=tip - Vector(0, 0, cap.height),
        x_dir=inward, z_dir=-(front * sin(angle) + Vector(0, 0, cos(angle))),
    )
    stop_plane = Plane(origin=tip + inward * cap.depth, z_dir=inward)

    # A box under the cap plane, with its inner face on the stop plane, covers the end.
    reach = 2 * head.bounding_box().diagonal
    inner_edge = Location(cap_plane.shift_origin(cap_plane.origin + inward * cap.depth))
    cutter = inner_edge * Box(reach, reach, reach, align=(Align.MAX, Align.CENTER, Align.MIN))
    removed = head & cutter
    if not removed or removed.volume < 1e-6:
        raise ValueError("Cap misses the head; reduce height or adjust depth")
    if removed.bounding_box().max.Z >= -1e-6:
        raise ValueError("Cap cut reaches the mounting face; increase height or reduce angle/depth")
    capped = single_solid(head - cutter, "Cap cut must leave one valid head solid")
    if cap.blend_radius == 0:
        return capped

    # Round the cap-to-step join first, then the seam where the trim (cap,
    # step and their blend) meets the rest of the bottom: the shoulder contour.
    step_blend: list[Face] = []
    step = _edges_between(_faces_on(capped, cap_plane), _faces_on(capped, stop_plane))
    if step:
        capped = _fillet(capped, step, cap.blend_radius, "Cap step blend")
        step_blend = list(capped.faces(Select.LAST))
    trim = _faces_on(capped, cap_plane) + _faces_on(capped, stop_plane) + step_blend
    trimmed = set(trim)
    contour = [face for face in _head_bottom(capped) if face not in trimmed]
    seam = _edges_between(trim, contour)
    if not seam:
        raise ValueError("Cap has no shoulder-surface join to blend; adjust height/depth")
    return single_solid(
        _fillet(capped, seam, cap.blend_radius, "Cap blend"), "Cap blend must leave one valid head solid",
    )


def _round_head_corners(
    body: Part, bottom: list[Face], head_path: Wire, p: WRestParameters,
) -> tuple[Part, list[Face]]:
    """Round the exposed upright corners at both head ends.

    The tail covers the left end's corners down to its underside, where the
    head and tail sides meet tangentially; only the edges below it are rounded.
    """
    if not p.head.corner_radius:
        return body, bottom

    def corners(t: float) -> list[Vector]:
        end, front = head_path @ t, _front(head_path % t)
        return [end + front * p.head.front_width, end - front * p.head.back_width]

    def at(edge: Edge, points: list[Vector]) -> bool:
        center = edge.center()
        return any((Vector(center.X, center.Y) - point).length < 1e-6 for point in points)

    below_tail = -p.tail.thickness + 1e-6
    edges = [
        edge for edge in body.edges().filter_by(Axis.Z)
        if at(edge, corners(0))
        or (at(edge, corners(1)) and edge.bounding_box().max.Z <= below_tail)
    ]
    if not edges:
        return body, bottom
    rounded = _fillet(body, edges, p.head.corner_radius, "Head corner fillet")
    return rounded, _descendants(bottom, rounded)


def _fillet_outline(body: Part, faces: list[Face], radius: float, name: str) -> Part:
    """Round where a set of faces meets the rest of the body, excluding seams within it."""
    if not radius:
        return body
    selected = set(faces)
    others = [face for face in body.faces() if face not in selected]
    return _fillet(body, _edges_between(faces, others), radius, name)


def _fillet(body: Part, edges: list[Edge], radius: float, name: str) -> Part:
    """Fillet edges, requiring one valid solid; ``name`` identifies the feature in errors.

    Returns the fillet's own result, which keeps its history for selecting faces.
    """
    if not edges:
        raise ValueError(f"{name} has no edges to round")
    try:
        result = body.fillet(radius, edges)
    except ValueError as error:
        raise ValueError(f"{name} failed; reduce its radius or adjust the fit") from error
    single_solid(result, f"{name} must leave one valid solid")
    return result


def _faces_on(body: Part, plane: Plane) -> list[Face]:
    return [f for f in body.faces() if f.geom_type == GeomType.PLANE and f.is_coplanar(plane)]


def _edges_between(faces: list[Face], others: list[Face]) -> list[Edge]:
    """Edges shared by one of faces and one of others, in a stable order."""
    other_edges = {edge for face in others for edge in face.edges()}
    return list(dict.fromkeys(e for face in faces for e in face.edges() if e in other_edges))


def _descendants(faces: Iterable[Face], result: Shape) -> list[Face]:
    """Faces of an operation's result that are, or were rebuilt from, the given input faces.

    Only the head bottom needs this, to survive the tail join and corner fillets.
    """
    history = ShapeHistory.of(result)
    if history is None:
        raise ValueError("Operation must record face history")
    trace = history.trace(face.wrapped for face in faces)
    return [
        face for face in result.faces()
        if trace.is_untouched(face.wrapped) or trace.is_modified(face.wrapped)
    ]


if __name__ == "__main__":
    from ocp_vscode import show

    from shoulder_rest.parts.leg.hinge_leg import HingeLeg
    from shoulder_rest.parts.leg.rod_retention import RodRetentionParameters
    from shoulder_rest.parts.rest import Rest
    from shoulder_rest.parts.shoulder.step_shoulder import load_shoulder_cast
    from shoulder_rest.parts.violin_outline.spline_violin_outline import build_violin_outline

    shoulder = load_shoulder_cast()
    violin = build_violin_outline()
    violin.position_on(shoulder)
    geometry = w_rest_geometry(violin, shoulder, WRestParameters(head=WHeadParameters(
        left_cap=WHeadCapParameters(angle=24, height=34, depth=30),
        right_cap=WHeadCapParameters(angle=10, height=30, depth=20),
    )))
    # show(geometry.part)  # Inspect the body in its local frame.
    rest = Rest(geometry, HingeLeg(rod_retention=RodRetentionParameters()))
    rest.add(rest.left.leg(angle=20))
    rest.add(rest.right.leg())
    rest.add(rest.left.housing)
    rest.add(rest.right.housing)
    rest.position_on(violin)
    show(Compound(label="W rest fitting", children=[shoulder.assembly, violin.block, rest.assembly]))
