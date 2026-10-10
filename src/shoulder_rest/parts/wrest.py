from dataclasses import dataclass
from math import cos, isfinite, radians, sin

from build123d import (
    BuildLine, BuildPart, Location, Mode, Part, Plane, Polyline, RigidJoint,
    Side, Vector, Wire,
    extrude, fillet, insert, make_face, offset,
)

from shoulder_rest.parts.rest_geometry import RestGeometry
from shoulder_rest.parts.shoulder import Shoulder
from shoulder_rest.parts.violin_outline import ViolinOutline


@dataclass(frozen=True)
class WRestParameters:
    """W dimensions in mm and stroke angles in degrees.

    All three angles are absolute offsets from (-1, 0) in local XY: zero
    points left, positive angles slope down, and negative angles slope up.
    Radii follow the centerline from right to left at the ends of strokes 1,
    2, and 3. Zero leaves a sharp corner. The end extensions continue the
    adjacent strokes without introducing bends at the attachment points.
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

    tail_thickness: float = 12
    violin_gap: float = 12
    
    tail_width: float = 24
    head_front_width: float = 18
    head_back_width: float = 16
    

    def __post_init__(self) -> None:
        lengths = (self.w1, self.w2, self.w3, self.right_extend,
                   self.left_extend, self.tail_thickness)
        radii = (self.first_radius, self.second_radius, self.third_radius)
        if not all(isfinite(value) and value > 0 for value in lengths):
            raise ValueError("W stroke lengths, extensions, and thickness must be positive")
        if not all(isfinite(value) and value >= 0 for value in radii):
            raise ValueError("W corner radii must be finite and nonnegative")
        if not all(isfinite(value) for value in
                   (self.w_angle1, self.w_angle2, self.w_angle3)):
            raise ValueError("W stroke angles must be finite")
        if not isfinite(self.violin_gap) or self.violin_gap < 0:
            raise ValueError("Violin gap must be finite and nonnegative")


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


def _blank_from_centerline(centerline: Wire, p: WRestParameters) -> Part:
    """Thicken a local XY centerline into a blank below Z=0."""
    outline = offset(
        centerline, amount=p.tail_thickness / 2,
        side=Side.BOTH, closed=True,
    )
    footprint = make_face(outline)
    with BuildPart(mode=Mode.PRIVATE) as blank:
        extrude(footprint, amount=-p.tail_thickness)
    assert blank.part_local is not None
    return blank.part_local



class WRestGeometry(RestGeometry):
    """Fit a W blank to a shoulder before installing any legs.

    The blank is modeled in violin-local XY, with its mounting face at Z=0
    and material toward -Z. Mount X follows each outer stroke across the W;
    mount Z points into the body. Construction positions the violin and body
    at the shoulder's violin frame before the shoulder cut.
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
        blank = _blank_from_centerline(centerline, p)
        blank_joint = violin.add_mount_joint(blank, offset=violin_joint_offset)
        
        violin.mount_joint.connect_to(blank_joint)
        pose = Location(blank.location)

        # Cut in the blank's local frame; place the finished body after adding joints.
        with BuildPart(mode=Mode.PRIVATE) as contoured:
            insert(blank.located(Location()))
            insert(shoulder.extended.moved(pose.inverse()), mode=Mode.SUBTRACT)
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
        self._part.locate(pose)

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
    geometry = WRestGeometry(violin, shoulder)
    rest = Rest(geometry, build_hinge_leg())
    scene = Compound(label="WRest fitting", children=[
        shoulder.assembly, violin.block, rest.assembly,
    ])
    rest.left.attach_to(rest.assembly, angle=20)
    rest.right.attach_to(rest.assembly)
    rest.left.attach_housing_to(rest.assembly)
    rest.right.attach_housing_to(rest.assembly)
    show(scene)
