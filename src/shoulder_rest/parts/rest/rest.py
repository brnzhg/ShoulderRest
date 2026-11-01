"""Rest body interface, and a rest assembled from a body and two legs.

A rest body is modeled in the violin outline's local XY: its flat
leg-mounting face is Z=0 and material extends toward -Z.

The body is printed in PETG with that mounting face on the bed, so preserve
the plane when shaping a body. Export ``Rest.part`` in its local frame and turn
it over; the fitted scene is not a print pose.
"""

from dataclasses import dataclass

from build123d import Compound, Location, Part, Plane, RigidJoint, Shape, Vector, VectorLike

from shoulder_rest.parts._validation import single_solid
from shoulder_rest.parts.leg import Leg, LegInstallation
from shoulder_rest.parts.violin_outline import ViolinOutline


@dataclass(frozen=True)
class RestGeometry:
    """A finished rest body before leg cavities, with its attachment frames.

    Every frame is a ``Location`` in the body's local frame. ``left_mount`` and
    ``right_mount`` are leg mount frames (see ``leg_mount``). ``violin_mount``
    is placed on the violin's ``mount_location`` when the rest is positioned;
    ``violin.mount_location * Pos(0, 0, gap)`` hangs the rest ``gap`` mm below
    the violin, and other offsets can tilt it.
    """

    part: Part
    left_mount: Location
    right_mount: Location
    violin_mount: Location

    def __post_init__(self) -> None:
        single_solid(self.part, "Rest body must be one valid solid")
        if self.part.parent is not None or self.part.location != Location():
            raise ValueError("Supply an un-nested rest body in its local frame")


def leg_mount(center: VectorLike, facing: VectorLike) -> Location:
    """Leg mount frame on the Z=0 mounting face, pointing Z into the body.

    Mount +Y follows ``facing`` (in XY); a hinge leg's nose points that way
    and its rod runs along mount X.
    """
    facing = Vector(facing)
    return Location(Plane(origin=center, x_dir=(-facing.Y, facing.X, 0), z_dir=(0, 0, -1)))


class Rest[InstallationT: LegInstallation]:
    """A rest body with both leg cavities cut, assembled for display and fitting.

    ``part`` is the printable body. ``assembly`` contains it and anything added
    with ``add``; its frame is the body's local frame, so the components that
    ``left`` and ``right`` produce can be added directly. ``right_leg``
    defaults to ``leg``.

    ``left_mount_joint`` and ``right_mount_joint`` mark the leg mount frames on
    ``part``; ``violin_joint`` is on the whole assembly, so positioning moves
    every component together.
    """

    def __init__(
        self, geometry: RestGeometry, leg: Leg[InstallationT], *,
        right_leg: Leg[InstallationT] | None = None,
    ) -> None:
        right_leg = leg if right_leg is None else right_leg
        body, self.left = leg.install(geometry.part, at=geometry.left_mount)
        body, self.right = right_leg.install(body, at=geometry.right_mount)
        self.part = body
        self.left_mount_joint = RigidJoint("left_mount", body, geometry.left_mount)
        self.right_mount_joint = RigidJoint("right_mount", body, geometry.right_mount)
        self.assembly = Compound(label="Shoulder rest", children=[body])
        self.violin_joint = RigidJoint("violin", self.assembly, geometry.violin_mount)

    def add[ShapeT: Shape](self, component: ShapeT) -> ShapeT:
        """Add a component modeled in the rest's local frame and return it.

        Works whether or not the rest is already positioned or nested; the
        component then follows the rest. For example, ``rest.add(rest.left.leg())``.
        """
        poses = [(node, node.location) for node in reversed(self.assembly.path)]
        component.parent = self.assembly
        # build123d rebuilds a compound at the origin when its children change,
        # so restore each level's pose and refresh the levels above it.
        for node, pose in poses:
            node.children = node.children
            node.locate(pose)
        return component

    def position_on(self, violin: ViolinOutline) -> None:
        """Move the whole rest onto the violin's current pose.

        Placement happens once, before either is nested in a scene; call again
        after moving the violin.
        """
        if self.assembly.parent is not None or violin.block.parent is not None:
            raise ValueError("Position the rest and violin before nesting them in a scene")
        violin.mount_joint.connect_to(self.violin_joint)
