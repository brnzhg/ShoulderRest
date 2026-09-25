"""Shoulder geometry and violin attachment; run this module to preview them."""

from copy import deepcopy
from importlib.resources import as_file, files
from os import PathLike
from typing import Protocol

from build123d import Compound, Location, RigidJoint, import_step


# Example placement: adjust XYZ translation (mm) and XYZ rotation (degrees).
# Both casts rotate about the source origin, then translate together.
POSITION = (0.0, 0.0, 0.0)
ROTATION = (30.0, 30.0, -5.0)

# Violin placement in the corrected shoulder frame (mm and degrees).
VIOLIN_POSITION = (0.0, 0.0, 20.0)
VIOLIN_ROTATION = (0.0, 0.0, 0.0)


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


class StepShoulder:
    """A Shoulder made from two STEP files sharing one source coordinate frame.

    ``cast_location`` maps both files into the corrected shoulder frame.
    ``violin_location`` is specified directly in that corrected frame, without
    applying ``cast_location`` again. Both default to the identity location.

    Position the finished shoulder through ``assembly.locate(...)`` or its joint.
    Connect joints before nesting the assembly, following build123d's convention.
    """

    def __init__(
        self,
        reference_file: str | PathLike[str],
        extended_file: str | PathLike[str],
        *,
        cast_location: Location | None = None,
        violin_location: Location | None = None,
    ) -> None:
        placement = Location() if cast_location is None else cast_location
        self._reference = import_step(reference_file).moved(placement)
        self._reference.label = "Shoulder reference"
        self._extended = import_step(extended_file).moved(placement)
        self._extended.label = "Shoulder extended"
        self._assembly = Compound(
            label="Shoulder", children=[deepcopy(self._reference)]
        )
        self._violin_joint = RigidJoint(
            "violin",
            to_part=self._assembly,
            joint_location=Location() if violin_location is None else violin_location,
        )

    @property
    def reference(self) -> Compound:
        return self._reference.moved(self._assembly.global_location)

    @property
    def extended(self) -> Compound:
        return self._extended.moved(self._assembly.global_location)

    @property
    def assembly(self) -> Compound:
        return self._assembly

    @property
    def violin_joint(self) -> RigidJoint:
        return self._violin_joint


def load_shoulder(
    *,
    cast_location: Location | None = None,
    violin_location: Location | None = None,
) -> Shoulder:
    """Load the bundled shoulder using the example placements unless overridden."""
    assets = files("shoulder_rest").joinpath("assets", "shoulder_cast")
    with (
        as_file(assets.joinpath("shoulder_reference_solid.step")) as reference_file,
        as_file(assets.joinpath("shoulder_extended_solid.step")) as extended_file,
    ):
        return StepShoulder(
            reference_file,
            extended_file,
            cast_location=(
                Location(POSITION, ROTATION) if cast_location is None else cast_location
            ),
            violin_location=(
                Location(VIOLIN_POSITION, VIOLIN_ROTATION)
                if violin_location is None
                else violin_location
            ),
        )


if __name__ == "__main__":
    from ocp_vscode import show

    shoulder = load_shoulder()
    show(
        shoulder.assembly,
        shoulder.extended,
        shoulder.violin_joint.symbol,
        names=["Shoulder", "Extended cutting tool", "Violin attachment"],
    )
