"""Leg interface: what a rest needs from any leg mechanism.

A mount frame places a leg on a rest body: its origin is on the body's flat
mounting face and its Z axis points into the body. Each leg implementation
defines how X and Y orient it; ``rest.leg_mount`` builds frames from a facing
direction. Dimensions are in millimeters.
"""

from typing import Protocol

from build123d import Compound, Location, Part


class LegInstallation(Protocol):
    """One leg site on a rest body; every placement is in the body's local frame."""

    @property
    def location(self) -> Location:
        """Mount frame of this site."""
        ...

    @property
    def housing(self) -> Part:
        """Fresh guide of the material the site needs around its cavity."""
        ...

    def leg(self) -> Compound:
        """Fresh leg component at its neutral pose, seated in this site."""
        ...


class Leg[InstallationT: LegInstallation](Protocol):
    """A leg design: a printable part and the cavity it needs in a rest body."""

    @property
    def part(self) -> Part:
        """Printable leg in its own modeling frame, for export."""
        ...

    def install(self, body: Part, *, at: Location) -> tuple[Part, InstallationT]:
        """Return a copy of body with this leg's cavity cut at mount frame ``at``.

        ``body`` is in its local modeling frame and ``at`` is in those
        coordinates. Also returns the site, for adding leg components later.
        """
        ...
