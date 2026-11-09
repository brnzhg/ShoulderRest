"""Optional solid bumps that retain HingeLeg's rod, in the hinge source frame.

Dimensions are in millimeters. The rest prints with its mounting face on the
bed, which puts source +Z toward the bed: each channel's +Z wall becomes its
printed floor, so the bumps grow upward with support.

This is a local deformation fit. Insertion force, wear and retention need a
PETG print trial; tune ``interference`` in steps of about 0.05 mm, using
``examples/rod_retention_coupon.py --export`` for a test coupon.
"""

from dataclasses import dataclass, fields
from math import isfinite, sqrt
from typing import TYPE_CHECKING

from build123d import BuildPart, Cylinder, Locations, Mode, Part

if TYPE_CHECKING:
    from .hinge_leg import CavityParameters, LegParameters


@dataclass(frozen=True)
class RodRetentionParameters:
    """Solid ribs on each rod channel's +Z wall, which is the floor when printed."""

    interference: float = 0.10  # Rod diameter minus minimum throat opening.
    bump_radius: float = 0.45
    bump_y: float = 0.75
    bump_width: float = 0.8  # Short contact along X to limit insertion force.

    def __post_init__(self) -> None:
        if any(not isfinite(getattr(self, f.name)) or getattr(self, f.name) <= 0 for f in fields(self)):
            raise ValueError("Rod-retention dimensions must be finite and positive")


def _retention_bumps(
    p: "LegParameters", c: "CavityParameters", r: RodRetentionParameters,
) -> Part:
    """Two bumps, one centered on each rod overhang outside the leg cavity."""
    half_slot = c.slot_width(p.rod) / 2
    bump_z = half_slot - c.rod_slot_clearance - r.interference + r.bump_radius
    cavity_half_width = p.width / 2 + c.clearance
    overhang = p.rod.length / 2 - cavity_half_width
    bump_x = cavity_half_width + overhang / 2
    entry_y = (1 - sqrt(2)) * half_slot + c.rod_slot_run
    if r.interference >= p.rod.diameter:
        raise ValueError("Rod throat must remain open")
    if c.rod_slot_clearance + r.interference >= r.bump_radius:
        raise ValueError("Bump center must stay embedded in the channel's +Z wall")
    if r.bump_width >= overhang:
        raise ValueError("Rod overhang must leave room for both retention bumps")
    if r.bump_y - r.bump_radius <= 0 or r.bump_y + r.bump_radius >= entry_y:
        raise ValueError("Bumps must fit between the diamond seat and the entry bend")
    if sqrt(r.bump_y**2 + bump_z**2) <= p.rod.diameter / 2 + r.bump_radius:
        raise ValueError("Retention bumps must clear the seated rod")
    if bump_z + r.bump_radius >= p.knuckle_half:
        raise ValueError("Retention bumps must fit below the mounting face")
    with BuildPart(mode=Mode.PRIVATE) as bumps:
        with Locations((-bump_x, r.bump_y, bump_z), (bump_x, r.bump_y, bump_z)):
            Cylinder(r.bump_radius, r.bump_width, rotation=(0, 90, 0))
    assert bumps.part is not None
    return bumps.part
