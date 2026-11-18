"""A contoured bar rest with hinge legs on the example shoulder.

uv run python examples/bar_rest_fitting.py
"""

from build123d import Compound

from example_shoulder import load_example_shoulder
from shoulder_rest.parts.leg.hinge_leg import HingeLeg
from shoulder_rest.parts.rest import Rest
from shoulder_rest.parts.rest.bar_rest import contoured_bar_rest_geometry
from shoulder_rest.parts.violin_outline.spline_violin_outline import build_violin_outline


def main() -> None:
    from ocp_vscode import show

    shoulder = load_example_shoulder()
    violin = build_violin_outline()
    violin.position_on(shoulder)
    rest = Rest(contoured_bar_rest_geometry(violin, shoulder), HingeLeg())
    rest.add(rest.left.leg(angle=20))
    rest.add(rest.right.leg())
    rest.add(rest.left.housing)
    rest.add(rest.right.housing)
    rest.position_on(violin)
    show(Compound(label="Bar rest fitting", children=[shoulder.assembly, violin.block, rest.assembly]))


if __name__ == "__main__":
    main()
