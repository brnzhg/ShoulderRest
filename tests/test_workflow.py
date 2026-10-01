"""Smoke checks for assembly workflows; inspect evolving geometry in CAD previews."""

import unittest

from build123d import Compound, Location

from shoulder_rest.parts.leg.hinge_leg import build_hinge_leg
from shoulder_rest.parts.rest import Rest
from shoulder_rest.parts.shoulder.step_shoulder import load_shoulder_cast
from shoulder_rest.parts.simple_rest import SimpleRestGeometry, build_simple_rest
from shoulder_rest.parts.violin_outline.spline_violin_outline import build_violin_outline


class WorkflowTests(unittest.TestCase):
    def test_assemble_rest_and_fit_to_shoulder(self) -> None:
        shoulder = load_shoulder_cast(
            cast_location=Location((0, 0, 0), (30, 30, -5)),
            violin_location=Location((-55, -87.5, 57.5), (4, -26, 60)),
        )
        violin = build_violin_outline()
        violin.position_on(shoulder)
        self.assertEqual(violin.mount_joint.location, shoulder.violin_joint.location)

        geometry = SimpleRestGeometry(violin)
        rest = Rest(geometry, build_hinge_leg())
        rest.position_on(violin)
        self.assertEqual(rest.violin_joint.location, violin.mount_joint.location)
        scene = Compound(children=[shoulder.assembly, violin.block, rest.assembly])
        self.assertTrue(scene.is_valid)

    def test_fit_assembled_rest_and_reposition(self) -> None:
        violin = build_violin_outline()
        rest = build_simple_rest(
            violin, build_hinge_leg(angle=15), right_leg=build_hinge_leg(angle=-10),
        )
        for pose in (Location(), Location((20, -30, 40), (10, 20, 30))):
            violin.block.locate(pose)
            rest.position_on(violin)
            self.assertEqual(rest.violin_joint.location, violin.mount_joint.location)
        self.assertTrue(rest.assembly.is_valid)


if __name__ == "__main__":
    unittest.main()
