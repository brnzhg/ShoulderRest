"""Shared construction and placement for two-legged shoulder rests."""

from build123d import Compound, Location, Part, RigidJoint, Solid

from shoulder_rest.parts.leg import Leg, LegInstallation
from shoulder_rest.parts.rest_geometry import RestGeometry
from shoulder_rest.parts.violin_outline import ViolinOutline


_LEFT_INSTALLATION_LABEL = "left_leg"
_RIGHT_INSTALLATION_LABEL = "right_leg"


class Rest:
    """Install and assemble two legs on a finished RestGeometry.

    Reads the geometry's typed local frames and passes its body to installation.
    Installs two independent legs, delegates their final attachment, and owns the
    completed assembly. Move the whole assembly, never its individual children.
    The supplied leg template serves both sides unless right_leg is provided.
    """

    def __init__(
        self, geometry: RestGeometry, leg: Leg, *,
        right_leg: Leg | None = None,
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
            left.rest, at=right_frame, joint_label=_RIGHT_INSTALLATION_LABEL,
        )
        self._part = right.rest
        self._installations = (left, right)
        # Create the rest's public frames once, on the finished body.
        self._left_mount_joint = RigidJoint(
            geometry.left_mount_joint.label, self._part, self._part.location * left_frame,
        )
        self._right_mount_joint = RigidJoint(
            geometry.right_mount_joint.label, self._part, self._part.location * right_frame,
        )
        left.attach_to(self._part)
        right.attach_to(self._part)
        self._assembly = Compound(
            label="Shoulder rest", children=[self._part, left.leg, right.leg],
        )
        # The external joint belongs to the assembly so alignment moves all parts.
        self._violin_joint = RigidJoint(
            "violin", self._assembly, self._part.location * violin_frame,
        )

    @property
    def part(self) -> Part | Solid:
        """Printable body child, with both leg cavities already cut."""
        return self._part

    @property
    def assembly(self) -> Compound:
        """Completed body and legs; repeated access returns the same assembly."""
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
    def installations(self) -> tuple[LegInstallation, LegInstallation]:
        """Left and right installation results; tools remain construction snapshots."""
        return self._installations

    def position_on(self, violin: ViolinOutline) -> None:
        """Align the complete rest to the violin's current pose before scene nesting.

        May be called again after moving the violin. Joint connections perform
        placement once; they do not continuously constrain the two assemblies.
        """
        if self._assembly.parent is not None or violin.block.parent is not None:
            raise ValueError("Position the rest and violin before nesting them in a scene")
        violin.shoulder_joint.connect_to(self.violin_joint)


if __name__ == "__main__":
    from build123d import Location
    from ocp_vscode import show

    from shoulder_rest.parts.leg.hinge_leg import build_hinge_leg
    from shoulder_rest.parts.shoulder.step_shoulder import load_shoulder_cast
    from shoulder_rest.parts.simple_rest import SimpleRestGeometry
    from shoulder_rest.parts.violin_outline.spline_violin_outline import build_violin_outline

    violin = build_violin_outline()
    shoulder = load_shoulder_cast(
        cast_location=Location((0, 0, 0), (30, 30, -5)),
        violin_location=(
            # Base location, violin level correction, orient Z direction
            Location((-55, -87.5, 57.5), (4, 0, 90 - 30)) * 
            # Offset from base, violin roll angle
            Location((0, 5, 20), (0, -26, 0))
        )
    )
    shoulder.violin_joint.connect_to(violin.shoulder_joint)
    geometry = SimpleRestGeometry(violin)
    violin.shoulder_joint.connect_to(geometry.violin_joint)
    # A contouring implementation can finish its body in this pose before assembly.
    rest = Rest(geometry, build_hinge_leg())
    assembly = Compound(label="Rest fitting example", children=[
        shoulder.assembly, violin.block, rest.assembly,
    ])
    show(assembly)
