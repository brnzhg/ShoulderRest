"""Smoke checks for the independently rounded W blank."""

from dataclasses import replace
from math import cos, radians, sin
import unittest

from build123d import Location, Plane, Pos, Rotation, Vector

from shoulder_rest.parts.leg.hinge_leg import build_hinge_leg
from shoulder_rest.parts.rest import Rest
from shoulder_rest.parts.shoulder.step_shoulder import load_shoulder_cast
from shoulder_rest.parts.violin_outline.spline_violin_outline import build_violin_outline
from shoulder_rest.parts.wrest import (
    WRestGeometry, WRestParameters, _oversized_blank, _rounded_centerline,
)


class WBlankTests(unittest.TestCase):
    def test_stroke_angles_share_the_leftward_reference(self) -> None:
        parameters = replace(
            WRestParameters(), w_angle1=0, w_angle2=30, w_angle3=-20,
            first_radius=0, second_radius=0, third_radius=0,
        )
        centerline = _rounded_centerline(
            Vector(-95, 12), Vector(95, 12), parameters,
        )

        for edge, angle in zip(centerline.edges()[:3], (0, 30, -20)):
            with self.subTest(angle=angle):
                direction = radians(angle)
                expected = Vector(-cos(direction), -sin(direction), 0)
                self.assertAlmostEqual(edge.tangent_at(0).dot(expected), 1)

    def test_default_and_individual_corner_radii(self) -> None:
        left = Vector(-95.5555, 12.2806)
        right = Vector(95.5555, 12.2806)
        parameters = WRestParameters()
        baseline = _oversized_blank(left, right, parameters)
        self.assertTrue(baseline.is_valid)
        self.assertEqual(len(baseline.solids()), 1)

        for change in (
            {"first_radius": 2},
            {"second_radius": 3},
            {"third_radius": 1},
        ):
            with self.subTest(change=change):
                blank = _oversized_blank(left, right, replace(parameters, **change))
                self.assertTrue(blank.is_valid)
                self.assertEqual(len(blank.solids()), 1)
                self.assertNotAlmostEqual(blank.volume, baseline.volume, places=4)

    def test_extensions_follow_outer_strokes(self) -> None:
        left = Vector(-95.5555, 12.2806)
        right = Vector(95.5555, 12.2806)
        parameters = WRestParameters()
        centerline = _rounded_centerline(left, right, parameters)

        right_extension = right - centerline.position_at(0)
        left_extension = centerline.position_at(1) - left
        self.assertAlmostEqual(right_extension.length, parameters.right_extend)
        self.assertAlmostEqual(left_extension.length, parameters.left_extend)
        self.assertAlmostEqual(right_extension.normalized().dot(centerline.tangent_at(0)), 1)
        self.assertAlmostEqual(left_extension.normalized().dot(centerline.tangent_at(1)), 1)

    def test_mounts_follow_their_local_strokes(self) -> None:
        shoulder = load_shoulder_cast(
            cast_location=Location((0, 0, 0), (30, 30, -5)),
            violin_location=(
                Pos(-55, -87.5, 57.5) * Rotation(0, 0, 66) * Rotation(8, 0, 0)
                * Location((18, 2, 24), (0, -24, 0))
            ),
        )
        violin = build_violin_outline()
        geometry = WRestGeometry(violin, shoulder)
        left = violin.attachment_point("left", 0.4)
        right = violin.attachment_point("right", 0.4)
        centerline = _rounded_centerline(left, right, geometry.parameters)

        for joint, point, outward in (
            (geometry.left_mount_joint, left, centerline.tangent_at(1)),
            (geometry.right_mount_joint, right, -centerline.tangent_at(0)),
        ):
            with self.subTest(joint=joint.label):
                frame = Plane(joint.relative_location)
                expected_x = Vector(outward.Y, -outward.X, 0)
                self.assertIs(joint.parent, geometry.part)
                self.assertLess((frame.origin - point).length, 1e-6)
                self.assertAlmostEqual(frame.x_dir.dot(expected_x), 1)
                self.assertAlmostEqual(frame.z_dir.Z, -1)

        self.assertLess(Plane(geometry.left_mount_joint.relative_location).x_dir.dot(
            Plane(geometry.right_mount_joint.relative_location).x_dir), 0)
        rest = Rest(geometry, build_hinge_leg())
        self.assertTrue(rest.part.is_valid)
        self.assertEqual(len(rest.part.solids()), 1)


if __name__ == "__main__":
    unittest.main()
