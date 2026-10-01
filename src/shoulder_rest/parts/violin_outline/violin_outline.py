"""Violin construction curves and shared attachment interface."""

from typing import Literal, Protocol

from build123d import Compound, Location, RigidJoint, Solid, Vector, Wire


class ViolinOutline(Protocol):
    """Local XY construction geometry, independent of how the outline is made.

    All four open curves run from the lower-Y end to the upper-Y end. Curves
    and attachment points stay in this modeling frame even if the block moves.
    The block's placement maps that frame into an assembly.
    """

    @property
    def left(self) -> Wire:
        """Original outline on the negative-X side."""
        ...

    @property
    def right(self) -> Wire:
        """Original outline on the positive-X side."""
        ...

    @property
    def left_attachment(self) -> Wire:
        """Inward offset of the left outline for leg centers."""
        ...

    @property
    def right_attachment(self) -> Wire:
        """Inward offset of the right outline for leg centers."""
        ...

    @property
    def block(self) -> Solid:
        """Positionable visualization solid with a 'shoulder' rigid joint."""
        ...

    @property
    def shoulder_joint(self) -> RigidJoint:
        """Shared attachment joint on the positionable violin block."""
        ...

    @property
    def mount_location(self) -> Location:
        """Shared local frame at the upper-Y closing line's midpoint, on Z=0."""
        ...

    def add_mount_joint(
        self,
        part: Solid | Compound,
        *,
        label: str = "violin",
        offset: Location | None = None,
    ) -> RigidJoint:
        """Add a shared-frame joint to a part modeled in the outline's local frame.

        Offset is applied in the mount frame. A positive Z joint offset places
        the connected rest toward -Z, away from the violin. Connect before nesting.
        """
        ...

    def attachment_point(self, side: Literal["left", "right"], fraction: float) -> Vector:
        """Point at a fraction of attachment-curve arc length, from 0 to 1."""
        ...
