"""Finished rest body and attachment interface, independent of assembly."""

from typing import Protocol

from build123d import Part, RigidJoint, Solid


class RestGeometry(Protocol):
    """A finished, un-nested single solid and three distinct joints on that solid.

    The body's location records its intended placement relative to the shoulder
    and violin. Implementations may position reference parts and subtract the
    shoulder before defining these joints on the final body. Joint labels are
    implementation details; consumers use the typed properties.

    Dimensions are in millimeters and angles in degrees. Installation mount Z
    points into the body; X sets orientation (the rod axis for hinge legs).
    The violin joint carries
    the shared attachment frame, including spacing and tilt.
    """

    @property
    def part(self) -> Part | Solid:
        """Finished body before leg cuts, at its intended placement."""
        ...

    @property
    def left_mount_joint(self) -> RigidJoint:
        """Left leg installation frame on part."""
        ...

    @property
    def right_mount_joint(self) -> RigidJoint:
        """Right leg installation frame on part."""
        ...

    @property
    def violin_joint(self) -> RigidJoint:
        """Violin attachment on part, following the body's placement."""
        ...
