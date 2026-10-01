"""Shared construction and placement for two-legged shoulder rests."""

from copy import deepcopy
from typing import cast

from build123d import Compound, Part, RigidJoint, Solid

from shoulder_rest.parts.leg import Leg, LegInstallation
from shoulder_rest.parts.rest_geometry import RestGeometry
from shoulder_rest.parts.violin_outline import ViolinOutline


_LEFT_INSTALLATION_LABEL = "left_leg"
_RIGHT_INSTALLATION_LABEL = "right_leg"


def _copy_body(body: Part | Solid) -> Part | Solid:
    """Copy the body and joint frames without copying connected reference parts."""
    part = deepcopy(body, {id(body.joints): {}})
    for label, joint in body.joints.items():
        memo: dict[int, object] = {id(body): part}
        if joint.connected_to is not None:
            memo[id(joint.connected_to)] = None
        part.joints[label] = deepcopy(joint, memo)
    return part


class Rest:
    """Install and assemble two legs on a finished RestGeometry.

    Copies the supplied body and its joint frames, preserving their placement.
    Existing reference connections remain on the input geometry only. Installs
    two independent legs, delegates their final attachment, and owns the
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
            if (
                not isinstance(joint, RigidJoint)
                or joint.parent is not body
                or body.joints.get(joint.label) is not joint
            ):
                raise ValueError("Geometry joints must be rigid joints registered on geometry.part")
        if len({joint.label for joint in mounts}) != 3:
            raise ValueError("Geometry must provide three distinct attachment joints")
        left_mount_label = mounts[0].label
        right_mount_label = mounts[1].label
        violin_label = mounts[2].label

        part = _copy_body(body)
        left = leg.install(
            cast(RigidJoint, part.joints[left_mount_label]), joint_label=_LEFT_INSTALLATION_LABEL,
        )
        right_template = leg if right_leg is None else right_leg
        right = right_template.install(
            cast(RigidJoint, left.rest.joints[right_mount_label]), joint_label=_RIGHT_INSTALLATION_LABEL,
        )
        self._part = right.rest
        self._installations = (left, right)
        # Cuts replace the body and its joints; retain references only after both cuts.
        self._left_mount_joint = cast(RigidJoint, self._part.joints[left_mount_label])
        self._right_mount_joint = cast(RigidJoint, self._part.joints[right_mount_label])
        left.attach_to(self._part)
        right.attach_to(self._part)
        self._assembly = Compound(
            label="Shoulder rest", children=[self._part, left.leg, right.leg],
        )
        # The external joint belongs to the assembly so alignment moves all parts.
        self._violin_joint = RigidJoint(
            "violin", self._assembly, self._part.joints[violin_label].location,
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
