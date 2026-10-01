"""Shoulder geometry and violin attachment; run this module to preview them."""

from copy import deepcopy
from importlib.resources import as_file, files
from os import PathLike

from build123d import Compound, Location, RigidJoint, import_step
from .shoulder import Shoulder


class StepShoulder(Shoulder):
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
        cast_location: Location,
        violin_location: Location,
    ) -> None:
        self._reference = import_step(reference_file).moved(cast_location)
        self._reference.label = "Shoulder reference"
        self._extended = import_step(extended_file).moved(cast_location)
        self._extended.label = "Shoulder extended"
        self._assembly = Compound(
            label="Shoulder", children=[deepcopy(self._reference)]
        )
        self._violin_joint = RigidJoint(
            "violin",
            to_part=self._assembly,
            joint_location=violin_location
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


# TODO attach a box to the violin joint to view
def load_shoulder_cast(
        cast_location: Location,
        violin_location: Location,
    ) -> Shoulder:

    assets = files("shoulder_rest").joinpath("assets", "shoulder_cast")
    with (
        as_file(assets.joinpath("shoulder_reference_solid.step")) as reference_file,
        as_file(assets.joinpath("shoulder_extended_solid.step")) as extended_file,
    ):
        return StepShoulder(
            reference_file,
            extended_file,
            cast_location=(
                cast_location
                #Location((0, 0, 0), (30, 30, -5))
            ),
            violin_location=(
                violin_location
            ),
        )

if __name__ == "__main__":
    from ocp_vscode import show

    shoulder = load_shoulder_cast(
        cast_location=Location((0, 0, 0), (30, 30, -5)),
        violin_location=(
            # Base location, violin level correction, orient Z direction
            Location((-55, -87.5, 57.5), (4, 0, 90 - 30)) * 
            # Offset from base, violin roll angle
            Location((0, 5, 20), (0, -26, 0))
        )
    )
    show(
        shoulder.assembly,
        shoulder.extended,
        shoulder.violin_joint.symbol,
        names=["Shoulder", "Extended cutting tool", "Violin attachment"],
    )
