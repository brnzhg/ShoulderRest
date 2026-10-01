"""Leg interface and installation results for rest implementations."""

from typing import Protocol

from build123d import Compound, Part, RigidJoint, Solid


class LegInstallation(Protocol):
    """Independent installation result responsible for its own final attachment.

    Each installation returns a new body, preserving existing attachment frames.
    Complete every installation before calling attach_to with the final body.
    Joint types, attachment settings, and connection details belong to the
    implementation. Tools and guides remain snapshots at installation time.
    """

    @property
    def rest(self) -> Part | Solid:
        """Body after this installation, before any subsequent cuts."""
        ...

    @property
    def leg(self) -> Compound:
        """Independent leg assembly, ready for attachment and scene nesting."""
        ...

    @property
    def tool(self) -> Part:
        """Positioned cavity tool snapshot."""
        ...

    @property
    def housing(self) -> Part:
        """Positioned surrounding-material guide snapshot."""
        ...

    def attach_to(self, final_body: Part | Solid) -> None:
        """Attach this leg to the final body before nesting either in a scene.

        Resolve any required frames on final_body, not the intermediate rest.
        Position the leg and connect joints as needed without changing body
        geometry. Attachment configuration is owned by the leg implementation.
        """
        ...


class Leg(Protocol):
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
        self, mount: RigidJoint, *, joint_label: str = "leg",
    ) -> LegInstallation:
        """Return a new body and independent leg without modifying inputs.

        Preserve existing joints. Use joint_label to distinguish this
        installation's attachment data from other installations on the body.
        """
        ...
