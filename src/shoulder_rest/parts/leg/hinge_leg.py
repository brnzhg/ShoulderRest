"""Hinge-slot leg, cavity cutter and installation in the Onshape source frame.

The rod axis is X through the origin. The nut housing extends toward +Y;
the screw runs along Z. Lengths are in millimeters and angles in degrees.
"""

from copy import deepcopy
from dataclasses import dataclass, fields
from math import isfinite, radians, sqrt, tan

from build123d import (
    Align, Axis, Box, BuildPart, BuildSketch, Color, Compound, Cylinder,
    Face, Kind, Location, Locations, Mode, Part, Plane, Polygon,
    Rectangle, RevoluteJoint, RigidJoint,
    chamfer, extrude, fillet, insert, offset,
)

from shoulder_rest.parts.kun import KunParameters, nut_slot_face, screw_hole_face
from .leg import Leg, LegInstallation


@dataclass(frozen=True)
class RodParameters:
    """Actual metal stock dimensions; clearances belong to the receiving parts."""

    diameter: float = 2.0
    length: float = 20.0

    def __post_init__(self) -> None:
        if not all(isfinite(v) and v > 0 for v in (self.diameter, self.length)):
            raise ValueError("Rod dimensions must be finite and positive")


@dataclass(frozen=True)
class LegParameters:
    """Printable body dimensions and the hardware it receives."""

    rod: RodParameters = RodParameters()
    kun: KunParameters = KunParameters()
    width: float = 12.0
    wall: float = 2.0
    rear_relief_angle: float = 20.0
    edge_chamfer: float = 0.3
    rod_house_length: float = 6.2
    rod_bore_clearance: float = 0.3  # Added to diameter, not radius.
    housing_gap: float = 1.0
    nose_radius: float = 1.5

    def __post_init__(self) -> None:
        sizes = (self.width, self.wall, self.rod_house_length, self.nose_radius)
        gaps = (self.rod_bore_clearance, self.housing_gap, self.edge_chamfer)
        if not all(isfinite(v) for v in (*sizes, *gaps, self.rear_relief_angle)):
            raise ValueError("Leg dimensions must be finite")
        if min(sizes) <= 0 or min(gaps) < 0:
            raise ValueError("Sizes must be positive; clearances, gaps and chamfer may be zero")
        if not 0 < self.rear_relief_angle < 90:
            raise ValueError("Relief angle must be between 0 and 90 degrees")
        if self.nose_radius >= self.rod_half or self.rod_hole_diameter >= self.rod_house_length:
            raise ValueError("Nose radius and rod bore must fit inside the rod housing")
        if self.rod.length <= self.width:
            raise ValueError("Metal rod must extend beyond both sides of the printed leg")
        if self.edge_chamfer >= min(self.width / 2, self.wall, self.nose_radius):
            raise ValueError("Chamfer is too large for the housing")
        k = self.kun
        roof_x = k.screw_circle_offset - k.screw_diameter / 2 - k.screw_roof_extension
        if max(abs(roof_x), k.screw_flat_x) >= self.width / 2 - self.edge_chamfer:
            raise ValueError("Screw opening must fit between the side faces")

    @property
    def rod_hole_diameter(self) -> float:
        return self.rod.diameter + self.rod_bore_clearance

    @property
    def rod_half(self) -> float:
        return self.rod_house_length / 2

    @property
    def nose_swing_radius(self) -> float:
        """Maximum distance from the hinge axis to the rounded nose."""
        return sqrt(2) * (self.rod_half - self.nose_radius) + self.nose_radius

    @property
    def housing_start(self) -> float:
        return self.rod_half + self.housing_gap

    @property
    def screw_y(self) -> float:
        return self.housing_start + self.wall + self.kun.nut_slot_width / 2

    @property
    def rear_y(self) -> float:
        return self.housing_start + 2 * self.wall + self.kun.nut_slot_width

    @property
    def top_z(self) -> float:
        return self.rod_half + self.kun.nut_slot_height + self.wall


def _lower_body_profile(p: LegParameters) -> Face:
    """Shared side profile in sketch XY (horizontal=body Y, vertical=body Z)."""
    h = p.rod_half
    relief_width = h * tan(radians(p.rear_relief_angle))
    with BuildSketch(mode=Mode.PRIVATE) as profile:
        with Locations((-h, 0)):
            Rectangle(p.rear_y + h, p.rod_house_length, align=(Align.MIN, Align.CENTER))
        # Remove the triangular wedge beneath the rear wall.
        Polygon(
            (p.rear_y, 0), (p.rear_y, -h), (p.rear_y - relief_width, -h),
            align=None, mode=Mode.SUBTRACT,
        )
        fillet(profile.vertices().group_by(Axis.X)[0], p.nose_radius)
    return profile.face()


def _nut_housing_profile(p: LegParameters) -> Face:
    """Raised housing in the same sketch frame as the lower body."""
    with BuildSketch(mode=Mode.PRIVATE) as profile:
        with Locations((p.housing_start, p.rod_half)):
            Rectangle(
                p.rear_y - p.housing_start, p.top_z - p.rod_half,
                align=(Align.MIN, Align.MIN),
            )
    return profile.face()


def _body_profile(p: LegParameters) -> Face:
    """Combine the shared lower body and raised nut housing."""
    with BuildSketch(mode=Mode.PRIVATE) as profile:
        insert(_lower_body_profile(p))
        insert(_nut_housing_profile(p))
    return profile.face()


class HingeLegPart(Part):
    """One printable housing with rigid attachment frames.

    Joints: rod at the origin with its Z axis along +X; screw at the nominal
    screw entry on the bottom face with Z along +Z; nut at the nut seat center.
    Use these frames before nesting in an assembly.
    """

    def __init__(self, parameters: LegParameters = LegParameters()) -> None:
        p = self.parameters = parameters
        with BuildPart(mode=Mode.PRIVATE) as body:
            with BuildSketch(Plane.YZ):
                insert(_body_profile(p))
            extrude(amount=p.width / 2, both=True)

            # Finish the exterior before cutting, keeping seats and passages sharp.
            if p.edge_chamfer:
                side_perimeters = body.faces().filter_by(Axis.X).edges()
                top_cross_edges = body.edges().filter_by(Axis.X).group_by(Axis.Z)[-1]
                chamfer(side_perimeters + top_cross_edges, length=p.edge_chamfer)

            Cylinder(p.rod_hole_diameter / 2, p.width, rotation=(0, 90, 0), mode=Mode.SUBTRACT)
            nut_face = nut_slot_face(p.kun).moved(Location(
                (0, p.screw_y, p.rod_half + p.kun.nut_slot_height / 2)
            ))
            extrude(nut_face, amount=p.width / 2, both=True, dir=(1, 0, 0), mode=Mode.SUBTRACT)
            with BuildSketch(Plane.XY.offset(-p.rod_half)):
                with Locations((0, p.screw_y)):
                    insert(screw_hole_face(p.kun))
            extrude(amount=p.top_z + p.rod_half, mode=Mode.SUBTRACT)

        if body.part_local is None or not body.part_local.is_valid or len(body.solids()) != 1:
            raise ValueError("Dimensions did not produce a single valid leg housing")
        super().__init__(body.part_local.wrapped, label="Hinge slot leg")

        self._rod_joint = RigidJoint("rod", self, Location(Plane(origin=(0, 0, 0), z_dir=(1, 0, 0))))
        self._screw_joint = RigidJoint("screw", self, Location((0, p.screw_y, -p.rod_half)))
        self._nut_joint = RigidJoint("nut", self, Location((0, p.screw_y, p.rod_half)))

    @property
    def rod_joint(self) -> RigidJoint:
        """Rod axis on the printable child; use assembly joints for placement."""
        return self._rod_joint

    @property
    def screw_joint(self) -> RigidJoint:
        """Screw entry on the printable child."""
        return self._screw_joint

    @property
    def nut_joint(self) -> RigidJoint:
        """Nut seat on the printable child."""
        return self._nut_joint


@dataclass(frozen=True)
class CavityParameters:
    """Fit and insertion clearances, separate from the printable leg dimensions."""

    clearance: float = 0.1
    bottom_clearance: float = 0.1
    rod_slot_clearance: float = 0.1  # Added to the rod diameter.
    rod_slot_run: float = 3.0
    rod_slot_inner_radius: float = 0.2
    rod_slot_radius_clearance: float = 0.1  # Added to the rod radius.
    rod_length_clearance: float = 1.0  # Total extra length, split between both ends.
    housing_wall: float = 2.0
    rod_end_wall: float = 1.0

    def __post_init__(self) -> None:
        if any(not isfinite(getattr(self, f.name)) for f in fields(self)):
            raise ValueError("Cavity dimensions must be finite")
        if min(
            self.clearance, self.bottom_clearance, self.rod_slot_clearance,
            self.rod_slot_radius_clearance, self.rod_length_clearance,
        ) < 0 or min(
            self.rod_slot_run, self.rod_slot_inner_radius,
            self.housing_wall, self.rod_end_wall,
        ) <= 0:
            raise ValueError("Cavity sizes must be positive; clearances may be zero")

    def slot_width(self, rod: RodParameters) -> float:
        return rod.diameter + self.rod_slot_clearance

    def slot_outer_radius(self, rod: RodParameters) -> float:
        return rod.diameter / 2 + self.rod_slot_radius_clearance

    def tool_length(self, rod: RodParameters) -> float:
        return rod.length + self.rod_length_clearance


def _cavity_profile(p: LegParameters, c: CavityParameters) -> Face:
    """Shared lower profile with nose swing allowance, underside relief and fit."""
    h, reach = p.rod_half, p.nose_swing_radius
    with BuildSketch(mode=Mode.PRIVATE) as profile:
        insert(_lower_body_profile(p))
        # Preserve the source's rectangular allowance toward -Y and -Z.
        with Locations((-reach, -reach)):
            Rectangle(h + reach, h + reach, align=(Align.MIN, Align.MIN))
        if c.bottom_clearance:
            insert(profile.face().moved(Location((0, -c.bottom_clearance, 0))))
        if c.clearance:
            offset(amount=c.clearance, kind=Kind.INTERSECTION)
    return profile.face()


def _rod_slot_profile(p: LegParameters, c: CavityParameters) -> Face:
    """Diamond seat, horizontal channel and upright entry in the side profile."""
    width = c.slot_width(p.rod)
    half_width = width / 2
    seat_x = (1 - sqrt(2)) * half_width
    entry_x = seat_x + c.rod_slot_run
    with BuildSketch(mode=Mode.PRIVATE) as slot:
        with Locations((seat_x, 0)):
            # A rotated square gives the seat its two 45-degree contact faces.
            Rectangle(width / sqrt(2), width / sqrt(2), rotation=45)
            Rectangle(c.rod_slot_run + width, width, align=(Align.MIN, Align.CENTER))
        with Locations((entry_x, -half_width)):
            Rectangle(width, p.rod_half + half_width, align=(Align.MIN, Align.MIN))

        # Ease the inside and outside corners where the entry turns into the channel.
        for x, y, radius in (
            (entry_x, half_width, c.rod_slot_inner_radius),
            (entry_x + width, -half_width, c.slot_outer_radius(p.rod)),
        ):
            corners = [v for v in slot.vertices() if abs(v.X - x) < 1e-7 and abs(v.Y - y) < 1e-7]
            fillet(corners, radius)
    return slot.face()


def _cavity_tool(p: LegParameters, c: CavityParameters) -> Part:
    """Extrude the clearance silhouette and add the two-sided rod insertion slot."""
    if c.slot_outer_radius(p.rod) >= c.slot_width(p.rod):
        raise ValueError("Rod slot outer radius must fit inside its width")
    width = p.width + 2 * c.clearance
    rod_length = c.tool_length(p.rod)
    if rod_length <= width:
        raise ValueError("Rod must extend beyond both sides of the leg cavity")

    with BuildPart(mode=Mode.PRIVATE) as tool:
        with BuildSketch(Plane.YZ):
            insert(_cavity_profile(p, c))
        extrude(amount=width / 2, both=True)
        with BuildSketch(Plane.YZ):
            insert(_rod_slot_profile(p, c))
        extrude(amount=rod_length / 2, both=True)

    if tool.part_local is None or not tool.part_local.is_valid or len(tool.solids()) != 1:
        raise ValueError("Dimensions did not produce a single cavity tool")
    tool.part_local.label = "Leg cavity tool"
    return tool.part_local


def _housing_guide(p: LegParameters, c: CavityParameters, tool: Part) -> Part:
    """A simple symmetric material envelope, with the cavity already removed."""
    nose_reach = p.nose_swing_radius
    half_width = c.tool_length(p.rod) / 2 + c.rod_end_wall
    front = -nose_reach - c.housing_wall
    rear = p.rear_y + c.housing_wall
    bottom = -p.rod_half - c.housing_wall
    if bottom >= tool.bounding_box().min.Z or front >= tool.bounding_box().min.Y:
        raise ValueError("Housing wall must extend beyond the cavity's bottom and nose")
    with BuildPart(mode=Mode.PRIVATE) as guide:
        with Locations((-half_width, front, bottom)):
            Box(
                2 * half_width, rear - front, p.rod_half - bottom,
                align=(Align.MIN, Align.MIN, Align.MIN),
            )
        insert(tool, mode=Mode.SUBTRACT)
    if guide.part_local is None or not guide.part_local.is_valid or len(guide.solids()) != 1:
        raise ValueError("Housing wall must leave a connected guide around the cavity")
    guide.part_local.label = "Leg housing guide"
    return guide.part_local


@dataclass(frozen=True)
class HingeLegInstallation:
    """Hinge-specific result; captures the configured final angle in degrees."""
    leg: Compound
    tool: Part
    housing: Part
    joint_label: str
    rod_joint_label: str
    angle: float
    local_placement: Location
    angular_range: tuple[float, float]

    def attach_to(self, final_body: Part) -> None:
        """Create the hinge on the finished body and connect the installed rod."""
        if final_body.parent is not None or final_body.children or self.leg.parent is not None:
            raise ValueError("Attach the leg before nesting the body or leg in an assembly")
        if self.joint_label in final_body.joints:
            raise ValueError(f"Final body already has a joint named {self.joint_label!r}")
        placement = final_body.location * self.local_placement
        hinge = RevoluteJoint(
            self.joint_label, final_body, Axis.X.located(placement),
            angular_range=self.angular_range,
        )
        # Use this hinge's actual zero frame; an axis alone does not retain roll.
        self.leg.locate(placement)
        rod_joint = RigidJoint(self.rod_joint_label, self.leg, hinge.location)
        hinge.connect_to(rod_joint, angle=self.angle)


class HingeLeg(Leg):
    """Reusable leg template, cutter and housing guide sharing one source frame.

    The mount uses the Onshape connector's origin, with explicit axes: X along
    the rod and Z toward the rest (-Z in the source frame). Connect/install
    before nesting this leg assembly in the final assembly. Installation cuts
    the supplied body in place and copies the leg template. Move assembly, not
    its individual hardware children.
    """

    def __init__(
        self, parameters: LegParameters = LegParameters(),
        cavity: CavityParameters = CavityParameters(),
        *, angle: float = 0, angular_range: tuple[float, float] = (-180, 180),
    ) -> None:
        if not all(isfinite(a) for a in angular_range) or not angular_range[0] <= 0 <= angular_range[1]:
            raise ValueError("Angular range must be finite and include the neutral angle (0)")
        if not isfinite(angle) or not angular_range[0] <= angle <= angular_range[1]:
            raise ValueError("Hinge angle must be finite and within the angular range")
        self._angle = angle
        self._angular_range = angular_range
        self._part = HingeLegPart(parameters)
        self._tool = _cavity_tool(parameters, cavity)
        self._housing = _housing_guide(parameters, cavity, self._tool)
        with BuildPart(mode=Mode.PRIVATE) as rod:
            Cylinder(parameters.rod.diameter / 2, parameters.rod.length, rotation=(0, 90, 0))
        assert rod.part_local is not None
        self._rod = rod.part_local
        self._rod.label = "Metal hinge rod"
        self._rod.color = Color("silver")
        self._assembly = Compound(label="Hinge leg assembly", children=[self._part, self._rod])
        self._rod_joint = RigidJoint(
            self._part.rod_joint.label, self._assembly, self._part.rod_joint.location,
        )
        self._screw_joint = RigidJoint(
            self._part.screw_joint.label, self._assembly, self._part.screw_joint.location,
        )
        self._nut_joint = RigidJoint(
            self._part.nut_joint.label, self._assembly, self._part.nut_joint.location,
        )
        self._mount_joint = RigidJoint("mount", self._assembly, Location(Plane(
            origin=(0, parameters.screw_y, parameters.rod_half),
            x_dir=(1, 0, 0), z_dir=(0, 0, -1),
        )))

    @property
    def part(self) -> HingeLegPart:
        return self._part

    @property
    def assembly(self) -> Compound:
        return self._assembly

    @property
    def rod(self) -> Part:
        """Metal hardware child, centered on the printable leg's bore."""
        return self._rod

    @property
    def tool(self) -> Part:
        return self._tool.moved(self._assembly.global_location)

    @property
    def housing(self) -> Part:
        return self._housing.moved(self._assembly.global_location)

    @property
    def mount_joint(self) -> RigidJoint:
        return self._mount_joint

    @property
    def rod_joint(self) -> RigidJoint:
        """Rod attachment on the complete template assembly."""
        return self._rod_joint

    @property
    def screw_joint(self) -> RigidJoint:
        """Screw entry on the complete template assembly."""
        return self._screw_joint

    @property
    def nut_joint(self) -> RigidJoint:
        """Nut seat on the complete template assembly."""
        return self._nut_joint

    def install(
        self, body: Part, *, at: Location, joint_label: str = "leg",
    ) -> HingeLegInstallation:
        """Cut body in place and return it with an independent leg assembly."""
        if not isinstance(body, Part) or body.parent is not None or body.children:
            raise ValueError("Install on an un-nested Part before assembly")
        if not joint_label:
            raise ValueError("Choose a new, nonempty hinge joint label")

        local_placement = at * self.mount_joint.relative_location.inverse()
        placement = body.location * local_placement
        # Cut in the body's modeling frame; the builder restores its placement.
        with BuildPart(body.location, mode=Mode.PRIVATE) as installed:
            with Locations(body.location.inverse()):
                insert(body)
            with Locations(local_placement):
                insert(self._tool, mode=Mode.SUBTRACT)
        rest = installed.part
        assert rest is not None
        if not rest.is_valid or len(rest.solids()) != 1:
            raise ValueError("Installation must leave one valid connected rest solid")
        if body.volume - rest.volume < 1e-7:
            raise ValueError("Cavity tool does not intersect the rest")

        # Replace only the geometry, retaining the body's identity and attributes.
        body.wrapped = rest.wrapped

        return HingeLegInstallation(
            leg=deepcopy(self._assembly).locate(placement),
            tool=self._tool.moved(placement),
            housing=self._housing.moved(placement),
            joint_label=joint_label,
            rod_joint_label=self.rod_joint.label,
            angle=self._angle,
            local_placement=local_placement,
            angular_range=self._angular_range,
        )


def build_hinge_leg(
    parameters: LegParameters = LegParameters(),
    cavity: CavityParameters = CavityParameters(),
    *, angle: float = 0, angular_range: tuple[float, float] = (-180, 180),
) -> HingeLeg:
    """Build a hinge template with its final attachment angle and limits in degrees."""
    return HingeLeg(parameters, cavity, angle=angle, angular_range=angular_range)


if __name__ == "__main__":
    from ocp_vscode import show

    leg = build_hinge_leg()
    show(leg.assembly, leg.tool, leg.housing, leg.mount_joint.symbol)
