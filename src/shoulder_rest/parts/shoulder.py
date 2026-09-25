"""Import and position the shoulder casts; run this file to preview both."""

from importlib.resources import as_file, files

from build123d import Compound, Location, import_step


# Example placement: adjust XYZ translation (mm) and XYZ rotation (degrees).
# Both casts rotate about the source origin, then translate together.
POSITION = (0.0, 0.0, 0.0)
ROTATION = (30.0, 30.0, -5.0)


def load_shoulders(
    position: tuple[float, float, float],
    rotation: tuple[float, float, float]
) -> tuple[Compound, Compound]:
    """Return the reference and extended casts with the same placement."""
    placement = Location(position, rotation)
    assets = files("shoulder_rest").joinpath("assets", "shoulder_cast")
    with as_file(assets.joinpath("shoulder_reference_solid.step")) as path:
        reference = import_step(path)
    with as_file(assets.joinpath("shoulder_extended_solid.step")) as path:
        extended = import_step(path)
    return reference.moved(placement), extended.moved(placement)


if __name__ == "__main__":
    from ocp_vscode import show

    shoulder = load_shoulders(POSITION, ROTATION)
    show(shoulder)
