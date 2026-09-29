"""Reusable cutting profiles for the Kun screw leg; dimensions are in millimeters."""

from dataclasses import dataclass, fields
from math import acos, cos, degrees, isfinite, radians, sin, sqrt, tan

from build123d import BuildLine, BuildSketch, CenterArc, Face, Mode, Plane, Polyline, Rectangle, make_face, mirror


@dataclass(frozen=True)
class KunParameters:
    """Fitted opening dimensions, including the print-oriented screw profile."""

    nut_slot_width: float = 8.65
    nut_slot_height: float = 3.4
    screw_diameter: float = 4.0
    screw_circle_offset: float = 0.1
    screw_flat_x: float = 1.9
    screw_roof_extension: float = 0.2
    screw_tangent_angle: float = 40.0

    def __post_init__(self) -> None:
        if any(not isfinite(getattr(self, f.name)) for f in fields(self)):
            raise ValueError("Kun dimensions must be finite")
        if min(self.nut_slot_width, self.nut_slot_height, self.screw_diameter, self.screw_flat_x) <= 0:
            raise ValueError("Kun opening dimensions must be positive")
        radius = self.screw_diameter / 2
        if not 0 <= self.screw_circle_offset < radius or self.screw_roof_extension < 0:
            raise ValueError("Invalid screw circle offset or roof extension")
        if not 0 < self.screw_tangent_angle < 90:
            raise ValueError("Screw tangent angle must be between 0 and 90 degrees")
        if self.screw_diameter >= self.nut_slot_width:
            raise ValueError("Screw opening must fit within the nut slot width")
        angle = radians(self.screw_tangent_angle)
        tangent_x = self.screw_circle_offset - radius * cos(angle)
        roof_x = self.screw_circle_offset - radius - self.screw_roof_extension
        roof_y = radius * sin(angle) - (tangent_x - roof_x) / tan(angle)
        if tangent_x >= 0 or roof_y <= 0:
            raise ValueError("Screw tangent angle/roof extension cannot form the clipped roof")


def screw_hole_face(p: KunParameters = KunParameters()) -> Face:
    """XY opening at nominal screw axis (0, 0); extrude along Z.

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
    arc_start = degrees(acos(-center_x / radius))  # Circle's intersection with X=0.
    arc_end = 180 - p.screw_tangent_angle
    with BuildSketch(mode=Mode.PRIVATE) as profile:
        with BuildLine():
            # Upper boundary: flat back, circular shoulder, tangent roof, clipped tip.
            shoulder = CenterArc((center_x, 0), radius, arc_start, arc_end - arc_start)
            Polyline((p.screw_flat_x, 0), (p.screw_flat_x, half_span), shoulder @ 0)
            Polyline(shoulder @ 1, (roof_x, roof_y), (roof_x, 0))
            mirror(about=Plane.XZ)
        make_face()
    return profile.face()


def nut_slot_face(p: KunParameters = KunParameters()) -> Face:
    """Centered YZ rectangle: width along Y, height along Z; extrude along X."""
    with BuildSketch(Plane.YZ, mode=Mode.PRIVATE) as profile:
        Rectangle(p.nut_slot_width, p.nut_slot_height)
    return Plane.YZ.from_local_coords(profile.face())
