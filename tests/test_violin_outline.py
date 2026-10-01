"""Geometry checks for violin outlines and parametric attachment guides."""

import unittest

from build123d import Box, Location, Polyline, RigidJoint, Vector

from shoulder_rest.parts.violin_outline import ViolinOutline
from shoulder_rest.parts.violin_outline.spline_violin_outline import (
    SplineViolinOutline,
    build_violin_outline,
)

RIGHT_OUTLINE_POINTS = (
    (87.175, -56.570), (91.220, -49.3), (96.473, -37.724),
    (101.728, -15.76), (102.605, 0.0), (101.12, 15.165),
    (94.784, 32.802), (84.79, 46.767), (65.910, 61.558),
    (43.630, 69.918), (18.865, 73.536),
)


class ViolinOutlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.violin: ViolinOutline = build_violin_outline(attachment_offset=3)

    def assert_vector(self, actual: Vector, expected: Vector) -> None:
        self.assertLess((actual - expected).length, 1e-5)

    def test_interpolation_mirroring_and_curve_direction(self) -> None:
        right, left = self.violin.right, self.violin.left
        for x, y in RIGHT_OUTLINE_POINTS:
            self.assertLess(right.distance_to((x, y, 0)), 1e-5)
            self.assertLess(left.distance_to((-x, y, 0)), 1e-5)
        for curve in (right, left, self.violin.left_attachment, self.violin.right_attachment):
            self.assertTrue(curve.is_valid)
            self.assertFalse(curve.is_closed)
            self.assertLess((curve @ 0).Y, (curve @ 1).Y)
        for fraction in (0, 0.1, 0.25, 0.5, 0.8, 1):
            r = self.violin.attachment_point("right", fraction)
            l = self.violin.attachment_point("left", fraction)
            self.assert_vector(l, Vector(-r.X, r.Y, 0))

    def test_offsets_are_normal_distances_inside_the_block(self) -> None:
        for side in ("left", "right"):
            original = getattr(self.violin, side)
            for index in range(21):
                point = self.violin.attachment_point(side, index / 20)
                self.assertAlmostEqual(original.distance_to(point), 3, places=5)
                self.assertTrue(self.violin.block.is_inside(point + Vector(0, 0, 1)))

    def test_block_uses_original_outline_and_configurable_thickness(self) -> None:
        block = self.violin.block
        self.assertTrue(block.is_valid)
        self.assertEqual(len(block.solids()), 1)
        self.assertAlmostEqual(block.bounding_box().min.Z, 0, places=5)
        self.assertAlmostEqual(block.bounding_box().max.Z, 38, places=5)
        half = SplineViolinOutline(RIGHT_OUTLINE_POINTS, attachment_offset=0, block_thickness=19)
        self.assertAlmostEqual(block.volume, 2 * half.block.volume, places=4)
        for t in (0, 0.25, 0.5, 0.75, 1):
            self.assert_vector(half.right @ t, half.right_attachment @ t)
        self.assertIsInstance(block.joints["shoulder"], RigidJoint)
        self.assertIs(self.violin.shoulder_joint, block.joints["shoulder"])
        self.assertIs(self.violin.shoulder_joint.parent, block)
        self.assertEqual(block.joints["shoulder"].location, self.violin.mount_location)

    def test_polyline_endpoints_follow_parameter_changes(self) -> None:
        for offset in (1.0, 5.0):
            violin = build_violin_outline(attachment_offset=offset)
            left = violin.attachment_point("left", 0.2)
            right = violin.attachment_point("right", 0.65)
            guide = Polyline(left, (0, 10), right)
            self.assert_vector(guide @ 0, left)
            self.assert_vector(guide @ 1, right)
            self.assertLess(violin.left_attachment.distance_to(guide @ 0), 1e-5)
            self.assertLess(violin.right_attachment.distance_to(guide @ 1), 1e-5)

    def test_curves_are_independent_of_block_placement_and_returned_copies(self) -> None:
        violin = build_violin_outline()
        point = violin.attachment_point("left", 0.4)
        placement = Location((10, 20, 30), (20, 30, 40))
        violin.block.locate(placement)
        self.assertEqual(
            violin.shoulder_joint.location, placement * violin.mount_location
        )
        self.assert_vector(violin.attachment_point("left", 0.4), point)
        curve = violin.left_attachment
        curve.move(placement)
        self.assert_vector(violin.left_attachment @ 0.4, point)

    def test_alternative_tracing(self) -> None:
        violin = SplineViolinOutline([(10, -10), (15, 0), (10, 10)], attachment_offset=1)
        self.assertTrue(violin.block.is_valid)
        self.assertLess(violin.right.distance_to((15, 0, 0)), 1e-5)

    def test_mount_uses_top_midpoint_and_stays_in_modeling_frame(self) -> None:
        violin = build_violin_outline()
        self.assertEqual(violin.mount_location, Location((0, 73.536, 0)))
        violin.block.move(Location((10, 20, 30), (20, 30, 40)))
        self.assertEqual(violin.mount_location, Location((0, 73.536, 0)))
        other = SplineViolinOutline([(10, -10), (15, 0), (10, 10)], attachment_offset=1)
        self.assertEqual(other.mount_location, Location((0, 10, 0)))

    def test_rest_joint_has_local_offset_even_on_an_already_positioned_part(self) -> None:
        rest = Box(20, 30, 5).moved(Location((10, 20, 30), (10, 20, 30)))
        offset = Location((0, 0, 12), (5, 0, 0))
        joint = self.violin.add_mount_joint(rest, offset=offset)
        self.assertIs(rest.joints["violin"], joint)
        self.assertEqual(joint.relative_location, self.violin.mount_location * offset)
        self.assertEqual(joint.location, rest.location * self.violin.mount_location * offset)
        with self.assertRaises(ValueError):
            self.violin.add_mount_joint(rest)

    def test_shoulder_violin_and_rest_share_mount_with_leg_height(self) -> None:
        violin = build_violin_outline()
        # Stand-in for the shoulder's attachment; use a nontrivial orientation.
        shoulder = Box(1, 1, 1)
        shoulder_joint = RigidJoint(
            "violin", shoulder, Location((40, -30, 70), (20, -30, 40))
        )
        shoulder_joint.connect_to(violin.shoulder_joint)
        self.assertEqual(violin.shoulder_joint.location, shoulder_joint.location)
        for height in (0, 12):
            with self.subTest(height=height):
                rest = Box(20, 30, 5)
                joint = violin.add_mount_joint(rest, offset=Location((0, 0, height)))
                violin.shoulder_joint.connect_to(joint)
                self.assertEqual(joint.location, shoulder_joint.location)
                self.assertEqual(
                    rest.location, violin.block.location * Location((0, 0, -height))
                )
                # Connecting directly to the shoulder gives the same rest pose.
                expected = rest.location
                rest.locate(Location())
                shoulder_joint.connect_to(joint)
                self.assertEqual(rest.location, expected)

    def test_invalid_dimensions_and_tracing(self) -> None:
        for offset in (-1, float("nan"), float("inf"), 100):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                build_violin_outline(attachment_offset=offset)
        for points in ([], [(1, 0)], [(1, 0), (1, 0)], [(-1, 0), (1, 1)],
                       [(1, 1), (2, 0)], [(float("nan"), 0), (1, 1)]):
            with self.subTest(points=points), self.assertRaises(ValueError):
                SplineViolinOutline(points)
        for fraction in (-0.1, 1.1, float("nan"), float("inf")):
            with self.subTest(fraction=fraction), self.assertRaises(ValueError):
                self.violin.attachment_point("left", fraction)
        with self.assertRaises(ValueError):
            self.violin.attachment_point("center", 0.5)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
