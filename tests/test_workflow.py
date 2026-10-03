"""Smoke checks for assembly workflows; inspect evolving geometry in CAD previews."""

import unittest

from build123d import Align, Box, Compound, Location, Plane, Pos, Rotation

from shoulder_rest.parts.contoured_rest import ContouredRestGeometry, ContouredRestParameters
from shoulder_rest.parts.leg.hinge_leg import build_hinge_leg
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
                    installation = build_hinge_leg(angle=angle).install(body, at=mount)
                    installation.attach_to(body)
                    self.assertEqual(
                        installation.leg.location,
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
                    self.assertEqual(installation.leg.location, installation.tool.location)

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
        self.assertIs(rest.part, geometry.part)
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
