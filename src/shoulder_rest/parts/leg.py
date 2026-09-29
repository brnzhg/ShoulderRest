"""Hinge-slot leg, cavity cutter and installation in the Onshape source frame.

The rod axis is X through the origin. The nut housing extends toward +Y;
the screw runs along Z. Lengths are in millimeters and angles in degrees.
"""

from copy import deepcopy
from dataclasses import dataclass, fields
from math import isclose, isfinite, radians, sqrt, tan
from typing import Protocol, cast

from build123d import (
    Align, Axis, Box, BuildPart, BuildSketch, Color, Compound, Cylinder,
    Face, GeomType, Kind, Location, Locations, Mode, Part, Plane, Polygon,
    Rectangle, RevoluteJoint, RigidJoint, ShapeList, Solid,
    chamfer, extrude, fillet, insert, offset,
)

from shoulder_rest.parts.kun import KunParameters, nut_slot_face, screw_hole_face


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
    rod_bore_clearance: float = 0.2  # Added to diameter, not radius.
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
    """One printable housing with named face tags and rigid attachment frames.

    tags returns current world-space face snapshots: rod_bore, nut_floor,
    nut_roof, screw_passage, and side_faces.
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
                    elif isclose(center.Z, p.rod_half + p.kun.nut_slot_height, abs_tol=1e-6):
                        tags["nut_roof"].append(face)
            if (
                box.size.Z > 1e-6
                and box.min.Y > p.housing_start + p.wall
                and box.max.Y < p.housing_start + p.wall + p.kun.nut_slot_width
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
class LegInstallation:
    """Independent results of one installation; connect the leg after all cuts.

    Use the *latest* rest's joints[joint_label] for final assembly. A subsequent
    installation returns another rest, carrying forward all existing joints.
    leg is the full assembly (printed body and metal rod).
    tool and housing are fixed snapshots of the installed, zero-angle cavity.
    """

    rest: Part | Solid
    leg: Compound
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
        """Printable child for export; position the whole assembly for modeling."""
        ...

    @property
    def assembly(self) -> Compound:
        """Printable leg and metal rod; position and connect this assembly."""
        ...

    @property
    def tool(self) -> Part:
        """Cavity tool snapshot at the template assembly's current placement."""
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
    before nesting this leg assembly in the final assembly. Installation never
    modifies inputs. Move assembly, not its individual hardware children.
    """

    def __init__(
        self, parameters: LegParameters = LegParameters(),
        cavity: CavityParameters = CavityParameters(),
    ) -> None:
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
        for name, joint in self._part.joints.items():
            RigidJoint(name, self._assembly, joint.location)
        RigidJoint("mount", self._assembly, Location(Plane(
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
        return cast(RigidJoint, self._assembly.joints["mount"])

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
        # Cut in the rest's local frame so copied joints keep their coordinates.
        rest_placement = source.location
        local_rest = source.located(Location())
        local_tool = tool.moved(rest_placement.inverse())
        rest = (local_rest - local_tool).moved(rest_placement)
        if not rest.is_valid or len(rest.solids()) != 1:
            raise ValueError("Installation must leave one valid connected rest solid")
        if source.volume - rest.volume < 1e-7:
            raise ValueError("Cavity tool does not intersect the rest")

        leg = deepcopy(self._assembly).locate(placement)
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
    show(leg.assembly, leg.tool, leg.housing, leg.mount_joint.symbol)
