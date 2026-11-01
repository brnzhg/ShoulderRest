"""Openings for the Kun screw-leg hardware; dimensions are in millimeters."""

from dataclasses import dataclass, fields
from math import cos, isfinite, radians, sin, sqrt, tan

from build123d import (
    Align, BuildLine, BuildSketch, Circle, Face, Keep, Locations, Mode, Plane,
    PolarLine, Polyline, Rectangle, make_face, mirror, split,
)


@dataclass(frozen=True)
class KunParameters:
    """Fitted opening dimensions, including the print-oriented screw profile."""

    nut_slot_width: float = 8.65
    nut_slot_height: float = 3.4
    screw_diameter: float = 4.0
    screw_circle_offset: float = 0.1
    screw_flat_half_height: float = 1.9  # Squared-off side's extent along +X.
    screw_roof_extension: float = 0.2  # Clipped roof's extent beyond the circle along -X.
    screw_tangent_angle: float = 40.0  # Upper tangent contact radius's angle from -X.

    def __post_init__(self) -> None:
        if any(not isfinite(getattr(self, f.name)) for f in fields(self)):
            raise ValueError("Kun dimensions must be finite")
        if min(self.nut_slot_width, self.nut_slot_height, self.screw_diameter, self.screw_flat_half_height) <= 0:
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
        roof_x = self.roof_x
        roof_y = radius * sin(angle) - (tangent_x - roof_x) / tan(angle)
        if tangent_x >= 0 or roof_y <= 0:
            raise ValueError("Screw tangent angle/roof extension cannot form the clipped roof")

    @property
    def roof_x(self) -> float:
        """X of the screw opening's clipped roof tip."""
        return self.screw_circle_offset - self.screw_diameter / 2 - self.screw_roof_extension


def screw_hole_face(p: KunParameters = KunParameters()) -> Face:
    """Printable screw opening in XY, centered on the nominal screw axis; extrude along Z.

    The circle is offset along +X, its +X side is squared off, and a clipped
    tangent roof extends it toward -X, symmetric about the X axis.
    """
    radius = p.screw_diameter / 2
    center_x = p.screw_circle_offset
    half_chord = sqrt(radius**2 - center_x**2)  # Circle's half-width at X=0.
    with BuildSketch(mode=Mode.PRIVATE) as profile:
        with Locations((center_x, 0)):
            Circle(radius)
        circle = profile.edge()

        # Replace the +X half with a rectangle meeting the circle at its chord.
        split(bisect_by=Plane.YZ, keep=Keep.BOTTOM)
        Rectangle(p.screw_flat_half_height, 2 * half_chord, align=(Align.MIN, Align.CENTER))

        # Follow the circle's upper tangent to the roof's clipped tip, then mirror.
        roof_clip = Plane.YZ.offset(p.roof_x)
        contact = (180 - p.screw_tangent_angle) / 360  # Fraction of the full circle.
        with BuildLine():
            tangent = PolarLine(circle @ contact, length=roof_clip, direction=circle % contact)
            Polyline(tangent @ 1, roof_clip.origin, (0, 0), tangent @ 0)
        upper_roof = make_face()
        mirror(upper_roof, about=Plane.XZ)
    return profile.face()
