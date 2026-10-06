"""Optional solid rod-retention bumps for HingeLeg, in its source frame.

Dimensions are millimeters. Tooling returns local geometry for explicit insertion.
These are prototype fits requiring print trials.
"""

from dataclasses import dataclass, fields
from math import isfinite, sqrt
from typing import TYPE_CHECKING

from build123d import BuildPart, Cylinder, Locations, Mode, Part

if TYPE_CHECKING:
    from .hinge_leg import CavityParameters, LegParameters


@dataclass(frozen=True)
class RodRetentionParameters:
    """Short, solid rounded ribs below each rod channel; no spring reliefs."""

    interference: float = 0.10  # Rod diameter minus minimum throat opening.
    bump_radius: float = 0.45
    bump_y: float = 0.75
    bump_width: float = 0.8  # Short contact along X to limit insertion force.

    def __post_init__(self) -> None:
        if any(not isfinite(getattr(self, f.name)) or getattr(self, f.name) <= 0 for f in fields(self)):
            raise ValueError("Rod-retention dimensions must be finite and positive")


def _rod_retention(
    p: "LegParameters", c: "CavityParameters", r: RodRetentionParameters,
) -> tuple[Part, Part]:
    half_slot = c.slot_width(p.rod) / 2
    bump_z = -half_slot + c.rod_slot_clearance + r.interference - r.bump_radius
    cavity_half = p.width / 2 + c.clearance
    overhang = p.rod.length / 2 - cavity_half
    entry_y = (1 - sqrt(2)) * half_slot + c.rod_slot_run
    if r.interference >= p.rod.diameter:
        raise ValueError("Rod throat must remain open")
    if c.rod_slot_clearance + r.interference >= r.bump_radius:
        raise ValueError("Bump center must stay embedded below the channel floor")
    if r.bump_width >= overhang:
        raise ValueError("Rod overhang must leave room for both retention bumps")
    if r.bump_y - r.bump_radius <= 0 or r.bump_y + r.bump_radius >= entry_y:
        raise ValueError("Bumps must fit between the diamond seat and the entry bend")
    if sqrt(r.bump_y**2 + bump_z**2) <= p.rod.diameter / 2 + r.bump_radius:
        raise ValueError("Retention bumps must clear the seated rod")
    if bump_z - r.bump_radius <= -p.rod_house_half - c.housing_wall:
        raise ValueError("Retention bumps must fit above the housing bottom")
    bumps = []
    for side in (-1, 1):
        with BuildPart(mode=Mode.PRIVATE) as bump:
            with Locations((side * (cavity_half + overhang / 2), r.bump_y, bump_z)):
                Cylinder(r.bump_radius, r.bump_width, rotation=(0, 90, 0))
        assert bump.part_local is not None
        bumps.append(bump.part_local)
    return bumps[0], bumps[1]

