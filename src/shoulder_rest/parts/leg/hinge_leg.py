"""Hinge-slot leg, its cavity and installation, in the Onshape source frame.

Source frame: the rod axis is X through the origin, the nut housing extends
toward +Y, and the screw runs along Z. Side profiles are sketched in XY with
horizontal = body Y and vertical = body Z, then placed on the YZ plane.
Lengths are in millimeters and angles in degrees. Run to preview the leg.

Source: Onshape "Hinge Slot Leg"
(https://cad.onshape.com/documents/4b6fd83d4ef915bc8da1e93f/w/38814d255f0d64578653c02a/e/db1dc0bcdac152a853d83f7c),
exported to ``assets/leg/`` as modeling references. With
``rod_bore_clearance=0.2`` the leg and default cavity match the Onshape solids
by volume and two-way Boolean difference; the housing guide fills the source
dummy housing's one-sided underside notch to stay symmetric.
"""

from copy import deepcopy
from dataclasses import dataclass, fields
from math import isfinite, radians, sqrt, tan

from build123d import (
    Align, Axis, Box, BuildPart, BuildSketch, Color, Compound, Cylinder, Face,
    Kind, Location, Locations, Mode, Part, Plane, Polygon, Pos, Rectangle,
    RevoluteJoint, RigidJoint, Rotation, chamfer, extrude, fillet, insert, offset,
)

from shoulder_rest.parts._validation import single_solid

from .kun import KunParameters, screw_hole_face
from .rod_retention import RodRetentionParameters, _retention_bumps


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
    """Printable leg dimensions and the hardware it receives."""

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
        if min(sizes) <= 0 or min(gaps) < 0:
            raise ValueError("Sizes must be positive; clearances, gaps and chamfer may be zero")
        if not 0 < self.rear_relief_angle < 90:
            raise ValueError("Relief angle must be between 0 and 90 degrees")
        if self.nose_radius >= self.rod_house_half or self.rod_hole_diameter >= self.rod_house_length:
            raise ValueError("Nose radius and rod bore must fit inside the rod housing")
        if self.rod.length <= self.width:
            raise ValueError("Metal rod must extend beyond both sides of the printed leg")
        if self.edge_chamfer >= min(self.width / 2, self.wall, self.nose_radius):
            raise ValueError("Chamfer is too large for the housing")
        if max(abs(self.kun.roof_x), self.kun.screw_flat_half_height) >= self.width / 2 - self.edge_chamfer:
            raise ValueError("Screw opening must fit between the side faces")

    @property
    def rod_house_half(self) -> float:
        """Half the square rod housing; its top face is the mounting face."""
        return self.rod_house_length / 2

    @property
    def nose_swing_radius(self) -> float:
        """Maximum distance from the hinge axis to the rounded nose."""
        return sqrt(2) * (self.rod_house_half - self.nose_radius) + self.nose_radius

    @property
    def rod_hole_diameter(self) -> float:
        return self.rod.diameter + self.rod_bore_clearance

    @property
    def housing_start_y(self) -> float:
        """Front of the raised nut housing."""
        return self.rod_house_half + self.housing_gap

    @property
    def screw_y(self) -> float:
        return self.housing_start_y + self.wall + self.kun.nut_slot_width / 2

    @property
    def rear_y(self) -> float:
        return self.housing_start_y + 2 * self.wall + self.kun.nut_slot_width

    @property
    def top_z(self) -> float:
        return self.rod_house_half + self.kun.nut_slot_height + self.wall


@dataclass(frozen=True)
class CavityParameters:
    """Fit and insertion clearances, separate from the printable leg dimensions.

    ``nose_clearance`` deepens the nose recess toward -Y and -Z, leaving the
    rear step, leg and mount unchanged. It makes room for a hand-cut piece of
    thin foam and consumes the housing's front and bottom walls rather than
    growing it, so check the material left in the final rest.
    """

    clearance: float = 0.1
    bottom_clearance: float = 0.1
    nose_clearance: float = 0.0  # Extra room toward -Y and -Z in the nose recess.
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
        clearances = (
            self.clearance, self.bottom_clearance, self.nose_clearance,
            self.rod_slot_clearance, self.rod_slot_radius_clearance, self.rod_length_clearance,
        )
        sizes = (self.rod_slot_run, self.rod_slot_inner_radius, self.housing_wall, self.rod_end_wall)
        if min(clearances) < 0 or min(sizes) <= 0:
            raise ValueError("Cavity sizes must be positive; clearances may be zero")

    def slot_width(self, rod: RodParameters) -> float:
        return rod.diameter + self.rod_slot_clearance

    def slot_outer_radius(self, rod: RodParameters) -> float:
        return rod.diameter / 2 + self.rod_slot_radius_clearance

    def tool_length(self, rod: RodParameters) -> float:
        return rod.length + self.rod_length_clearance


def _lower_profile(p: LegParameters) -> Face:
    """Rod housing with a rounded nose and rear relief; shared by leg and cavity."""
    h = p.rod_house_half
    relief_width = h * tan(radians(p.rear_relief_angle))
    with BuildSketch(mode=Mode.PRIVATE) as profile:
        with Locations((-h, 0)):
            Rectangle(p.rear_y + h, p.rod_house_length, align=(Align.MIN, Align.CENTER))
        # Remove the triangular wedge beneath the rear wall.
        Polygon(
            (p.rear_y, 0), (p.rear_y, -h), (p.rear_y - relief_width, -h),
            align=None, mode=Mode.SUBTRACT,
        )
        nose_corners = profile.vertices().group_by(Axis.X)[0]
        fillet(nose_corners, p.nose_radius)
    return profile.face()


def _leg_profile(p: LegParameters) -> Face:
    """Lower profile plus the raised nut housing behind the rod housing."""
    with BuildSketch(mode=Mode.PRIVATE) as profile:
        insert(_lower_profile(p))
        with Locations((p.housing_start_y, p.rod_house_half)):
            Rectangle(
                p.rear_y - p.housing_start_y, p.top_z - p.rod_house_half,
                align=(Align.MIN, Align.MIN),
            )
    return profile.face()


def _printed_leg(p: LegParameters) -> Part:
    with BuildPart(mode=Mode.PRIVATE) as leg:
        with BuildSketch(Plane.YZ):
            insert(_leg_profile(p))
        extrude(amount=p.width / 2, both=True)

        # Finish the exterior before cutting, keeping seats and passages sharp.
        if p.edge_chamfer:
            side_perimeters = leg.faces().filter_by(Axis.X).edges()
            top_cross_edges = leg.edges().filter_by(Axis.X).group_by(Axis.Z)[-1]
            chamfer(side_perimeters + top_cross_edges, length=p.edge_chamfer)

        Cylinder(p.rod_hole_diameter / 2, p.width, rotation=(0, 90, 0), mode=Mode.SUBTRACT)
        # The nut slot runs across the full width, seated on the rod housing.
        with Locations((0, p.screw_y, p.rod_house_half)):
            Box(
                p.width, p.kun.nut_slot_width, p.kun.nut_slot_height,
                align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT,
            )
        # The screw passes up from the underside through the nut housing.
        with BuildSketch(Plane.XY.offset(-p.rod_house_half)):
            with Locations((0, p.screw_y)):
                insert(screw_hole_face(p.kun))
        extrude(amount=p.top_z + p.rod_house_half, mode=Mode.SUBTRACT)

    return single_solid(leg.part, "Dimensions did not produce a single valid leg")


class HingeLegPart(Part):
    """The printable leg, with rigid frames for its hardware.

    ``rod_joint`` is at the origin with Z along the rod (+X); ``screw_joint`` is
    the nominal screw entry on the bottom face and ``nut_joint`` the nut seat
    center, both with Z along +Z. Use the assembly's copies of these joints
    to position the leg and rod together.
    """

    def __init__(self, parameters: LegParameters = LegParameters()) -> None:
        p = parameters
        super().__init__(_printed_leg(p).wrapped, label="Hinge slot leg")
        self.rod_joint = RigidJoint("rod", self, Location(Plane(origin=(0, 0, 0), z_dir=(1, 0, 0))))
        self.screw_joint = RigidJoint("screw", self, Location((0, p.screw_y, -p.rod_house_half)))
        self.nut_joint = RigidJoint("nut", self, Location((0, p.screw_y, p.rod_house_half)))


def _cavity_profile(p: LegParameters, c: CavityParameters) -> Face:
    """Lower profile with nose swing allowance, underside relief and fit offset."""
    h, reach = p.rod_house_half, p.nose_swing_radius + c.nose_clearance
    with BuildSketch(mode=Mode.PRIVATE) as profile:
        insert(_lower_profile(p))
        # Room for the nose to swing, up to the rear step at Y=h.
        with Locations((-reach, -reach)):
            Rectangle(h + reach, h + reach, align=(Align.MIN, Align.MIN))
        if c.bottom_clearance:
            insert(profile.face().moved(Pos(0, -c.bottom_clearance)))
        if c.clearance:
            offset(amount=c.clearance, kind=Kind.INTERSECTION)
    return profile.face()


def _rod_slot_profile(p: LegParameters, c: CavityParameters) -> Face:
    """Diamond seat, horizontal channel and upright entry for inserting the rod."""
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
            Rectangle(width, p.rod_house_half + half_width, align=(Align.MIN, Align.MIN))

        # Ease the inside and outside corners where the entry turns into the channel.
        inner_corner = slot.vertices().sort_by_distance((entry_x, half_width))[0]
        fillet(inner_corner, c.rod_slot_inner_radius)
        outer_corner = slot.vertices().sort_by_distance((entry_x + width, -half_width))[0]
        fillet(outer_corner, c.slot_outer_radius(p.rod))
    return slot.face()


def _cavity_tool(p: LegParameters, c: CavityParameters, bumps: Part | None) -> Part:
    """Clearance silhouette across the leg, plus the rod slot across the rod's length."""
    if c.slot_outer_radius(p.rod) >= c.slot_width(p.rod):
        raise ValueError("Rod slot outer radius must fit inside its width")
    width = p.width + 2 * c.clearance
    rod_tool_length = c.tool_length(p.rod)
    if rod_tool_length <= width:
        raise ValueError("Rod must extend beyond both sides of the leg cavity")

    with BuildPart(mode=Mode.PRIVATE) as tool:
        with BuildSketch(Plane.YZ):
            insert(_cavity_profile(p, c))
        extrude(amount=width / 2, both=True)
        with BuildSketch(Plane.YZ):
            insert(_rod_slot_profile(p, c))
        extrude(amount=rod_tool_length / 2, both=True)
        if bumps is not None:
            insert(bumps, mode=Mode.SUBTRACT)

    cavity = single_solid(tool.part, "Dimensions did not produce a single cavity tool")
    cavity.label = "Leg cavity tool"
    return cavity


def _housing_guide(p: LegParameters, c: CavityParameters, tool: Part) -> Part:
    """A symmetric block of surrounding material with the cavity removed."""
    half_width = c.tool_length(p.rod) / 2 + c.rod_end_wall
    front = -p.nose_swing_radius - c.housing_wall
    rear = p.rear_y + c.housing_wall
    bottom = -p.rod_house_half - c.housing_wall
    top = p.rod_house_half
    if bottom >= tool.bounding_box().min.Z or front >= tool.bounding_box().min.Y:
        raise ValueError("Housing wall must extend beyond the cavity's bottom and nose")
    with BuildPart(mode=Mode.PRIVATE) as guide:
        with Locations((0, front, bottom)):
            Box(2 * half_width, rear - front, top - bottom, align=(Align.CENTER, Align.MIN, Align.MIN))
        insert(tool, mode=Mode.SUBTRACT)
    housing = single_solid(guide.part, "Housing wall must leave a connected guide around the cavity")
    housing.label = "Leg housing guide"
    return housing


class HingeLeg:
    """A leg that swings on a metal rod and screws to a Kun foot.

    All geometry is in the source frame. ``mount_location`` is the mount frame
    in that frame: centered on the nut-seat edge of the mounting face, with X
    along the rod and Z toward the rest (source -Z), so the nose faces mount +Y.

    ``assembly`` carries rigid ``rod_joint``, ``screw_joint``, ``nut_joint`` and
    ``mount_joint`` frames, and the ``hinge`` revolute joint about the rod. The
    hinge axis points along source -X, so positive angles turn about mount +X.
    ``angular_range`` sets the hinge's limits in degrees, which also bound
    ``HingeLegInstallation.leg``; they describe kinematics, not collisions.
    """

    def __init__(
        self, parameters: LegParameters = LegParameters(),
        cavity: CavityParameters = CavityParameters(), *,
        angular_range: tuple[float, float] = (-180, 180),
        rod_retention: RodRetentionParameters | None = None,
    ) -> None:
        low, high = angular_range
        if not (isfinite(low) and isfinite(high) and low <= 0 <= high):
            raise ValueError("Angular range must be finite and include the neutral angle (0)")
        self.parameters = parameters
        self.cavity = cavity
        self._retention_bumps = (
            None if rod_retention is None
            else _retention_bumps(parameters, cavity, rod_retention)
        )

        self.part = HingeLegPart(parameters)
        self.rod = Cylinder(parameters.rod.diameter / 2, parameters.rod.length, rotation=(0, 90, 0))
        self.rod.label = "Metal hinge rod"
        self.rod.color = Color("silver")
        self.tool = _cavity_tool(parameters, cavity, self._retention_bumps)
        self.housing = _housing_guide(parameters, cavity, self.tool)
        self.mount_location = Location(Plane(
            origin=(0, parameters.screw_y, parameters.rod_house_half),
            x_dir=(1, 0, 0), z_dir=(0, 0, -1),
        ))

        self.assembly = Compound(label="Hinge leg assembly", children=[self.part, self.rod])
        self.rod_joint, self.screw_joint, self.nut_joint = (
            RigidJoint(joint.label, self.assembly, joint.relative_location)
            for joint in (self.part.rod_joint, self.part.screw_joint, self.part.nut_joint)
        )
        self.mount_joint = RigidJoint("mount", self.assembly, self.mount_location)
        self.hinge = RevoluteJoint(
            "hinge", self.assembly, Axis((0, 0, 0), (-1, 0, 0)), angular_range=angular_range,
        )

    def install(self, body: Part, *, at: Location) -> tuple[Part, "HingeLegInstallation"]:
        """Return a copy of body with the cavity cut at mount frame ``at``, and the site."""
        site = HingeLegInstallation(self, at)
        if self._retention_bumps is not None:
            uncovered = self._retention_bumps.moved(site.placement) - body
            if uncovered.volume > 1e-6:
                raise ValueError("Rest must contain the retention bumps; retain the housing guide envelope")
        installed = single_solid(
            body - self.tool.moved(site.placement),
            "Installation must leave one valid connected rest solid",
        )
        if body.volume - installed.volume < 1e-7:
            raise ValueError("Cavity tool does not intersect the rest")
        installed.label, installed.color = body.label, body.color
        return installed, site


@dataclass(frozen=True)
class HingeLegInstallation:
    """A hinge leg site; each call creates a fresh, independent component."""

    template: HingeLeg
    location: Location
    """Mount frame in the body's local frame."""

    @property
    def placement(self) -> Location:
        """The leg's source frame in the body's local frame."""
        return self.location * self.template.mount_location.inverse()

    @property
    def housing(self) -> Part:
        """Housing guide at this site, independent of leg angle."""
        return self.template.housing.moved(self.placement)

    def leg(self, angle: float = 0) -> Compound:
        """Rod-and-leg assembly at this site, swung ``angle`` degrees about mount +X.

        The copy keeps the template's joints, so it can be positioned or built on further.
        """
        low, high = self.template.hinge.angular_range
        if not (isfinite(angle) and low <= angle <= high):
            raise ValueError("Hinge angle must be finite and within the angular range")
        leg = deepcopy(self.template.assembly)
        leg.locate(self.placement * Rotation(angle, 0, 0))
        return leg


if __name__ == "__main__":
    from ocp_vscode import show

    hinge = HingeLeg()
    show(hinge.assembly, hinge.tool, hinge.housing, hinge.mount_joint.symbol)
