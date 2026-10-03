"""A rounded bar with one oversized half cut to fit a shoulder."""

from dataclasses import dataclass
from math import atan2, degrees, isfinite
from typing import Literal

from build123d import (
    BuildPart, BuildSketch, Keep, Location, Locations, Mode, Part, Plane,
    RigidJoint, SlotCenterToCenter, Vector, extrude, insert,
)

from shoulder_rest.parts.rest_geometry import RestGeometry
from shoulder_rest.parts.shoulder import Shoulder
from shoulder_rest.parts.simple_rest import SimpleRestParameters
from shoulder_rest.parts.violin_outline import ViolinOutline


@dataclass(frozen=True)
class ContouredRestParameters(SimpleRestParameters):
    """Bar dimensions in mm; contact_depth is total depth below the mounting face."""

    contact_depth: float = 80
    contact_side: Literal["left", "right"] = "right"

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isfinite(self.contact_depth) or self.contact_depth <= self.thickness:
            raise ValueError("Contact depth must be finite and greater than bar thickness")
        if self.contact_side not in ("left", "right"):
            raise ValueError("Contact side must be 'left' or 'right'")


def _oversized_blank(left: Vector, right: Vector, p: ContouredRestParameters) -> Part:
    """Extrude the whole footprint to bar thickness, and one half to contact depth."""
    span = right - left
    if span.length < 1e-7:
        raise ValueError("Leg centers must be distinct")
    midpoint = (left + right) / 2
    direction = span.normalized()
    across = Vector(-direction.Y, direction.X, 0)
    with BuildSketch(mode=Mode.PRIVATE) as footprint:
        with Locations(midpoint):
            SlotCenterToCenter(
                span.length, p.width, rotation=degrees(atan2(span.Y, span.X)),
            )
    # The split follows the bar, including when its leg centers have different Y.
    contact_half = footprint.sketch.split(
        Plane(origin=midpoint, x_dir=across, z_dir=direction),
        keep=Keep.BOTTOM if p.contact_side == "left" else Keep.TOP,
    )
    with BuildPart(mode=Mode.PRIVATE) as blank:
        extrude(footprint.sketch, amount=-p.thickness)
        extrude(contact_half, amount=-p.contact_depth)
    assert blank.part_local is not None
    return blank.part_local


class ContouredRestGeometry(RestGeometry):
    """Fit a half-depth extension to a shoulder before installing any legs.

    Construction positions the supplied violin on the shoulder. Call before
    nesting either reference in a scene. The bar is modeled in violin-local XY,
    with mounting face Z=0 and material toward -Z. The finished body is returned
    at its fitted world pose; Rest can consume it without another placement call.
    """

    def __init__(
        self, violin: ViolinOutline, shoulder: Shoulder,
        parameters: ContouredRestParameters = ContouredRestParameters(),
    ) -> None:
        p = self.parameters = parameters
        violin.position_on(shoulder)
        left = violin.attachment_point("left", p.left_fraction)
        right = violin.attachment_point("right", p.right_fraction)
        blank = _oversized_blank(left, right, p)

        blank_joint = violin.add_mount_joint(
            blank, offset=Location((0, 0, p.violin_gap)),
        )
        violin.mount_joint.connect_to(blank_joint)
        pose = Location(blank.location)

        # Build locally; the builder places the finished body at the fitted pose.
        with BuildPart(pose, mode=Mode.PRIVATE) as contoured:
            insert(blank.located(Location()))
            insert(shoulder.extended.moved(pose.inverse()), mode=Mode.SUBTRACT)
        body = contoured.part
        assert body is not None
        if not body.is_valid or len(body.solids()) != 1:
            raise ValueError("Shoulder cut must leave one solid; adjust the fit or contact depth")
        if blank.volume - body.volume < 1e-6:
            raise ValueError("Shoulder tool misses the blank; adjust the fit or contact depth")
        self._part = body
        self._part.label = "Contoured rest body"

        # Create the final attachments on the cut body.
        direction = (right - left).normalized()
        across = Vector(-direction.Y, direction.X, 0)
        self._left_mount_joint = RigidJoint(
            "left_mount", self._part,
            pose * Location(Plane(origin=left, x_dir=across, z_dir=(0, 0, -1))),
        )
        self._right_mount_joint = RigidJoint(
            "right_mount", self._part,
            pose * Location(Plane(origin=right, x_dir=-across, z_dir=(0, 0, -1))),
        )
        self._violin_joint = violin.add_mount_joint(
            self._part, offset=Location((0, 0, p.violin_gap)),
        )

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
    geometry = ContouredRestGeometry(violin, shoulder)
    rest = Rest(geometry, build_hinge_leg())
    scene = Compound(label="Contoured rest fitting", children=[
        shoulder.assembly, violin.block, rest.assembly,
    ])
    rest.left.attach_to(rest.assembly, angle=20)
    rest.right.attach_to(rest.assembly)
    rest.left.attach_housing_to(rest.assembly)
    rest.right.attach_housing_to(rest.assembly)
    show(scene)
