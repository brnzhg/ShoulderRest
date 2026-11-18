"""Load a shoulder from STEP casts of a scan."""

from os import PathLike

from build123d import Location, import_step

from .shoulder import Shoulder


def load_shoulder(
    reference: PathLike[str] | str, extended: PathLike[str] | str, violin_location: Location,
    *, cast_location: Location = Location(),
) -> Shoulder:
    """Load reference and extended casts from STEP files.

    ``cast_location`` maps the files' scan frame into the shoulder frame, for
    example to level a scan taken at an arbitrary orientation.
    ``violin_location`` is in the shoulder frame (see ``Shoulder``).
    """
    reference_cast = import_step(reference).moved(cast_location)
    extended_cast = import_step(extended).moved(cast_location)
    reference_cast.label = "Shoulder reference"
    extended_cast.label = "Shoulder extended"
    return Shoulder(reference_cast, extended_cast, violin_location)
