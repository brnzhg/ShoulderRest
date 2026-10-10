from dataclasses import dataclass
from math import cos, isfinite, radians, sin, tan

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeShape
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.Standard import Standard_Failure
from OCP.StdFail import StdFail_NotDone
from OCP.TopoDS import TopoDS

from build123d import (
    BuildLine, BuildPart, BuildSketch, Compound, Edge, Face, GeomType, Location,
    Mode, Part, Plane, Polyline, RigidJoint, Side, Vector, Wire,
    extrude, fillet, insert, make_face,
)

from shoulder_rest.parts.rest_geometry import RestGeometry
from shoulder_rest.parts.shoulder import Shoulder
from shoulder_rest.parts.violin_outline import ViolinOutline


@dataclass(frozen=True)
class WHeadCapParameters:
    """End-cap dimensions in mm and angle in degrees.

    Height is measured from Z=0 toward -Z at the head's end centerline point.
    Positive angle slopes the front toward -Z relative to the back. Depth follows
    the inward end tangent; blend_radius rounds the transition to the shoulder.
    Zero blend_radius leaves the cut sharp for inspection.
    """

    angle: float = 10
    height: float = 12
    depth: float = 20
    blend_radius: float = 1

    def __post_init__(self) -> None:
        if not isfinite(self.angle) or not -90 < self.angle < 90:
            raise ValueError("Cap angle must be finite and between -90 and 90 degrees")
        if not all(isfinite(v) and v > 0 for v in (self.height, self.depth)):
            raise ValueError("Cap height and depth must be finite and positive")
        if not isfinite(self.blend_radius) or self.blend_radius < 0:
            raise ValueError("Cap blend radius must be finite and nonnegative")


@dataclass(frozen=True)
class WRestParameters:
    """W dimensions in mm and stroke angles in degrees.

    All three angles are absolute offsets from (-1, 0) in local XY: zero
    points left, positive angles slope down, and negative angles slope up.
    tail_width is total width; head widths are offsets from the centerline.
    head_depth is the oversized depth below the mounting face before cutting.
    Radii follow the centerline from right to left at the ends of strokes 1,
    2, and 3. Zero leaves a sharp corner. The end extensions continue the
    adjacent strokes without introducing bends at the attachment points.
    Optional left_cap and right_cap trim the head ends independently.
    """

    w_angle1: float = 10
    w_angle2: float = -20
    w_angle3: float = 10

    w1: float = 40
    w2: float = 56
    w3: float = 36

    right_extend: float = 20
    left_extend: float = 10

    first_radius: float = 40
    second_radius: float = 10
    third_radius: float = 5

    tail_width: float = 24
    tail_thickness: float = 12
    head_front_width: float = 18
    head_back_width: float = 16
    head_depth: float = 80
    violin_gap: float = 12
    left_cap: WHeadCapParameters | None = None
    right_cap: WHeadCapParameters | None = None

    def __post_init__(self) -> None:
        lengths = (self.w1, self.w2, self.w3, self.right_extend,
                   self.left_extend, self.tail_width, self.tail_thickness,
                   self.head_front_width, self.head_back_width)
        radii = (self.first_radius, self.second_radius, self.third_radius)
        if not all(isfinite(value) and value > 0 for value in lengths):
            raise ValueError("W lengths, widths, and tail thickness must be finite and positive")
        if not isfinite(self.head_depth) or self.head_depth <= self.tail_thickness:
            raise ValueError("Head depth must be finite and greater than tail thickness")
        if not all(isfinite(value) and value >= 0 for value in radii):
            raise ValueError("W corner radii must be finite and nonnegative")
        if not all(isfinite(value) for value in
                   (self.w_angle1, self.w_angle2, self.w_angle3)):
            raise ValueError("W stroke angles must be finite")
        if not isfinite(self.violin_gap) or self.violin_gap < 0:
            raise ValueError("Violin gap must be finite and nonnegative")
        for cap in (self.left_cap, self.right_cap):
            if cap is not None:
                slope = -tan(radians(cap.angle))
                if cap.height <= max(self.head_front_width * slope,
                                     -self.head_back_width * slope):
                    raise ValueError("Cap line must stay below the Z=0 mounting face")


def _stroke(start: Vector, length: float, angle_from_left: float) -> Vector:
    """Advance at an absolute angle from the leftward (-X) axis."""
    direction = radians(angle_from_left)
    return start + Vector(-length * cos(direction), -length * sin(direction), 0)


def _rounded_centerline(
    left_attach: Vector, right_attach: Vector, p: WRestParameters,
) -> Wire:
    """Build the W path, extending its outer strokes past the attachments."""
    if right_attach.X <= left_attach.X:
        raise ValueError("Right attachment must lie to the right of the left attachment")

    first = _stroke(right_attach, p.w1, p.w_angle1)
    second = _stroke(first, p.w2, p.w_angle2)
    third = _stroke(second, p.w3, p.w_angle3)
    final_stroke = left_attach - third
    if final_stroke.length < 1e-7:
        raise ValueError("Last W stroke must reach a distinct left attachment")
    right_tip = right_attach - (first - right_attach).normalized() * p.right_extend
    left_tip = left_attach + final_stroke.normalized() * p.left_extend
    points = (
        right_tip, first, second, third, left_tip,
    )
    radii = (p.first_radius, p.second_radius, p.third_radius)

    with BuildLine(mode=Mode.PRIVATE) as centerline:
        Polyline(*points)
        for corner, radius in zip(points[1:-1], radii):
            if radius == 0:
                continue
            vertex = min(centerline.vertices(), key=lambda v: (Vector(v) - corner).length)
            fillet(vertex, radius)
    return centerline.wires()[0]


def _blank_sections(centerline: Wire, p: WRestParameters) -> tuple[Part, Part]:
    """Return a thin tail and an oversized head in local XY, below Z=0.

    The last straight stroke is the tail; the joining fillet belongs to the
    head. Front is the left side of the right-to-left path (usually lower Y).
    Head widths are distances from the centerline; tail_width is total width.
    """
    edges = centerline.order_edges()
    if len(edges) < 2:
        raise ValueError("W centerline must have distinct head and tail strokes")
    head_path = Wire(edges[:-1])
    tail_path = Wire(edges[-1:])
    with BuildSketch(mode=Mode.PRIVATE) as tail_footprint:
        make_face(tail_path.offset_2d(p.tail_width / 2, side=Side.BOTH))
    with BuildSketch(mode=Mode.PRIVATE) as head_footprint:
        make_face(head_path.offset_2d(p.head_front_width, side=Side.LEFT))
        make_face(head_path.offset_2d(p.head_back_width, side=Side.RIGHT))
    with BuildPart(mode=Mode.PRIVATE) as tail:
        extrude(tail_footprint.sketch, amount=-p.tail_thickness)
    with BuildPart(mode=Mode.PRIVATE) as head:
        extrude(head_footprint.sketch, amount=-p.head_depth)
    assert tail.part_local is not None and head.part_local is not None
    return tail.part_local, head.part_local


def _blank_from_centerline(centerline: Wire, p: WRestParameters) -> Part:
    """Join the tail and oversized head for inspecting or mounting the blank."""
    tail, head = _blank_sections(centerline, p)
    return tail + head


def _retained_faces(
    operation: BRepBuilderAPI_MakeShape, sources: list[Face], result: Part,
) -> list[Face]:
    """Follow captured contact faces through a cut or fillet."""
    candidates = []
    for face in sources:
        candidates.append(face)
        candidates.extend(Face(TopoDS.Face_s(s)) for s in operation.Modified(face.wrapped))
    return [f for f in result.faces() if any(f.is_same(c) for c in candidates)]


def _shared_edges(first: list[Face], second: list[Face]) -> list[Edge]:
    """Edges joining two captured sets of surfaces, without their perimeter."""
    first_edges = [e for f in first for e in f.edges()]
    second_edges = [e for f in second for e in f.edges()]
    shared = []
    for edge in first_edges:
        if (any(edge.is_same(e) for e in second_edges)
                and not any(edge.is_same(e) for e in shared)):
            shared.append(edge)
    return shared


def _blend_cap_edges(
    body: Part, edges: list[Edge], radius: float, contact_faces: list[Face],
) -> tuple[Part, list[Face]]:
    operation = BRepFilletAPI_MakeFillet(body.wrapped)
    for edge in edges:
        operation.Add(radius, edge.wrapped)
    try:
        result = Part(operation.Shape())
        if not result.is_valid or len(result.solids()) != 1:
            raise ValueError("Cap blend must leave one valid head solid")
    except (StdFail_NotDone, Standard_Failure) as error:
        raise ValueError("Cap blend failed; reduce blend_radius or adjust height/depth") from error
    return result, _retained_faces(operation, contact_faces, result)


def _cap_head(
    head: Part, contact_faces: list[Face], head_path: Wire,
    cap: WHeadCapParameters, *, left: bool,
) -> tuple[Part, list[Face]]:
    """Trim one head end, then round its transition to captured shoulder faces."""
    parameter = 1 if left else 0
    tip = head_path.position_at(parameter)
    tangent = head_path.tangent_at(parameter)
    inward = -tangent if left else tangent
    front = Vector(-tangent.Y, tangent.X, 0)
    theta = -radians(cap.angle)
    cap_plane = Plane(
        origin=tip + Vector(0, 0, -cap.height), x_dir=inward,
        z_dir=front * sin(theta) + Vector(0, 0, -cos(theta)),
    )
    stop_plane = Plane(origin=tip + inward * cap.depth, z_dir=inward)

    # Cover the head across its end face; the extrusion ends at the fixed depth.
    box = head.bounding_box()
    across = [(Vector(x, y, 0) - tip).dot(front)
              for x in (box.min.X, box.max.X) for y in (box.min.Y, box.max.Y)]
    along = [(Vector(x, y, 0) - tip).dot(inward)
             for x in (box.min.X, box.max.X) for y in (box.min.Y, box.max.Y)]
    a, b = min(across) - 1, max(across) + 1
    # The rounded outline can protrude outward past the centerline end plane.
    start = min(0, min(along)) - 1
    bottom = box.min.Z - box.size.length
    end_face = Plane(origin=tip + inward * start, x_dir=front, z_dir=inward)
    # End-face Y can be +Z or -Z depending on which end is being cut.
    vertical = end_face.y_dir.Z
    with BuildSketch(end_face, mode=Mode.PRIVATE) as profile:
        with BuildLine():
            Polyline(
                (a, (-cap.height + a * tan(theta)) * vertical),
                (b, (-cap.height + b * tan(theta)) * vertical),
                (b, bottom * vertical), (a, bottom * vertical), close=True,
            )
        make_face()
    with BuildPart(mode=Mode.PRIVATE) as cutter:
        extrude(profile.sketch, amount=cap.depth - start, dir=inward)
    assert cutter.part_local is not None
    removed = head & cutter.part_local
    if not removed or removed.volume < 1e-6:
        raise ValueError("Cap misses the head; reduce height or adjust depth")
    if removed.bounding_box().max.Z >= -1e-6:
        raise ValueError("Cap cut reaches the mounting face; increase height or reduce angle/depth")

    operation = BRepAlgoAPI_Cut(head.wrapped, cutter.part_local.wrapped)
    result = Part(operation.Shape())
    if not result.is_valid or len(result.solids()) != 1:
        raise ValueError("Cap cut must leave one valid head solid")
    contact_faces = _retained_faces(operation, contact_faces, result)
    if cap.blend_radius == 0:
        return result, contact_faces

    def plane_faces(body: Part, plane: Plane) -> list[Face]:
        return [f for f in body.faces()
                if f.geom_type == GeomType.PLANE and f.is_coplanar(plane)]

    # Round the cap-to-step join first; then the step (or cap itself) to shoulder.
    step_edges = _shared_edges(plane_faces(result, cap_plane),
                               plane_faces(result, stop_plane))
    if step_edges:
        result, contact_faces = _blend_cap_edges(
            result, step_edges, cap.blend_radius, contact_faces,
        )
    transition_faces = plane_faces(result, cap_plane) + plane_faces(result, stop_plane)
    shoulder_edges = _shared_edges(transition_faces, contact_faces)
    if not shoulder_edges:
        raise ValueError("Cap has no shoulder-surface join to blend; adjust height/depth")
    return _blend_cap_edges(result, shoulder_edges, cap.blend_radius, contact_faces)


def _contoured_head(
    head: Part, shoulder_tool: Compound,
) -> tuple[Part, list[Face]]:
    """Cut the shoulder contour and capture its contact faces for cap blends."""
    # OCCT history captures the actual shoulder faces, including planar ones.
    # Keep this ancestry through the cap cuts instead of guessing by face type.
    operation = BRepAlgoAPI_Cut(head.wrapped, shoulder_tool.wrapped)
    result = Part(operation.Shape())
    if not result.is_valid or len(result.solids()) != 1:
        raise ValueError("Shoulder cut must leave one valid W head solid")
    contact_faces = _retained_faces(operation, list(shoulder_tool.faces()), result)
    return result, contact_faces


def _capped_head(
    head: Part, contact_faces: list[Face], centerline: Wire, p: WRestParameters,
) -> Part:
    """Apply the optional cap cuts and blends to an already contoured head."""
    result = head
    head_path = Wire(centerline.order_edges()[:-1])
    for name, cap in (("left", p.left_cap), ("right", p.right_cap)):
        if cap is None:
            continue
        try:
            result, contact_faces = _cap_head(
                result, contact_faces, head_path, cap, left=name == "left",
            )
        except ValueError as error:
            raise ValueError(f"{name.capitalize()} head cap: {error}") from error
    return result


class WRestGeometry(RestGeometry):
    """Fit a W blank to a shoulder before installing any legs.

    The blank is modeled in violin-local XY, with its mounting face at Z=0
    and material toward -Z. Mount X is perpendicular to each outer stroke;
    mount Z points into the body. Construction positions the violin on the
    shoulder and transforms the shoulder cutter into the blank's frame.
    The finished body stays in local XY for inspection; position the completed
    Rest on the violin before nesting it in the fitting scene.
    """

    def __init__(
        self, violin: ViolinOutline, shoulder: Shoulder,
        parameters: WRestParameters = WRestParameters(),
    ) -> None:
        p = self.parameters = parameters
        violin.position_on(shoulder)
        left = violin.attachment_point("left", 0.46)
        right = violin.attachment_point("right", 0.4)

        # Create the oversized blank and mount it to the violin.
        violin_joint_offset = Location((0, 0, p.violin_gap))
        centerline = _rounded_centerline(left, right, p)
        tail, head = _blank_sections(centerline, p)
        blank = tail + head
        blank_joint = violin.add_mount_joint(blank, offset=violin_joint_offset)
        
        violin.mount_joint.connect_to(blank_joint)
        pose = Location(blank.location)

        # Finish the shoulder contour first, then cut and blend the head caps.
        head, contact_faces = _contoured_head(head, shoulder.extended.moved(pose.inverse()))
        head = _capped_head(head, contact_faces, centerline, p)
        # Join the untrimmed tail after shaping the head.
        with BuildPart(mode=Mode.PRIVATE) as contoured:
            insert(head)
            insert(tail)
        body = contoured.part_local
        if body is None or not body.is_valid or len(body.solids()) != 1:
            raise ValueError("Shoulder cut must leave one valid W rest solid")

        # The centerline runs right to left. Its end tangents give the outward
        # directions of the two straight mounting strokes.
        right_outward = -centerline.tangent_at(0)
        left_outward = centerline.tangent_at(1)
        left_across = Vector(left_outward.Y, -left_outward.X, 0)
        right_across = Vector(right_outward.Y, -right_outward.X, 0)
        self._part = body
        self._left_mount_joint = RigidJoint(
            "left_mount", self._part,
            Location(Plane(origin=left, x_dir=left_across, z_dir=(0, 0, -1))),
        )
        self._right_mount_joint = RigidJoint(
            "right_mount", self._part,
            Location(Plane(origin=right, x_dir=right_across, z_dir=(0, 0, -1))),
        )
        self._violin_joint = violin.add_mount_joint(self._part, offset=violin_joint_offset)

    @property
    def part(self) -> Part:
        return self._part

    @property
    def left_mount_joint(self) -> RigidJoint:
        return self._left_mount_joint

    @property
    def right_mount_joint(self) -> RigidJoint:
        return self._right_mount_joint

    @property
    def violin_joint(self) -> RigidJoint:
        return self._violin_joint
    
    
    
if __name__ == "__main__":
    from build123d import Compound, Pos, Rotation
    from ocp_vscode import show

    from shoulder_rest.parts.leg.hinge_leg import build_hinge_leg
    from shoulder_rest.parts.rest import Rest
    from shoulder_rest.parts.shoulder.step_shoulder import load_shoulder_cast
    from shoulder_rest.parts.violin_outline.spline_violin_outline import build_violin_outline

    shoulder = load_shoulder_cast(
        cast_location=Location((0, 0, 0), (30, 30, -5)),
        violin_location=(
            Pos(-55, -87.5, 57.5)
            * Rotation(0, 0, 66)
            * Rotation(8, 0, 0)
            * Location((18, 2, 24), (0, -24, 0))
        ),
    )
    violin = build_violin_outline()
    geometry = WRestGeometry(violin, shoulder, WRestParameters(
        left_cap=WHeadCapParameters(angle=24, height=34, depth=30),
        right_cap=WHeadCapParameters(angle=10, height=30, depth=20),
    ))
    show(geometry.part)  # Inspect the local body before assembling it.
    rest = Rest(geometry, build_hinge_leg())
    rest.position_on(violin)

    scene = Compound(label="WRest fitting", children=[
        shoulder.assembly, violin.block, rest.assembly,
    ])
    rest.left.attach_to(rest.assembly, angle=20)
    rest.right.attach_to(rest.assembly)
    rest.left.attach_housing_to(rest.assembly)
    rest.right.attach_housing_to(rest.assembly)
    #show(scene)
