"""Rounded bars between two leg centers, flat or with one half fitted to the shoulder.

Run to preview the contoured bar on the bundled shoulder.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Literal

from build123d import (
    BuildPart, BuildSketch, Keep, Locations, Mode, Part, Plane, Pos, Sketch,
    SlotCenterToCenter, Vector, extrude, insert, split,
)

from shoulder_rest.parts._validation import single_solid
from shoulder_rest.parts.shoulder import Shoulder
from shoulder_rest.parts.violin_outline import ViolinOutline
from .rest import RestGeometry, leg_mount


@dataclass(frozen=True)
class BarRestParameters:
    """Bar size in mm; fractions pick leg centers along the attachment curves."""

    width: float = 30
    thickness: float = 12
    left_fraction: float = 0.4
    right_fraction: float = 0.4
    violin_gap: float = 12

    def __post_init__(self) -> None:
        if not all(isfinite(v) and v > 0 for v in (self.width, self.thickness)):
            raise ValueError("Width and thickness must be finite and positive")
        if not isfinite(self.violin_gap) or self.violin_gap < 0:
            raise ValueError("Violin gap must be finite and nonnegative")


@dataclass(frozen=True)
class ContouredBarRestParameters(BarRestParameters):
    """Adds the oversized depth below Z=0 of the half cut to fit the shoulder."""

    contact_depth: float = 80
    contact_side: Literal["left", "right"] = "right"

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isfinite(self.contact_depth) or self.contact_depth <= self.thickness:
            raise ValueError("Contact depth must be finite and greater than bar thickness")
        if self.contact_side not in ("left", "right"):
            raise ValueError("Contact side must be 'left' or 'right'")


def bar_rest_geometry(
    violin: ViolinOutline, p: BarRestParameters = BarRestParameters(),
) -> RestGeometry:
    """A flat bar with semicircular ends centered on the legs."""
    left, right = _leg_centers(violin, p)
    bar = extrude(_footprint(left, right, p.width), amount=-p.thickness)
    bar.label = "Rest body"
    return _geometry(bar, violin, left, right, p)


def contoured_bar_rest_geometry(
    violin: ViolinOutline, shoulder: Shoulder,
    p: ContouredBarRestParameters = ContouredBarRestParameters(),
) -> RestGeometry:
    """A bar whose contact half is deepened, then cut to fit the shoulder."""
    left, right = _leg_centers(violin, p)
    footprint = _footprint(left, right, p.width)
    with BuildPart(mode=Mode.PRIVATE) as blank:
        extrude(footprint, amount=-p.thickness)
        with BuildSketch():
            insert(footprint)
            # Keep the contact half, split across the bar at its midpoint.
            split(
                bisect_by=Plane(origin=(left + right) / 2, z_dir=right - left),
                keep=Keep.TOP if p.contact_side == "right" else Keep.BOTTOM,
            )
        extrude(amount=-p.contact_depth)
    oversized = single_solid(blank.part, "Bar blank must be one valid solid")

    violin_mount = violin.mount_location * Pos(0, 0, p.violin_gap)
    body = single_solid(
        oversized - shoulder.cutter(violin_mount),
        "Shoulder cut must leave one solid; adjust the fit or contact depth",
    )
    if oversized.volume - body.volume < 1e-6:
        raise ValueError("Shoulder tool misses the blank; adjust the fit or contact depth")
    body.label = "Contoured rest body"
    return _geometry(body, violin, left, right, p)


def _leg_centers(violin: ViolinOutline, p: BarRestParameters) -> tuple[Vector, Vector]:
    left = violin.attachment_point("left", p.left_fraction)
    right = violin.attachment_point("right", p.right_fraction)
    if (right - left).length < 1e-7:
        raise ValueError("Leg centers must be distinct")
    return left, right


def _footprint(left: Vector, right: Vector, width: float) -> Sketch:
    with BuildSketch(mode=Mode.PRIVATE) as footprint:
        with Locations(Plane(origin=(left + right) / 2, x_dir=right - left)):
            SlotCenterToCenter((right - left).length, width)
    return footprint.sketch


def _geometry(
    body: Part, violin: ViolinOutline, left: Vector, right: Vector, p: BarRestParameters,
) -> RestGeometry:
    """Both legs face each other along the bar; the bar hangs violin_gap below the violin."""
    return RestGeometry(
        body,
        left_mount=leg_mount(left, facing=right - left),
        right_mount=leg_mount(right, facing=left - right),
        violin_mount=violin.mount_location * Pos(0, 0, p.violin_gap),
    )


if __name__ == "__main__":
    from build123d import Compound
    from ocp_vscode import show

    from shoulder_rest.parts.leg.hinge_leg import HingeLeg
    from shoulder_rest.parts.rest import Rest
    from shoulder_rest.parts.shoulder.step_shoulder import load_shoulder_cast
    from shoulder_rest.parts.violin_outline.spline_violin_outline import build_violin_outline

    shoulder = load_shoulder_cast()
    violin = build_violin_outline()
    violin.position_on(shoulder)
    rest = Rest(contoured_bar_rest_geometry(violin, shoulder), HingeLeg())
    rest.add(rest.left.leg(angle=20))
    rest.add(rest.right.leg())
    rest.add(rest.left.housing)
    rest.add(rest.right.housing)
    rest.position_on(violin)
    show(Compound(label="Bar rest fitting", children=[shoulder.assembly, violin.block, rest.assembly]))
