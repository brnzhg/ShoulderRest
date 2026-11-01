"""Interface smoke checks; inspect evolving geometry in CAD previews."""

import unittest

from build123d import Compound, Location, Rotation

from shoulder_rest.parts.leg.hinge_leg import HingeLeg
from shoulder_rest.parts.rest import Rest
from shoulder_rest.parts.rest.bar_rest import bar_rest_geometry
from shoulder_rest.parts.rest.w_rest import (
    WHeadCapParameters, WHeadParameters, WRestParameters, w_rest_geometry,
)
from shoulder_rest.parts.shoulder.step_shoulder import load_shoulder_cast
from shoulder_rest.parts.violin_outline.spline_violin_outline import build_violin_outline


class WorkflowTests(unittest.TestCase):
    def test_w_rest_constructs_and_positions_on_violin(self) -> None:
        """Catch construction failures and local/world frame mixups in the W workflow."""
        shoulder = load_shoulder_cast()
        violin = build_violin_outline()
        violin.position_on(shoulder)
        geometry = w_rest_geometry(violin, shoulder, WRestParameters(head=WHeadParameters(
            left_cap=WHeadCapParameters(angle=24, height=34, depth=30),
            right_cap=WHeadCapParameters(angle=10, height=30, depth=20),
        )))
        rest = Rest(geometry, HingeLeg())
        rest.position_on(violin)
        self.assertEqual(rest.violin_joint.location, violin.mount_joint.location)
        self.assertTrue(rest.part.is_valid)
        self.assertEqual(len(rest.part.solids()), 1)

    def test_components_follow_nested_rest(self) -> None:
        """Catch misplaced components when adding to or moving a nested assembly."""
        violin = build_violin_outline()
        violin.block.locate(Location((20, -30, 40), (10, 20, 30)))
        rest = Rest(bar_rest_geometry(violin), HingeLeg())
        rest.position_on(violin)
        self.assertEqual(rest.violin_joint.location, violin.mount_joint.location)
        scene = Compound(children=[rest.assembly])
        scene.locate(Location((5, 10, -15), (15, -20, 5)))
        leg = rest.add(rest.left.leg(angle=15))
        housing = rest.add(rest.left.housing)
        for pose in (scene.location, Location((30, -10, 5), (-20, 5, 15))):
            scene.locate(pose)
            site = rest.assembly.global_location * rest.left.placement
            self.assertEqual(leg.global_location, site * Rotation(15, 0, 0))
            self.assertEqual(housing.global_location, site)
        self.assertTrue(scene.is_valid)


if __name__ == "__main__":
    unittest.main()
