"""A rounded bar blank for experimenting with rest shape and leg placement."""

from dataclasses import dataclass
from math import atan2, degrees, isfinite

from build123d import (
    BuildPart, BuildSketch, Location, Locations, Mode, Part, Plane,
    RigidJoint, SlotCenterToCenter, Vector, extrude,
)

from shoulder_rest.parts.leg import Leg
from shoulder_rest.parts.rest import Rest
from shoulder_rest.parts.rest_geometry import RestGeometry
from shoulder_rest.parts.violin_outline import ViolinOutline


@dataclass(frozen=True)
class SimpleRestParameters:
    """Millimeters, plus arc-length fractions selecting the two leg centers."""

    width: float = 44
    thickness: float = 12
    left_fraction: float = 0.25
    right_fraction: float = 0.60
    violin_gap: float = 12

    def __post_init__(self) -> None:
        if not all(isfinite(v) and v > 0 for v in (self.width, self.thickness)):
            raise ValueError("Width and thickness must be finite and positive")
        if not all(isfinite(v) and 0 <= v <= 1 for v in (self.left_fraction, self.right_fraction)):
            raise ValueError("Attachment fractions must be between zero and one")
        if not isfinite(self.violin_gap) or self.violin_gap < 0:
            raise ValueError("Violin gap must be finite and nonnegative")


def _bar(left: Vector, right: Vector, p: SimpleRestParameters) -> Part:
    """Return a local solid below XY, with semicircular ends at the leg centers."""
    span = right - left
    if span.length < 1e-7:
        raise ValueError("Leg centers must be distinct")
    with BuildPart(mode=Mode.PRIVATE) as body:
        with BuildSketch():
            with Locations((left + right) / 2):
                SlotCenterToCenter(
                    span.length, p.width, rotation=degrees(atan2(span.Y, span.X)),
                )
        extrude(amount=-p.thickness)
    assert body.part_local is not None
    body.part_local.label = "Rest body"
    return body.part_local


class SimpleRestGeometry(RestGeometry):
    """Inspectable rounded bar and its attachments, independent of any leg."""

    def __init__(
        self, violin: ViolinOutline,
        parameters: SimpleRestParameters = SimpleRestParameters(),
    ) -> None:
        p = self.parameters = parameters
        left = violin.attachment_point("left", p.left_fraction)
        right = violin.attachment_point("right", p.right_fraction)
        self._part = _bar(left, right, p)
        direction = (right - left).normalized()
        across = Vector(-direction.Y, direction.X, 0)
        # Opposite rod directions put both noses inward; Z points into the bar.
        self._left_mount_joint = RigidJoint(
            "left_mount", self._part,
            Location(Plane(origin=left, x_dir=across, z_dir=(0, 0, -1))),
        )
        self._right_mount_joint = RigidJoint(
            "right_mount", self._part,
            Location(Plane(origin=right, x_dir=-across, z_dir=(0, 0, -1))),
        )
        self._violin_joint = violin.add_mount_joint(self._part, offset=Location((0, 0, p.violin_gap)))

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


def build_simple_rest(
    violin: ViolinOutline, leg: Leg,
    parameters: SimpleRestParameters = SimpleRestParameters(), *,
    right_leg: Leg | None = None,
) -> Rest:
    """Build a complete rest in local outline coordinates, ready for positioning.

    The mounting face is Z=0 and material extends toward -Z. The violin joint
    offsets the whole rest below the violin by ``violin_gap`` when positioned.
    The body is a flat blank without a shoulder contact contour.
    """
    return Rest(
        SimpleRestGeometry(violin, parameters), leg,
        right_leg=right_leg,
    )
