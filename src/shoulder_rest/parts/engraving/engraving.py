"""Shallow 2D designs, such as version IDs, recessed into a flat face.

Engravings are cut rather than raised so they never stand proud of a
functional surface. For FDM prints, keep the depth to a few layers and keep
strokes and the gaps between them at least about a nozzle width wide, or the
slicer drops them. A recess on a face that points up during printing needs no
support; its floor prints as a top surface.
"""

from dataclasses import dataclass
from math import isfinite

from build123d import Face, Location, Part, Plane, Sketch, extrude

from shoulder_rest.parts._validation import single_solid


@dataclass(frozen=True)
class Engraving:
    """A design in local XY, cut ``depth`` mm along -Z.

    The design reads correctly viewed from +Z, the side its face points
    toward. Its origin is the anchor that a placement puts on the face.
    Builders such as ``text_engraving`` produce one; any flat sketch works.
    """

    design: Sketch
    depth: float

    def __post_init__(self) -> None:
        if not isfinite(self.depth) or self.depth <= 0:
            raise ValueError("Engraving depth must be finite and positive")
        if not self.design.faces():
            raise ValueError("Engraving design must contain at least one face")
        box = self.design.bounding_box()
        if abs(box.min.Z) > 1e-6 or abs(box.max.Z) > 1e-6:
            raise ValueError("Engraving design must lie in its local XY plane")


def engrave(body: Part, engraving: Engraving, face: Face, at: Location) -> Part:
    """Cut an engraving into one flat face of a body and return the new body.

    ``at`` is the design's frame on the face: its origin lies on ``face`` and
    its Z points out of the body. The whole design must fit inside the face,
    so it stays clear of fillets and edges.
    """
    placed = at * engraving.design
    outward = Plane(at).z_dir
    if not face.is_inside(at.position):
        raise ValueError("Engraving origin must lie on the face; move it")
    if (outward - face.normal_at(at.position)).length > 1e-6:
        raise ValueError("Engraving frame Z must follow the face's outward normal")
    # Spline glyph areas are approximate, so sample the outline instead.
    samples = [edge @ t for edge in placed.edges() for t in (0, 0.25, 0.5, 0.75)]
    if not all(face.is_inside(point) for point in samples):
        raise ValueError("Engraving must fit inside the face; move or shrink it")
    tool = extrude(placed, amount=-engraving.depth, dir=outward)
    return single_solid(body - tool, "Engraving must leave one valid solid")
