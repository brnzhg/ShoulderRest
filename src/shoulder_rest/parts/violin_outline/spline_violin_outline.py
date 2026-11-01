"""Violin outline interpolated through a traced right-hand half; run to preview it."""

from collections.abc import Sequence
from math import isfinite

from build123d import Spline

from .violin_outline import ViolinOutline


TRACED_RIGHT_OUTLINE = (
    (87.175, -56.570),
    (91.220, -49.3),
    (96.473, -37.724),
    (101.728, -15.76),
    (102.605, 0.0),
    (101.12, 15.165),
    (94.784, 32.802),
    (84.79, 46.767),
    (65.910, 61.558),
    (43.630, 69.918),
    (18.865, 73.536),
)
"""Right half of the bundled violin tracing, in mm."""


def build_violin_outline(
    points: Sequence[tuple[float, float]] = TRACED_RIGHT_OUTLINE, *,
    attachment_offset: float = 6.0, block_thickness: float = 38.0,
) -> ViolinOutline:
    """Interpolate XY points with positive X and strictly increasing Y."""
    if len(points) < 2 or not all(isfinite(x) and isfinite(y) and x > 0 for x, y in points):
        raise ValueError("Provide at least two finite XY points with positive X")
    if any(a[1] >= b[1] for a, b in zip(points, points[1:])):
        raise ValueError("Outline points must have strictly increasing Y")
    return ViolinOutline(
        Spline(*points),
        attachment_offset=attachment_offset, block_thickness=block_thickness,
    )


if __name__ == "__main__":
    from build123d import Polyline
    from ocp_vscode import show

    violin = build_violin_outline()
    # A guide between attachment points stays on the curves when parameters change.
    guide = Polyline(
        violin.attachment_point("left", 0.25), (0, 10), violin.attachment_point("right", 0.60),
    )
    show(
        violin.block, violin.left, violin.right, violin.left_attachment,
        violin.right_attachment, guide, violin.mount_joint.symbol,
        names=[
            "Violin block", "Left outline", "Right outline",
            "Left attachment", "Right attachment", "Example rest guide", "Mount frame",
        ],
    )
