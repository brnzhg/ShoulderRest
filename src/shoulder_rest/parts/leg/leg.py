"""Leg interface and installation results for rest implementations."""

from typing import Protocol

from build123d import Compound, Location, Part, RigidJoint


class LegInstallation(Protocol):
    """Independent installation result responsible for its own final attachment.

    Each installation preserves the body's local modeling frame and placement.
    Complete every installation before calling attach_to with the final body.
    Joint types, attachment settings, and connection details belong to the
    implementation. Tools and guides remain snapshots at installation time.
    """

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

    def attach_to(self, final_body: Part) -> None:
        """Attach this leg to the final body before nesting either in a scene.

        Use the retained local installation frame and final_body's placement to
        create attachment joints or position the leg without changing body
        geometry. No attachment joint needs to survive the intermediate cuts.
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
        self, body: Part, *, at: Location, joint_label: str = "leg",
    ) -> LegInstallation:
        """Modify body in place at a local frame and return an independent leg result.

        Preserve the body's modeling frame and placement. Existing joints and
        connections need not be carried through cuts. The caller transfers
        the Part for construction and final nesting.
        Retain attachment data locally and create final joints in attach_to().
        Use joint_label to distinguish attachments from other installations.
        """
        ...
