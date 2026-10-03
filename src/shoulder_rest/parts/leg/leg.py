"""Leg interface and installation results for rest implementations."""

from typing import Protocol

from build123d import Compound, Location, Part, RigidJoint


class LegInstallation(Protocol):
    """An installation site; concrete implementations define attachment methods."""

    @property
    def body(self) -> Part:
        """Body containing the installation site."""
        ...

    @property
    def local_placement(self) -> Location:
        """Neutral leg source frame relative to the body's modeling frame."""
        ...


class Leg[InstallationT: LegInstallation](Protocol):
    """Geometry and installation interface for a shoulder-rest implementation."""

    @property
    def part(self) -> Part:
        """Printable child for export; position the whole assembly for modeling."""
        ...

    @property
    def assembly(self) -> Compound:
        """Printable leg and any hardware; position the complete assembly."""
        ...

    @property
    def tool(self) -> Part:
        """Cavity tool snapshot at the template assembly's current placement."""
        ...

    @property
    def housing(self) -> Part:
        """Required surrounding material guide; never automatically added to a rest."""
        ...

    @property
    def mount_joint(self) -> RigidJoint:
        """Installation reference on the complete template assembly."""
        ...

    def install(
        self, body: Part, *, at: Location, joint_label: str = "leg",
    ) -> InstallationT:
        """Modify body in place at a local frame and return an installation site.

        Preserve the body's modeling frame, placement, and existing site joints.
        The caller transfers the Part for construction and final nesting.
        Concrete installation methods choose which components to attach later.
        Use joint_label to distinguish attachments from other installations.
        """
        ...
