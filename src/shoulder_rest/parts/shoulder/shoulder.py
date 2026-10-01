"""Shoulder geometry and violin attachment interface."""

from typing import Protocol

from build123d import Compound, RigidJoint


class Shoulder(Protocol):
    """Geometry and attachment interface, independent of the source of the casts.

    Tool properties return independent shapes in world coordinates. Retrieve them
    after positioning the assembly; previously retrieved shapes are snapshots.
    """

    @property
    def reference(self) -> Compound:
        """Reference shoulder shape for contact geometry and inspection."""
        ...

    @property
    def extended(self) -> Compound:
        """Extended shoulder shape for cutting the rest."""
        ...

    @property
    def assembly(self) -> Compound:
        """Reference-only assembly to position or include in the final assembly."""
        ...

    @property
    def violin_joint(self) -> RigidJoint:
        """Violin attachment on the assembly, named 'violin'."""
        ...
