"""Checks shared by the geometry builders."""

from build123d import Part, Shape


def single_solid(shape: Shape | None, message: str) -> Part:
    """Return shape as a Part, raising ValueError(message) unless it is one valid solid."""
    if shape is None or not shape.is_valid or len(shape.solids()) != 1:
        raise ValueError(message)
    return shape if isinstance(shape, Part) else Part(shape.solids())
