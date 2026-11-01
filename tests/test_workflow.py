"""Interface smoke checks; inspect evolving geometry in CAD previews."""

import unittest

from build123d import Compound, Location, Pos, Rotation

from shoulder_rest.parts.leg.hinge_leg import build_hinge_leg
from shoulder_rest.parts.rest import Rest
from shoulder_rest.parts.shoulder.step_shoulder import load_shoulder_cast
from shoulder_rest.parts.simple_rest import build_simple_rest
from shoulder_rest.parts.violin_outline.spline_violin_outline import build_violin_outline
from shoulder_rest.parts.wrest import WRestGeometry


class WorkflowTests(unittest.TestCase):
    def test_w_rest_constructs_and_positions_on_violin(self) -> None:
        """Catch construction failures and local/world frame mixups in the W workflow."""
        shoulder = load_shoulder_cast(
            cast_location=Location((0, 0, 0), (30, 30, -5)),
            violin_location=(
                Pos(-55, -87.5, 57.5) * Rotation(0, 0, 66) * Rotation(8, 0, 0)
                * Location((18, 2, 24), (0, -24, 0))
            ),
        )
        violin = build_violin_outline()
        geometry = WRestGeometry(violin, shoulder)
        self.assertEqual(geometry.part.location, Location())
        rest = Rest(geometry, build_hinge_leg())
        rest.position_on(violin)
        self.assertEqual(rest.violin_joint.location, violin.mount_joint.location)
        self.assertTrue(rest.part.is_valid)
        self.assertEqual(len(rest.part.solids()), 1)

    def test_attachments_follow_nested_rest(self) -> None:
        """Catch misplaced attachments when adding to or moving a nested assembly."""
        violin = build_violin_outline()
        violin.block.locate(Location((20, -30, 40), (10, 20, 30)))
        rest = build_simple_rest(violin, build_hinge_leg())
        rest.position_on(violin)
        self.assertEqual(rest.violin_joint.location, violin.mount_joint.location)
        scene = Compound(children=[rest.assembly])
        scene.locate(Location((5, 10, -15), (15, -20, 5)))
        leg = rest.left.attach_to(rest.assembly, angle=15)
        housing = rest.left.attach_housing_to(rest.assembly)
        for pose in (scene.location, Location((30, -10, 5), (-20, 5, 15))):
            scene.locate(pose)
            self.assertEqual(
                leg.global_location,
                rest.left.tool.location * Rotation(15, 0, 0),
            )
            self.assertEqual(
                housing.global_location,
                rest.part.global_location * rest.left.local_placement,
            )
        self.assertTrue(scene.is_valid)


if __name__ == "__main__":
    unittest.main()
