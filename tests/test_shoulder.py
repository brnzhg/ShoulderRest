"""Check the coordinate frames and assembly behavior of STEP shoulders."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from build123d import Box, Compound, Location, RigidJoint, export_step

from shoulder_rest.parts.shoulder import Shoulder
from shoulder_rest.parts.shoulder.step_shoulder import StepShoulder


class ShoulderTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        reference_file = Path(directory.name) / "reference.step"
        extended_file = Path(directory.name) / "extended.step"
        export_step(Box(2, 4, 6).moved(Location((1, 2, 3))), reference_file)
        export_step(Box(4, 6, 8).moved(Location((4, 5, 6))), extended_file)
        self.joint_location = Location((7, 8, 9), (15, 25, 35))
        self.shoulder: Shoulder = StepShoulder(
            reference_file,
            extended_file,
            cast_location=Location((10, 20, 30), (0, 0, 90)),
            violin_location=self.joint_location,
        )

    def assert_center(self, shape: Compound, expected: tuple[float, ...]) -> None:
        for actual, target in zip(shape.center(), expected):
            self.assertAlmostEqual(actual, target, places=6)

    def test_cast_transform_does_not_transform_violin_offset(self) -> None:
        self.assert_center(self.shoulder.reference, (8, 21, 33))
        self.assert_center(self.shoulder.extended, (5, 24, 36))
        self.assertEqual(self.shoulder.violin_joint.location, self.joint_location)
        self.assertIs(
            self.shoulder.assembly.joints["violin"], self.shoulder.violin_joint
        )

    def test_assembly_contains_only_reference_and_tools_are_independent(self) -> None:
        self.assertEqual(len(self.shoulder.assembly.children), 1)
        self.assertAlmostEqual(self.shoulder.assembly.volume, 48)
        self.assertAlmostEqual(self.shoulder.extended.volume, 192)
        tool = self.shoulder.reference
        tool.move(Location((100, 0, 0)))
        self.assert_center(self.shoulder.reference, (8, 21, 33))
        self.assert_center(self.shoulder.assembly, (8, 21, 33))

    def test_moving_assembly_moves_both_tools_and_joint(self) -> None:
        placement = Location((100, 200, 300), (90, 0, 0))
        self.shoulder.assembly.locate(placement)
        self.assert_center(self.shoulder.reference, (108, 167, 321))
        self.assert_center(self.shoulder.extended, (105, 164, 324))
        self.assertEqual(
            self.shoulder.violin_joint.location, placement * self.joint_location
        )

    def test_joint_can_place_violin_or_shoulder(self) -> None:
        violin = Box(1, 2, 3)
        violin_joint = RigidJoint(
            "shoulder", violin, Location((1, 0, 0), (0, 45, 0))
        )
        self.shoulder.violin_joint.connect_to(violin_joint)
        self.assertEqual(violin_joint.location, self.shoulder.violin_joint.location)
        violin.locate(Location((100, 0, 0), (0, 0, 90)))
        violin_joint.connect_to(self.shoulder.violin_joint)
        self.assertEqual(violin_joint.location, self.shoulder.violin_joint.location)
        self.assert_center(
            self.shoulder.reference, tuple(self.shoulder.assembly.center())
        )

    def test_nested_assembly_tools_use_world_coordinates(self) -> None:
        self.shoulder.assembly.locate(Location((10, 0, 0)))
        final = Compound(children=[self.shoulder.assembly])
        final.locate(Location((0, 100, 0), (0, 0, 90)))
        self.assert_center(self.shoulder.reference, (-21, 118, 33))
        self.assert_center(self.shoulder.extended, (-24, 115, 36))


if __name__ == "__main__":
    unittest.main()
