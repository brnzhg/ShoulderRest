"""Planar violin attachment curves and a simplified visualization block."""

from copy import deepcopy
from math import isfinite
from typing import Literal, Sequence

from build123d import (
    BuildLine, BuildPart, BuildSketch, Compound, Face, Line, Location, Mode, Plane,
    RigidJoint, Side, Solid, Spline, Vector, Wire, extrude, insert, make_face,
)
from .violin_outline import ViolinOutline


class SplineViolinOutline(ViolinOutline):
    """Interpolate a right-hand tracing and mirror it across the YZ plane.

    Dimensions are in mm. Points must have positive X and strictly increasing Y.
    ``attachment_offset`` is a normal inward distance, not an X translation.
    The original curves and horizontal end caps enclose the block footprint;
    the block extends from Z=0 to ``block_thickness``. Its shared mount is at
    the upper-Y closing line's midpoint on Z=0, with the local XYZ axes.
    Curves are returned as copies.
    """

    def __init__(
        self,
        points: Sequence[tuple[float, float]],
        attachment_offset: float = 3.0,
        block_thickness: float = 38.0,
    ) -> None:
        if not isfinite(attachment_offset) or attachment_offset < 0:
            raise ValueError("attachment_offset must be finite and nonnegative")
        points = tuple(points)
        if len(points) < 2 or any(
            not isfinite(x) or not isfinite(y) or x <= 0 for x, y in points
        ):
            raise ValueError("Provide at least two finite XY points with positive X")
        if any(a[1] >= b[1] for a, b in zip(points, points[1:])):
            raise ValueError("Outline points must have strictly increasing Y")

        with BuildLine(mode=Mode.PRIVATE) as right:
            Spline(*points)
        self._right = Wire(right.edges())
        self._left = self._right.mirror(Plane.YZ)
        self._mount_location = Location((self._right @ 1 + self._left @ 1) / 2)
        with BuildSketch(mode=Mode.PRIVATE) as outline:
            with BuildLine():
                insert(self._right)
                Line(self._right @ 1, self._left @ 1)
                insert(self._left)
                Line(self._left @ 0, self._right @ 0)
            make_face()
        footprint = outline.face()
        if not footprint.is_valid or footprint.area <= 0:
            raise ValueError("Outline points do not form a valid block footprint")

        self._right_attachment = self._inward_curve(attachment_offset, footprint)
        self._left_attachment = self._right_attachment.mirror(Plane.YZ)
        with BuildPart(mode=Mode.PRIVATE) as block:
            extrude(footprint, amount=block_thickness, dir=(0, 0, 1))
        self._block = block.solid()
        self._block.label = "Violin block"
        self._mount_joint = self.add_mount_joint(self._block, label="mount")

    def _inward_curve(self, distance: float, footprint: Face) -> Wire:
        if distance == 0:
            return deepcopy(self._right)
        try:
            curve = Wire(self._right.offset_2d(distance, side=Side.LEFT, closed=False))
            # OCCT can return the offset in the opposite traversal direction.
            if (curve @ 0).Y > (curve @ 1).Y:
                curve = Wire([edge.reversed() for edge in reversed(curve.order_edges())])
            contained = curve.intersect(footprint)
            contained_length = sum(
                edge.length for shape in (contained or []) for edge in shape.edges()
            )
            if (
                not curve.is_valid
                or curve.is_closed
                or curve.bounding_box().min.X <= 0
                or abs(contained_length - curve.length) > 1e-5
            ):
                raise ValueError("Offset leaves the footprint or crosses the centerline")
        except (RuntimeError, ValueError, IndexError) as error:
            raise ValueError(
                "attachment_offset cannot form an inward curve within this outline; "
                "reduce the offset or revise the points"
            ) from error
        return curve

    @property
    def left(self) -> Wire:
        return deepcopy(self._left)

    @property
    def right(self) -> Wire:
        return deepcopy(self._right)

    @property
    def left_attachment(self) -> Wire:
        return deepcopy(self._left_attachment)

    @property
    def right_attachment(self) -> Wire:
        return deepcopy(self._right_attachment)

    @property
    def block(self) -> Solid:
        return self._block

    @property
    def mount_joint(self) -> RigidJoint:
        return self._mount_joint

    @property
    def mount_location(self) -> Location:
        return Location(self._mount_location)

    def add_mount_joint(
        self,
        part: Solid | Compound,
        *,
        label: str = "violin",
        offset: Location | None = None,
    ) -> RigidJoint:
        if label in part.joints:
            raise ValueError(f"Part already has a joint named {label!r}")
        local_joint = self.mount_location * (Location() if offset is None else offset)
        return RigidJoint(
            label, to_part=part, joint_location=part.location * local_joint
        )

    def attachment_point(self, side: Literal["left", "right"], fraction: float) -> Vector:
        if side not in ("left", "right"):
            raise ValueError("side must be 'left' or 'right'")
        if not isfinite(fraction) or not 0 <= fraction <= 1:
            raise ValueError("fraction must be finite and between 0 and 1")
        curve = self._left_attachment if side == "left" else self._right_attachment
        return curve.position_at(fraction)


def build_violin_outline(attachment_offset: float = 6) -> SplineViolinOutline:
    RIGHT_OUTLINE_POINTS = (
        (87.175, -56.570),
        (91.220, -49.3),
        (96.473, -37.724),
        (101.728, -15.76),
        (102.605, 0.0),
        (101.12, 15.165),
        (94.784, 32.802),
        (84.79, 46.767),
        (65.910, 61.558),
        (43.630, 69.918),
        (18.865, 73.536),
    )

    return SplineViolinOutline(points=RIGHT_OUTLINE_POINTS, attachment_offset=attachment_offset)

if __name__ == "__main__":
    from build123d import Polyline
    from ocp_vscode import show

    violin = build_violin_outline()
    # These endpoints stay on the attachment curves when the model is rebuilt.
    guide = Polyline(
        violin.attachment_point("left", 0.25),
        (0, 10),
        violin.attachment_point("right", 0.60),
    )
    show(
        violin.block,
        violin.left,
        violin.right,
        violin.left_attachment,
        violin.right_attachment,
        guide,
        violin.mount_joint.symbol,
        names=[
            "Violin block", "Left outline", "Right outline",
            "Left attachment", "Right attachment", "Example rest guide", "Mount frame",
        ],
    )
