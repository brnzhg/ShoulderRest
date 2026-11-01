"""A shoulder cast and the violin placement fitted to it."""

from copy import copy

from build123d import Compound, Location, RigidJoint, Shape


class Shoulder:
    """Shoulder casts and the violin's place on them, in one local frame.

    ``reference`` is the cast surface, for display and inspection. ``extended``
    is the cast grown away from the skin, for contouring rest bodies.
    ``violin_location`` is where the violin's mount frame
    (``ViolinOutline.mount_location``) sits in the shoulder frame.

    The shapes and ``violin_location`` never move. ``assembly`` displays the
    reference cast and carries ``violin_joint``; move the assembly to place the
    shoulder in a scene.
    """

    def __init__(
        self, reference: Shape, extended: Shape, violin_location: Location,
    ) -> None:
        self.reference = reference
        self.extended = extended
        self.violin_location = violin_location
        self.assembly = Compound(label="Shoulder", children=[copy(reference)])
        self.violin_joint = RigidJoint("violin", self.assembly, violin_location)

    def cutter(self, violin_mount: Location) -> Shape:
        """The extended cast in a rest body's frame, for subtracting from the body.

        ``violin_mount`` is the body's frame that meets the violin mount, in
        the body's local coordinates (see ``RestGeometry.violin_mount``).
        """
        return self.extended.moved(violin_mount * self.violin_location.inverse())
