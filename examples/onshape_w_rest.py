"""Approximate Rest091126 / Rest4.1 / configuration 4S14 from Onshape.

Reference: https://cad.onshape.com/documents/2dfee749c754c98b8b01074a/w/047fdd36ce12f1f0e8f1fa58/e/f1f59ad224076e4bc4ef1241

Sketch Center Line uses horizontal dimensions: 60 mm from the extended head
end to its first bend, with the mount 20 mm in from that end; then 56 and
36 mm to the next bends. The first and third strokes are parallel at 10 deg.
The tail is horizontal and its mount is 8 mm higher in sketch Y than the
head mount. Transform 1/2 use these sketch vertices without translation.

The reference is reflected in X to use the library's head-on-right convention:
Transform 1 becomes the right/head mount, Transform 2 the left/tail mount.
The attachment fractions below approximate sketch Y=14 and Y=22 on the
library's default 6 mm inward attachment curves. No Onshape features are edited.

uv run python examples/onshape_w_rest.py
uv run python examples/onshape_w_rest.py --centerline
"""

import argparse
from math import atan2, cos, degrees, hypot, radians, tan

from build123d import Compound, Polyline, Wire

from shoulder_rest.parts.leg.hinge_leg import HingeLeg
from shoulder_rest.parts.leg.rod_retention import RodRetentionParameters
from shoulder_rest.parts.rest import Rest
from shoulder_rest.parts.rest.w_rest import (
    Stroke, WHeadCapParameters, WHeadParameters, WPathParameters, WRestParameters,
    WStripeParameters, w_rest_geometry,
)
from shoulder_rest.parts.shoulder.step_shoulder import load_shoulder_cast
from shoulder_rest.parts.violin_outline import ViolinOutline
from shoulder_rest.parts.violin_outline.spline_violin_outline import build_violin_outline


def reference_parameters() -> tuple[ViolinOutline, WRestParameters]:
    """Build the traced violin and the W parameters fitted specifically to it."""
    violin = build_violin_outline(attachment_offset=6)
    right_fraction, left_fraction = 0.41019865, 0.45864359
    # Mount centers are approximately (95.23, 14) and (-93.02, 22) mm.
    right = violin.attachment_point("right", right_fraction)
    left = violin.attachment_point("left", left_fraction)
    angle = radians(10)
    # Make the third bend land at the tail mount's Y so the tail stays horizontal.
    # 8 mm between mounts + 13.40 mm to undo the outer strokes' fall = 21.40 mm.
    middle_rise = left.Y - right.Y + (40 + 36) * tan(angle)
    parameters = WRestParameters(
        right_fraction=right_fraction,
        left_fraction=left_fraction,
        path=WPathParameters(
            strokes=(
                Stroke(40 / cos(angle), 10),  # 40.62 mm along the first stroke.
                # 59.95 mm long, at -20.91 degrees from -X.
                Stroke(hypot(56, middle_rise), -degrees(atan2(middle_rise, 56))),
                Stroke(36 / cos(angle), 10),  # 36.56 mm along the third stroke.
            ),
            right_extend=20 / cos(angle),  # 20.31 mm along the first stroke.
            left_extend=10,
        ),
        head=WHeadParameters(
            left_cap=WHeadCapParameters(angle=24, height=34, depth=30),
            right_cap=WHeadCapParameters(angle=10, height=30, depth=20),
            stripes=WStripeParameters(),
        ),
    )
    return violin, parameters


def sketch_centerline(violin: ViolinOutline, p: WRestParameters) -> Wire:
    """Unrounded construction strokes for comparing with Sketch Center Line."""
    right = violin.attachment_point("right", p.right_fraction)
    left = violin.attachment_point("left", p.left_fraction)
    points = [right - p.path.strokes[0].vector.normalized() * p.path.right_extend, right]
    for stroke in p.path.strokes:
        points.append(points[-1] + stroke.vector)
    tail_direction = (left - points[-1]).normalized()
    return Polyline(*points, left, left + tail_direction * p.path.left_extend)


def main() -> None:
    from ocp_vscode import show

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--centerline", action="store_true", help="Preview only the local XY layout")
    args = parser.parse_args()
    violin, parameters = reference_parameters()
    if args.centerline:
        show(violin.left, violin.right, violin.left_attachment, violin.right_attachment,
             sketch_centerline(violin, parameters),
             names=["Violin left", "Violin right", "Left attachment", "Right attachment",
                    "Sketch Center Line (library frame)"])
        return

    shoulder = load_shoulder_cast()
    geometry = w_rest_geometry(violin, shoulder, parameters)
    rest = Rest(geometry, HingeLeg(rod_retention=RodRetentionParameters()))
    rest.add(rest.left.leg(angle=20))
    rest.add(rest.right.leg())
    rest.add(rest.left.housing)
    rest.add(rest.right.housing)
    violin.position_on(shoulder)
    rest.position_on(violin)
    show(Compound(label="Onshape reference W rest", children=[
        shoulder.assembly, violin.block, rest.assembly,
    ]))


if __name__ == "__main__":
    main()
