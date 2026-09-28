"""Hinge-slot leg, cavity cutter and installation in the Onshape source frame.

The rod axis is X through the origin. The nut housing extends toward +Y;
the screw runs along Z. Lengths are in millimeters and angles in degrees.
"""

from copy import deepcopy
from dataclasses import dataclass, fields
from math import atan2, cos, isclose, isfinite, radians, sin, sqrt, tan
from typing import Protocol, cast

from build123d import (
    Axis, Edge, Face, GeomType, Location, Part, Plane, RevoluteJoint, RigidJoint,
    ShapeList, Solid, Wire,
)


@dataclass(frozen=True)
class LegParameters:
    """Dimensions of the Onshape Leg, including its printable screw profile."""

    width: float = 12.0
    wall: float = 2.0
    rear_relief_angle: float = 20.0
    edge_chamfer: float = 0.3

    # nut slot
    nut_slot_width: float = 8.65
    nut_slot_height: float = 3.4

    # rod housing
    rod_house_length: float = 6.2
    rod_hole_diameter: float = 2.2 # rod diameter = 2, # clearance .2
    housing_gap: float = 1.0 # gap between the rod housing and the nut housing
    nose_radius: float = 1.5 # radius of the rounded nose at the hinge point

    # screw hole parameters, TODO split this out to its own part
    screw_diameter: float = 4.0
    screw_circle_offset: float = 0.1  # Circle center's X offset from the nominal screw axis.
    screw_flat_x: float = 1.9        # Flat side of the opening in the print direction.
    screw_roof_extension: float = 0.2
    screw_tangent_angle: float = 40.0  # Tangency point angle measured from -X.

    def __post_init__(self) -> None:
        if any(not isfinite(getattr(self, field.name)) for field in fields(self)):
            raise ValueError("Leg dimensions must be finite")
        positive = (
            self.width, self.nut_slot_width, self.nut_slot_height, self.wall,
            self.rod_house_length, self.rod_hole_diameter, self.nose_radius,
            self.screw_diameter, self.screw_flat_x,
        )
        if min(positive) <= 0 or min(
            self.housing_gap, self.edge_chamfer, self.screw_roof_extension
        ) < 0:
            raise ValueError("Sizes must be positive; gaps, chamfer and roof extension may be zero")
        if not 0 < self.rear_relief_angle < 90 or not 0 < self.screw_tangent_angle < 90:
            raise ValueError("Relief and tangent angles must be between 0 and 90 degrees")
        if self.nose_radius >= self.rod_half or self.rod_hole_diameter >= self.rod_house_length:
            raise ValueError("Nose radius and rod bore must fit inside the rod housing")
        if self.edge_chamfer >= min(self.width / 2, self.wall, self.nose_radius):
            raise ValueError("Chamfer is too large for the housing")
        radius = self.screw_diameter / 2
        if not 0 <= self.screw_circle_offset < radius:
            raise ValueError("Screw circle offset must be between zero and its radius")
        roof_x = self.screw_circle_offset - radius - self.screw_roof_extension
        if max(abs(roof_x), self.screw_flat_x) >= self.width / 2 - self.edge_chamfer:
            raise ValueError("Screw opening must fit between the side faces")
        if self.screw_diameter >= self.nut_slot_width:
            raise ValueError("Screw opening must fit within the nut slot width")

    @property
    def rod_half(self) -> float:
        return self.rod_house_length / 2

    @property
    def housing_start(self) -> float:
        return self.rod_half + self.housing_gap

    @property
    def screw_y(self) -> float:
        return self.housing_start + self.wall + self.nut_slot_width / 2

    @property
    def rear_y(self) -> float:
        return self.housing_start + 2 * self.wall + self.nut_slot_width

    @property
    def top_z(self) -> float:
        return self.rod_half + self.nut_slot_height + self.wall


def _body_profile(p: LegParameters) -> Face:
    """Side silhouette on YZ: rounded hinge nose, raised nut housing, rear relief."""
    h = p.rod_half
    side_points = [
        (-h, -h),
        (p.rear_y - h * tan(radians(p.rear_relief_angle)), -h),
        (p.rear_y, 0),
        (p.rear_y, p.top_z),
        (p.housing_start, p.top_z),
        (p.housing_start, h),
        (-h, h),
    ]
    profile = Face(Wire.make_polygon([(-p.width / 2, y, z) for y, z in side_points]))
    nose_corners = [v for v in profile.vertices() if isclose(v.Y, -h, abs_tol=1e-7)]
    return profile.fillet_2d(p.nose_radius, nose_corners)


def _screw_profile(p: LegParameters) -> Face:
    """Flat-backed circular opening with tangent roof slopes and a clipped tip.

    The circular sides preserve the screw clearance; the flats and roof match
    the source's print-oriented opening rather than approximating it as a bore.
    """
    radius = p.screw_diameter / 2
    center_x = p.screw_circle_offset
    angle = radians(p.screw_tangent_angle)
    half_span = sqrt(radius**2 - center_x**2)
    tangent_x = center_x - radius * cos(angle)
    tangent_y = radius * sin(angle)
    roof_x = center_x - radius - p.screw_roof_extension
    roof_y = tangent_y - (tangent_x - roof_x) / tan(angle)
    if tangent_x >= 0 or roof_y <= 0:
        raise ValueError("Screw tangent angle/roof extension cannot form the clipped roof")

    def point(x: float, y: float) -> tuple[float, float, float]:
        return (x, p.screw_y + y, -p.rod_half)

    flat_low = point(p.screw_flat_x, -half_span)
    flat_high = point(p.screw_flat_x, half_span)
    arc_high = point(0, half_span)
    tangent_high = point(tangent_x, tangent_y)
    roof_high = point(roof_x, roof_y)
    roof_low = point(roof_x, -roof_y)
    tangent_low = point(tangent_x, -tangent_y)
    arc_low = point(0, -half_span)

    # Midpoints specify the short circular arcs unambiguously.
    mid_angle = (atan2(half_span, -center_x) + atan2(tangent_y, tangent_x - center_x)) / 2
    mid_x = center_x + radius * cos(mid_angle)
    mid_y = radius * sin(mid_angle)
    return Face(Wire([
        Edge.make_line(flat_low, flat_high),
        Edge.make_line(flat_high, arc_high),
        Edge.make_three_point_arc(arc_high, point(mid_x, mid_y), tangent_high),
        Edge.make_line(tangent_high, roof_high),
        Edge.make_line(roof_high, roof_low),
        Edge.make_line(roof_low, tangent_low),
        Edge.make_three_point_arc(tangent_low, point(mid_x, -mid_y), arc_low),
        Edge.make_line(arc_low, flat_low),
    ]))


class HingeLegPart(Part):
    """One printable housing with named face tags and rigid attachment frames.

    tags returns current world-space face snapshots: rod_bore, nut_floor,
    nut_roof, screw_passage, and side_faces.
    Joints: rod at the origin with its Z axis along +X; screw at the nominal
    screw entry on the bottom face with Z along +Z; nut at the nut seat center.
    Use these frames before nesting in an assembly.
    """

    def __init__(self, parameters: LegParameters = LegParameters()) -> None:
        p = self.parameters = parameters
        body = Solid.extrude(_body_profile(p), (p.width, 0, 0))

        # Chamfer only the exterior: side perimeters and the two top cross-edges.
        # Doing this before cutting keeps the nut seat and both passages sharp.
        if p.edge_chamfer:
            outside_edges = [
                edge for edge in body.edges()
                if isclose(abs(edge.center().X), p.width / 2, abs_tol=1e-7)
                or (
                    isclose(edge.center().Z, p.top_z, abs_tol=1e-7)
                    and isclose(edge.bounding_box().size.X, p.width, abs_tol=1e-7)
                )
            ]
            body = cast(Solid, body.chamfer(p.edge_chamfer, None, outside_edges))

        rod_bore = Solid.make_cylinder(
            p.rod_hole_diameter / 2, p.width,
            Plane(origin=(-p.width / 2, 0, 0), z_dir=(1, 0, 0)),
        )
        nut_slot = Solid.make_box(p.width, p.nut_slot_width, p.nut_slot_height).moved(
            Location((-p.width / 2, p.housing_start + p.wall, p.rod_half))
        )
        screw_passage = Solid.extrude(_screw_profile(p), (0, 0, p.top_z + p.rod_half))
        result = body.cut(rod_bore, nut_slot, screw_passage)
        if not result.is_valid or len(result.solids()) != 1:
            raise ValueError("Dimensions did not produce a single valid leg housing")
        super().__init__(result.solids(), label="Hinge slot leg")

        RigidJoint("rod", self, Location(Plane(origin=(0, 0, 0), z_dir=(1, 0, 0))))
        RigidJoint("screw", self, Location((0, p.screw_y, -p.rod_half)))
        RigidJoint("nut", self, Location((0, p.screw_y, p.rod_half)))
        self._local_tags = self._tag_faces()

    def _tag_faces(self) -> dict[str, ShapeList[Face]]:
        """Select semantic faces by geometry, never by unstable face indices."""
        p = self.parameters
        tags: dict[str, ShapeList[Face]] = {
            name: ShapeList() for name in (
                "rod_bore", "nut_floor", "nut_roof", "screw_passage", "side_faces"
            )
        }
        for face in self.faces():
            box = face.bounding_box()
            center = face.center()
            if face.geom_type == GeomType.CYLINDER and isclose(
                box.size.Y, p.rod_hole_diameter, abs_tol=1e-6
            ) and abs(center.Y) < 1e-6:
                tags["rod_bore"].append(face)
            if face.geom_type == GeomType.PLANE:
                if box.size.X < 1e-6 and isclose(abs(center.X), p.width / 2, abs_tol=1e-6):
                    tags["side_faces"].append(face)
                if box.size.Z < 1e-6 and isclose(center.Y, p.screw_y, abs_tol=1e-6):
                    if isclose(center.Z, p.rod_half, abs_tol=1e-6):
                        tags["nut_floor"].append(face)
                    elif isclose(center.Z, p.rod_half + p.nut_slot_height, abs_tol=1e-6):
                        tags["nut_roof"].append(face)
            if (
                box.size.Z > 1e-6
                and box.min.Y > p.housing_start + p.wall
                and box.max.Y < p.housing_start + p.wall + p.nut_slot_width
                and box.min.X > -p.width / 2 + p.edge_chamfer
                and box.max.X < p.width / 2 - p.edge_chamfer
            ):
                tags["screw_passage"].append(face)
        for name, faces in tags.items():
            for face in faces:
                face.label = name
        return tags

    @property
    def tags(self) -> dict[str, ShapeList[Face]]:
        return {
            name: ShapeList(face.moved(self.global_location) for face in faces)
            for name, faces in self._local_tags.items()
        }


@dataclass(frozen=True)
class CavityParameters:
    """Fit and insertion clearances, separate from the printable leg dimensions."""

    clearance: float = 0.1
    bottom_clearance: float = 0.1
    rod_slot_width: float = 2.1
    rod_slot_run: float = 3.0
    rod_slot_inner_radius: float = 0.2
    rod_slot_outer_radius: float = 1.1
    rod_length: float = 21.0
    housing_wall: float = 2.0
    rod_end_wall: float = 1.0

    def __post_init__(self) -> None:
        if any(not isfinite(getattr(self, f.name)) for f in fields(self)):
            raise ValueError("Cavity dimensions must be finite")
        if min(self.clearance, self.bottom_clearance) < 0 or min(
            self.rod_slot_width, self.rod_slot_run, self.rod_slot_inner_radius,
            self.rod_slot_outer_radius, self.rod_length,
            self.housing_wall, self.rod_end_wall,
        ) <= 0:
            raise ValueError("Cavity sizes must be positive; clearances may be zero")
        if self.rod_slot_outer_radius >= self.rod_slot_width:
            raise ValueError("Rod slot outer radius must fit inside its width")


def _cavity_tool(p: LegParameters, c: CavityParameters) -> Part:
    """Extrude a clearance silhouette and fuse the two-sided rod insertion slot."""
    h, gap = p.rod_half, c.clearance
    width = p.width + 2 * gap
    if c.rod_length <= width:
        raise ValueError("Rod must extend beyond both sides of the leg cavity")

    # Maximum reach of the rounded nose as it swings about the rod.
    nose_reach = sqrt(2) * (h - p.nose_radius) + p.nose_radius
    rear = p.rear_y + gap
    bottom = -h - c.bottom_clearance - gap
    slope = tan(radians(p.rear_relief_angle))
    relief_intercept = p.rear_y + c.bottom_clearance * slope + gap / cos(radians(p.rear_relief_angle))
    outline = [
        (-nose_reach - gap, h + gap), (rear, h + gap),
        (rear, (rear - relief_intercept) / slope),
        (relief_intercept + bottom * slope, bottom),
        (h + gap, bottom), (h + gap, -nose_reach - c.bottom_clearance - gap),
        (-nose_reach - gap, -nose_reach - c.bottom_clearance - gap),
    ]
    face = Face(Wire.make_polygon([(-width / 2, y, z) for y, z in outline]))
    pocket = Solid.extrude(face, (width, 0, 0))

    # The pointed seat and return path let the rod slide in from the top.
    r = c.rod_slot_width / 2
    tip_y = -sqrt(2) * r
    inner_y = tip_y + r + c.rod_slot_run
    outer_y = inner_y + c.rod_slot_width
    slot_points = [
        (tip_y, 0), (tip_y + r, r), (inner_y, r),
        (inner_y, h), (outer_y, h), (outer_y, -r), (tip_y + r, -r),
    ]
    slot = Face(Wire.make_polygon([(-c.rod_length / 2, y, z) for y, z in slot_points]))
    for y, z, radius in (
        (inner_y, r, c.rod_slot_inner_radius),
        (outer_y, -r, c.rod_slot_outer_radius),
    ):
        corners = [v for v in slot.vertices() if abs(v.Y - y) < 1e-7 and abs(v.Z - z) < 1e-7]
        slot = slot.fillet_2d(radius, corners)
    rod_slot = Solid.extrude(slot, (c.rod_length, 0, 0))
    result = pocket.fuse(rod_slot)
    if not result.is_valid or len(result.solids()) != 1:
        raise ValueError("Dimensions did not produce a single cavity tool")
    return Part(result.solids(), label="Leg cavity tool")


def _housing_guide(p: LegParameters, c: CavityParameters, tool: Part) -> Part:
    """A simple symmetric material envelope, with the cavity already removed."""
    nose_reach = sqrt(2) * (p.rod_half - p.nose_radius) + p.nose_radius
    half_width = c.rod_length / 2 + c.rod_end_wall
    front = -nose_reach - c.housing_wall
    rear = p.rear_y + c.housing_wall
    bottom = -p.rod_half - c.housing_wall
    if bottom >= tool.bounding_box().min.Z or front >= tool.bounding_box().min.Y:
        raise ValueError("Housing wall must extend beyond the cavity's bottom and nose")
    envelope = Solid.make_box(2 * half_width, rear - front, p.rod_half - bottom).moved(
        Location((-half_width, front, bottom))
    )
    result = envelope.cut(tool)
    if not result.is_valid or len(result.solids()) != 1:
        raise ValueError("Housing wall must leave a connected guide around the cavity")
    return Part(result.solids(), label="Leg housing guide")


@dataclass(frozen=True)
class LegInstallation:
    """Independent results of one installation; connect the leg after all cuts.

    Use the *latest* rest's joints[joint_label] for final assembly. A subsequent
    installation returns another rest, carrying forward all existing joints.
    tool and housing are fixed snapshots of the installed, zero-angle cavity.
    """

    rest: Part
    leg: Part
    tool: Part
    housing: Part
    joint_label: str

    @property
    def rod_joint(self) -> RigidJoint:
        """Connect the final rest's hinge joint to this installed leg."""
        return cast(RigidJoint, self.leg.joints["rod"])


class Leg(Protocol):
    """Geometry and installation interface for a shoulder-rest implementation."""

    @property
    def part(self) -> Part:
        """Printable leg to preview; installation creates its own independent copy."""
        ...

    @property
    def tool(self) -> Part:
        """Cavity tool snapshot at the template part's current placement."""
        ...

    @property
    def housing(self) -> Part:
        """Required surrounding material guide; never automatically added to a rest."""
        ...

    @property
    def mount_joint(self) -> RigidJoint:
        """Installation reference at the center of the nut-seat edge."""
        ...

    def install(
        self, mount: RigidJoint, *, joint_label: str = "leg",
        angular_range: tuple[float, float] = (-180, 180),
    ) -> LegInstallation:
        """Cut mount.parent and return the new rest, hinge, leg and guide snapshots."""
        ...


class HingeLeg(Leg):
    """Reusable leg template, cutter and housing guide sharing one source frame.

    The mount uses the Onshape connector's origin, with explicit axes: X along
    the rod and Z toward the rest (-Z in the source frame). Connect/install
    before nesting parts in an assembly. Installation never modifies inputs.
    """

    def __init__(
        self, parameters: LegParameters = LegParameters(),
        cavity: CavityParameters = CavityParameters(),
    ) -> None:
        self._part = HingeLegPart(parameters)
        self._tool = _cavity_tool(parameters, cavity)
        self._housing = _housing_guide(parameters, cavity, self._tool)
        RigidJoint("mount", self._part, Location(Plane(
            origin=(0, parameters.screw_y, parameters.rod_half),
            x_dir=(1, 0, 0), z_dir=(0, 0, -1),
        )))

    @property
    def part(self) -> HingeLegPart:
        return self._part

    @property
    def tool(self) -> Part:
        return self._tool.moved(self._part.global_location)

    @property
    def housing(self) -> Part:
        return self._housing.moved(self._part.global_location)

    @property
    def mount_joint(self) -> RigidJoint:
        return cast(RigidJoint, self._part.joints["mount"])

    def install(
        self, mount: RigidJoint, *, joint_label: str = "leg",
        angular_range: tuple[float, float] = (-180, 180),
    ) -> LegInstallation:
        source = mount.parent
        if not isinstance(source, (Part, Solid)) or source.parent is not None or source.children:
            raise ValueError("Install on an un-nested Part or Solid before assembly")
        if source.joints.get(mount.label) is not mount:
            raise ValueError("Mount must belong to the current rest")
        if not joint_label or joint_label in source.joints:
            raise ValueError("Choose a new, nonempty hinge joint label")
        if any(j.connected_to is not None for j in source.joints.values()):
            raise ValueError("Install legs before connecting the rest's assembly joints")
        if not all(isfinite(a) for a in angular_range) or not angular_range[0] <= 0 <= angular_range[1]:
            raise ValueError("Angular range must be finite and include the neutral angle (0)")

        placement = mount.location * self.mount_joint.relative_location.inverse()
        tool = self._tool.moved(placement)
        cut = source.cut(tool)
        if not cut.is_valid or len(cut.solids()) != 1:
            raise ValueError("Installation must leave one valid connected rest solid")
        if source.volume - cut.volume < 1e-7:
            raise ValueError("Cavity tool does not intersect the rest")

        # Rebuild in the same local frame. Boolean results may bake the placement
        # into geometry, so their automatically copied joint frames are unsafe.
        local_cut = cut.moved(source.location.inverse())
        rest = Part(local_cut.solids(), label=source.label, color=source.color).locate(source.location)
        rest.material = getattr(source, "material", None)
        rest.joints = deepcopy(source.joints, {id(source): rest})
        for joint in rest.joints.values():
            joint.parent = rest

        leg = deepcopy(self._part).locate(placement)
        rod_axis = Axis(placement.position, placement.x_axis.direction)
        hinge = RevoluteJoint(joint_label, rest, rod_axis, angular_range=angular_range)
        # Clock the installed rod frame to this hinge's reference. This makes
        # angle=0 reproduce the cutting pose even for an arbitrarily rotated rest.
        RigidJoint("rod", leg, rest.location * hinge.relative_axis.location)
        return LegInstallation(rest, leg, tool, self._housing.moved(placement), joint_label)


def build_hinge_leg(
    parameters: LegParameters = LegParameters(),
    cavity: CavityParameters = CavityParameters(),
) -> HingeLeg:
    """Build a reusable leg, cavity tool and material guide."""
    return HingeLeg(parameters, cavity)


if __name__ == "__main__":
    from ocp_vscode import show

    leg = build_hinge_leg()
    show(leg.part, leg.tool, leg.housing, leg.mount_joint.symbol)

