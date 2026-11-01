"""The violin outline in its local XY frame, and the mount frame it shares."""

from math import isfinite
from typing import Literal

from build123d import (
    BuildLine, BuildSketch, Edge, Face, Line, Location, Mode, Plane, RigidJoint,
    Side, Vector, Wire, extrude, insert, make_face, mirror,
)

from shoulder_rest.parts.shoulder import Shoulder


class ViolinOutline:
    """Violin outline curves, leg-attachment curves and a display block.

    Built from the right-hand (+X) half of the outline, mirrored across YZ.
    Every curve is an open wire in local XY running from its lower-Y end to its
    upper-Y end. The attachment curves are offset ``attachment_offset`` mm
    inward and hold candidate leg centers (see ``attachment_point``).

    ``mount_location`` is the frame shared with the shoulder and the rest: the
    midpoint of the line closing the outline's upper-Y end, on Z=0, with the
    local axes. ``block`` is the outline extruded ``block_thickness`` mm toward
    +Z; it carries ``mount_joint`` and is what moves when the violin is placed.
    The curves and ``mount_location`` stay in the local frame.
    """

    def __init__(
        self, right: Edge | Wire, *,
        attachment_offset: float = 6.0, block_thickness: float = 38.0,
    ) -> None:
        right = Wire([right]) if isinstance(right, Edge) else right
        if right.is_closed or (right @ 0).Y >= (right @ 1).Y:
            raise ValueError("Outline curve must be open and run toward +Y")
        if right.bounding_box().min.X <= 0:
            raise ValueError("Outline curve must lie at positive X")
        if not isfinite(attachment_offset) or attachment_offset < 0:
            raise ValueError("attachment_offset must be finite and nonnegative")

        footprint = _footprint(right)
        self.right = right
        self.left = right.mirror(Plane.YZ)
        self.right_attachment = _inward_offset(right, attachment_offset, footprint)
        self.left_attachment = self.right_attachment.mirror(Plane.YZ)
        self.mount_location = Location((0, (right @ 1).Y, 0))
        self.block = extrude(footprint, amount=block_thickness)
        self.block.label = "Violin block"
        self.mount_joint = RigidJoint("mount", self.block, self.mount_location)

    def attachment_point(self, side: Literal["left", "right"], fraction: float) -> Vector:
        """Point at a fraction (0 to 1) of an attachment curve's arc length."""
        if not isfinite(fraction) or not 0 <= fraction <= 1:
            raise ValueError("fraction must be finite and between 0 and 1")
        if side == "left":
            return self.left_attachment @ fraction
        if side == "right":
            return self.right_attachment @ fraction
        raise ValueError("side must be 'left' or 'right'")

    def position_on(self, shoulder: Shoulder) -> None:
        """Move the block onto the shoulder's violin placement.

        Placement happens once, before either is nested in a scene; call again
        after moving the shoulder.
        """
        if self.block.parent is not None or shoulder.assembly.parent is not None:
            raise ValueError("Position the violin and shoulder before nesting them in a scene")
        shoulder.violin_joint.connect_to(self.mount_joint)


def _footprint(right: Wire) -> Face:
    """Both outline halves closed by horizontal lines across their ends."""
    bottom, top = right @ 0, right @ 1
    with BuildSketch(mode=Mode.PRIVATE) as footprint:
        with BuildLine():
            insert(right)
            Line(top, (0, top.Y))
            Line(bottom, (0, bottom.Y))
            mirror(about=Plane.YZ)
        make_face()
    if not footprint.face().is_valid:
        raise ValueError("Outline curve does not enclose a valid footprint")
    return footprint.face()


def _inward_offset(curve: Wire, distance: float, footprint: Face) -> Wire:
    """Offset the right-hand curve toward the centerline, staying inside the footprint."""
    if distance == 0:
        return curve
    error = ValueError(
        "attachment_offset cannot form an inward curve within this outline; "
        "reduce the offset or revise the curve"
    )
    try:
        # Inward is left of the curve's +Y travel.
        offset = Wire(curve.offset_2d(distance, side=Side.LEFT, closed=False))
    except (RuntimeError, ValueError, IndexError) as cause:
        raise error from cause
    if (offset @ 0).Y > (offset @ 1).Y:  # OCCT can reverse the traversal.
        offset = Wire([edge.reversed() for edge in reversed(offset.order_edges())])
    inside = offset.intersect(footprint)
    inside_length = sum(edge.length for shape in (inside or []) for edge in shape.edges())
    if (
        not offset.is_valid or offset.is_closed
        or offset.bounding_box().min.X <= 0
        or abs(inside_length - offset.length) > 1e-5
    ):
        raise error
    return offset
