"""A striped, capped W rest with hinge legs on the example shoulder.

uv run python examples/w_rest_fitting.py
"""

from build123d import Compound

from example_shoulder import load_example_shoulder
from shoulder_rest.parts.engraving.text_engraving import text_engraving
from shoulder_rest.parts.leg.hinge_leg import HingeLeg
from shoulder_rest.parts.leg.rod_retention import RodRetentionParameters
from shoulder_rest.parts.rest import Rest
from shoulder_rest.parts.rest.w_rest import (
    WHeadCapParameters, WHeadParameters, WRestParameters, WStripeParameters, WTailParameters,
    w_rest_geometry,
)
from shoulder_rest.parts.violin_outline.spline_violin_outline import build_violin_outline


def main() -> None:
    from ocp_vscode import show

    shoulder = load_example_shoulder()
    violin = build_violin_outline()
    violin.position_on(shoulder)
    geometry = w_rest_geometry(violin, shoulder, WRestParameters(head=WHeadParameters(
        left_cap=WHeadCapParameters(angle=24, height=34, depth=30),
        right_cap=WHeadCapParameters(angle=10, height=30, depth=20),
        stripes=WStripeParameters(),
    ), tail=WTailParameters(engraving=text_engraving("v1.0"))))
    # show(geometry.part)  # Inspect the body in its local frame.
    rest = Rest(geometry, HingeLeg(rod_retention=RodRetentionParameters()))
    rest.add(rest.left.leg(angle=20))
    rest.add(rest.right.leg())
    rest.add(rest.left.housing)
    rest.add(rest.right.housing)
    rest.position_on(violin)
    show(Compound(label="W rest fitting", children=[shoulder.assembly, violin.block, rest.assembly]))


if __name__ == "__main__":
    main()
