"""Smoke checks for assembly workflows; inspect evolving geometry in CAD previews."""

import unittest
from typing import assert_type

from build123d import Align, Box, Compound, Location, Plane, Pos, Rotation

from shoulder_rest.parts.contoured_rest import ContouredRestGeometry, ContouredRestParameters
from shoulder_rest.parts.leg.hinge_leg import HingeLegInstallation, build_hinge_leg
from shoulder_rest.parts.rest import Rest
from shoulder_rest.parts.shoulder.step_shoulder import load_shoulder_cast
from shoulder_rest.parts.simple_rest import SimpleRestGeometry, build_simple_rest
from shoulder_rest.parts.violin_outline.spline_violin_outline import build_violin_outline


class WorkflowTests(unittest.TestCase):
    def test_hinge_angle_on_positioned_body(self) -> None:
        for pose in (Location(), Location((20, -30, 40), (10, 20, 30))):
            for angle in (0, 15, -10):
                with self.subTest(pose=pose, angle=angle):
                    body = Box(50, 50, 12, align=(Align.CENTER, Align.CENTER, Align.MAX))
                    body.locate(pose)
                    mount = Location(Plane(origin=(0, 0, 0), z_dir=(0, 0, -1)))
                    installation = build_hinge_leg().install(body, at=mount)
                    assembly = Compound(children=[body])
                    leg = installation.attach_to(assembly, angle=angle)
                    self.assertEqual(
                        leg.global_location,
                        installation.tool.location * Rotation(angle, 0, 0),
                    )

    def test_contour_and_assemble_at_shoulder_pose(self) -> None:
        shoulder = load_shoulder_cast(
            cast_location=Location((0, 0, 0), (30, 30, -5)),
            violin_location=(
                Pos(-55, -87.5, 57.5) * Rotation(0, 0, 66) * Rotation(8, 0, 0)
                * Location((18, 2, 24), (0, -24, 0))
            ),
        )
        for parameters, pose in (
            (ContouredRestParameters(), Location()),
            (ContouredRestParameters(width=34, contact_depth=65,
                                     left_fraction=0.35, right_fraction=0.45),
             Location((20, -30, 40), (10, 20, 30))),
        ):
            with self.subTest(parameters=parameters):
                shoulder.assembly.locate(pose)
                violin = build_violin_outline()
                geometry = ContouredRestGeometry(violin, shoulder, parameters)
                self.assertTrue(geometry.part.is_valid)
                self.assertEqual(len(geometry.part.solids()), 1)
                self.assertLess((geometry.part & shoulder.extended).volume, 1e-5)
                # In this fit the cutter reaches the whole oversized bottom face.
                local_body = geometry.part.moved(geometry.part.location.inverse())
                self.assertGreater(local_body.bounding_box().min.Z,
                                   -parameters.contact_depth + 1)
                rest = Rest(geometry, build_hinge_leg())
                self.assertEqual(rest.violin_joint.location, violin.mount_joint.location)
                self.assertTrue(rest.assembly.is_valid)
                self.assertEqual(len(rest.part.solids()), 1)
                for installation in rest.installations:
                    leg = installation.attach_to(rest.assembly)
                    self.assertEqual(leg.global_location, installation.tool.location)

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
        assert_type(rest, Rest[HingeLegInstallation])
        assert_type(rest.left, HingeLegInstallation)
        assert_type(rest.right, HingeLegInstallation)
        assert_type(rest.installations, tuple[HingeLegInstallation, HingeLegInstallation])
        self.assertIs(rest.part, geometry.part)
        self.assertEqual(rest.assembly.children, (rest.part,))
        rest.left.attach_to(rest.assembly)
        rest.right.attach_to(rest.assembly)
        rest.position_on(violin)
        self.assertEqual(rest.violin_joint.location, violin.mount_joint.location)
        scene = Compound(children=[shoulder.assembly, violin.block, rest.assembly])
        self.assertTrue(scene.is_valid)

    def test_fit_assembled_rest_and_reposition(self) -> None:
        violin = build_violin_outline()
        rest = build_simple_rest(
            violin, build_hinge_leg(angular_range=(-30, 30)),
        )
        assert_type(rest, Rest[HingeLegInstallation])
        for pose in (Location(), Location((20, -30, 40), (10, 20, 30))):
            violin.block.locate(pose)
            rest.position_on(violin)
            self.assertEqual(rest.violin_joint.location, violin.mount_joint.location)
        self.assertTrue(rest.assembly.is_valid)
        scene = Compound(children=[rest.assembly])
        scene.locate(Location((5, 10, -15), (15, -20, 5)))
        body_pose = rest.part.global_location
        left = rest.left.attach_to(rest.assembly, angle=-20)
        right = rest.right.attach_to(rest.assembly, angle=15)
        housing = rest.left.attach_housing_to(rest.assembly)
        self.assertEqual(rest.part.global_location, body_pose)
        self.assertEqual(len(scene.solids()), 6)
        self.assertIs(left.parent, rest.assembly)
        self.assertIs(housing.parent, rest.assembly)
        self.assertEqual(
            left.global_location,
            rest.left.tool.location * Rotation(-20, 0, 0),
        )
        self.assertEqual(
            housing.global_location,
            rest.part.global_location * rest.left.local_placement,
        )
        with self.assertRaises(ValueError):
            rest.left.attach_to(rest.assembly, angle=31)
        scene.locate(Location((30, -10, 5), (-20, 5, 15)))
        self.assertEqual(
            left.global_location,
            housing.global_location * Rotation(-20, 0, 0),
        )
        self.assertEqual(right.global_location, rest.right.tool.location * Rotation(15, 0, 0))
        alternate = Compound(children=[Box(1, 1, 1)])
        alternate.locate(Location((60, 20, -40), (5, 30, -10)))
        another = rest.left.attach_to(alternate, angle=10)
        another_housing = rest.left.attach_housing_to(alternate)
        self.assertIsNot(another, left)
        self.assertEqual(another.global_location, rest.left.tool.location * Rotation(10, 0, 0))
        self.assertEqual(another_housing.global_location, housing.global_location)


if __name__ == "__main__":
    unittest.main()
