"""The bundled shoulder cast, loaded from STEP files; run to preview it."""

from importlib.resources import as_file, files

from build123d import Location, Pos, Rotation, VectorLike, import_step

from .shoulder import Shoulder


CAST_LOCATION = Location((0, 0, 0), (30, 30, -5))
"""Maps the bundled STEP files' scan frame into the corrected shoulder frame."""


def fitted_violin_location(
    *, angle: float = 24, level: float = 8, roll: float = 24,
    offset: VectorLike = (18, 2, 24),
) -> Location:
    """Violin mount frame on the bundled cast, in degrees and mm.

    Starting from a base point on the cast, ``angle`` turns the violin about
    the vertical, ``level`` tilts it level, ``offset`` moves it in that turned
    frame and ``roll`` rolls it about the mount Y axis.
    """
    base = Pos(-55, -87.5, 57.5)
    return (
        base * Rotation(0, 0, 90 - angle) * Rotation(level, 0, 0)
        * Location(offset, (0, -roll, 0))
    )


def load_shoulder_cast(
    cast_location: Location = CAST_LOCATION,
    violin_location: Location | None = None,
) -> Shoulder:
    """Load the bundled casts; ``violin_location`` defaults to the current fit."""
    if violin_location is None:
        violin_location = fitted_violin_location()
    assets = files("shoulder_rest").joinpath("assets", "shoulder_cast")
    with (
        as_file(assets.joinpath("shoulder_reference_solid.step")) as reference_file,
        as_file(assets.joinpath("shoulder_extended_solid.step")) as extended_file,
    ):
        reference = import_step(reference_file).moved(cast_location)
        extended = import_step(extended_file).moved(cast_location)
    reference.label = "Shoulder reference"
    extended.label = "Shoulder extended"
    return Shoulder(reference, extended, violin_location)


if __name__ == "__main__":
    from ocp_vscode import show

    shoulder = load_shoulder_cast()
    show(
        shoulder.assembly, shoulder.extended, shoulder.violin_joint.symbol,
        names=["Shoulder", "Extended cutting tool", "Violin mount"],
    )
