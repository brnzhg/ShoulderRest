"""Shared construction and placement for two-legged shoulder rests."""

from build123d import Compound, Location, Part, RigidJoint

from shoulder_rest.parts.leg import Leg, LegInstallation
from shoulder_rest.parts.rest_geometry import RestGeometry
from shoulder_rest.parts.violin_outline import ViolinOutline


_LEFT_INSTALLATION_LABEL = "left_leg"
_RIGHT_INSTALLATION_LABEL = "right_leg"


class Rest[InstallationT: LegInstallation]:
    """Prepare two leg sites on a finished RestGeometry.

    Reads the geometry's typed local frames and passes its body to installation.
    Owns an assembly initially containing only the cut body. The caller chooses
    components through the concrete installations' attachment methods.
    The supplied leg template serves both sides unless right_leg is provided.
    """

    def __init__(
        self, geometry: RestGeometry, leg: Leg[InstallationT], *,
        right_leg: Leg[InstallationT] | None = None,
    ) -> None:
        body = geometry.part
        if body.parent is not None or body.children:
            raise ValueError("Supply an un-nested rest body")
        if not body.is_valid or len(body.solids()) != 1:
            raise ValueError("Rest body must be one valid solid")
        mounts = (geometry.left_mount_joint, geometry.right_mount_joint, geometry.violin_joint)
        for joint in mounts:
            if joint.parent is not body:
                raise ValueError("Geometry joints must belong to geometry.part")
        left_frame, right_frame, violin_frame = (
            Location(joint.relative_location) for joint in mounts
        )

        left = leg.install(
            body, at=left_frame, joint_label=_LEFT_INSTALLATION_LABEL,
        )
        right_template = leg if right_leg is None else right_leg
        right = right_template.install(
            body, at=right_frame, joint_label=_RIGHT_INSTALLATION_LABEL,
        )
        self._part = body
        self._installations: tuple[InstallationT, InstallationT] = (left, right)
        # Create the rest's public frames once, on the finished body.
        self._left_mount_joint = RigidJoint(
            geometry.left_mount_joint.label, self._part, self._part.location * left_frame,
        )
        self._right_mount_joint = RigidJoint(
            geometry.right_mount_joint.label, self._part, self._part.location * right_frame,
        )
        self._assembly = Compound(
            label="Shoulder rest", children=[self._part],
        )
        # The external joint belongs to the assembly so alignment moves all parts.
        self._violin_joint = RigidJoint(
            "violin", self._assembly, self._part.location * violin_frame,
        )

    @property
    def part(self) -> Part:
        """Printable body child, with both leg cavities already cut."""
        return self._part

    @property
    def assembly(self) -> Compound:
        """Cut body and any explicitly attached components."""
        return self._assembly

    @property
    def violin_joint(self) -> RigidJoint:
        """External attachment on the whole assembly."""
        return self._violin_joint

    @property
    def left_mount_joint(self) -> RigidJoint:
        """Left installation frame on the printable body, in assembly coordinates."""
        return self._left_mount_joint

    @property
    def right_mount_joint(self) -> RigidJoint:
        """Right installation frame on the printable body, in assembly coordinates."""
        return self._right_mount_joint

    @property
    def left(self) -> InstallationT:
        """Left installation with its implementation-specific controls."""
        return self._installations[0]

    @property
    def right(self) -> InstallationT:
        """Right installation with its implementation-specific controls."""
        return self._installations[1]

    @property
    def installations(self) -> tuple[InstallationT, InstallationT]:
        """Left and right installations, retaining the leg's installation type."""
        return self._installations

    def position_on(self, violin: ViolinOutline) -> None:
        """Align the complete rest to the violin's current pose before scene nesting.

        May be called again after moving the violin. Joint connections perform
        placement once; they do not continuously constrain the two assemblies.
        """
        if self._assembly.parent is not None or violin.block.parent is not None:
            raise ValueError("Position the rest and violin before nesting them in a scene")
        violin.mount_joint.connect_to(self.violin_joint)
