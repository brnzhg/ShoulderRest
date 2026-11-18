"""An example shoulder scan and violin fit, for previews and tests; run to preview it.

The casts in ``data/shoulder_cast/`` are one player's scan. They are example
data, not part of the library: load your own casts with
``shoulder_rest.parts.shoulder.step_shoulder.load_shoulder``.
"""

from pathlib import Path

from build123d import Location, Pos, Rotation

from shoulder_rest.parts.shoulder import Shoulder
from shoulder_rest.parts.shoulder.step_shoulder import load_shoulder

DATA = Path(__file__).parent / "data" / "shoulder_cast"

CAST_LOCATION = Location((0, 0, 0), (30, 30, -5))
"""Levels the example scan in the shoulder frame."""

VIOLIN_LOCATION = (
    Pos(-55, -87.5, 57.5) * Rotation(0, 0, 66) * Rotation(8, 0, 0)
    * Location((18, 2, 24), (0, -24, 0))
)
"""A violin mount frame fitted to the example scan: a point on the cast, turned
about the vertical, tilted level, offset and rolled."""


def load_example_shoulder(violin_location: Location = VIOLIN_LOCATION) -> Shoulder:
    return load_shoulder(
        DATA / "reference.step", DATA / "extended.step", violin_location,
        cast_location=CAST_LOCATION,
    )


if __name__ == "__main__":
    from ocp_vscode import show

    shoulder = load_example_shoulder()
    show(
        shoulder.assembly, shoulder.extended, shoulder.violin_joint.symbol,
        names=["Shoulder", "Extended cutting tool", "Violin mount"],
    )
