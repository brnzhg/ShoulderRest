"""Construction and installation smoke checks for the rod bumps and adjustable nose recess."""

import unittest

from build123d import Align, Box, Compound, Location, Plane, Rotation

from shoulder_rest.parts.leg.hinge_leg import (
    CavityParameters, RodRetentionParameters, build_hinge_leg,
)


class HingeSnapTests(unittest.TestCase):
    def test_nose_clearance_enlarges_only_the_recess(self) -> None:
        for extra in (0.0, 0.2):
            with self.subTest(extra=extra):
                cavity = CavityParameters(nose_clearance=extra)
                leg = build_hinge_leg(cavity=cavity)
                p = leg.part.parameters
                self.assertTrue(leg.tool.is_valid)
                self.assertEqual(len(leg.housing.solids()), 1)
                self.assertAlmostEqual(leg.tool.bounding_box().min.Y,
                                       -p.nose_swing_radius - extra - cavity.clearance)
                self.assertAlmostEqual(leg.tool.bounding_box().min.Z,
                                       -p.nose_swing_radius - extra - cavity.clearance - cavity.bottom_clearance)
                self.assertAlmostEqual(leg.housing.bounding_box().min.Z,
                                       -p.rod_house_half - cavity.housing_wall)
                # The rear floor remains above the locally deepened nose recess.
                rear_floor = -p.rod_house_half - cavity.clearance - cavity.bottom_clearance
                self.assertTrue(leg.housing.is_inside((0, p.screw_y, rear_floor - 0.05)))

    def test_retention_installs_and_follows_body(self) -> None:
        leg = build_hinge_leg(
            cavity=CavityParameters(nose_clearance=0.2),
            rod_retention=RodRetentionParameters(), angular_range=(0, 90),
        )
        body = Box(50, 50, 12, align=(Align.CENTER, Align.CENTER, Align.MAX))
        body.locate(Location((20, -30, 40), (10, 20, 30)))
        volume = body.volume
        site = leg.install(body, at=Location(Plane(origin=(0, 0, 0), z_dir=(0, 0, -1))))
        self.assertIs(site.body, body)
        self.assertLess(body.volume, volume)
        self.assertTrue(body.is_valid)
        self.assertEqual(len(body.solids()), 1)
        assembly = Compound(children=[body])
        for angle in (0, 90):
            attached = site.attach_to(assembly, angle=angle)
            self.assertEqual(attached.global_location, site.tool.location * Rotation(angle, 0, 0))
        assembly.locate(Location((10, 20, 30), (15, 25, 35)))
        self.assertEqual(attached.global_location, site.tool.location * Rotation(90, 0, 0))

    def test_bumps_require_receiving_material(self) -> None:
        leg = build_hinge_leg(rod_retention=RodRetentionParameters())
        body = Box(14, 50, 12, align=(Align.CENTER, Align.CENTER, Align.MAX))
        volume = body.volume
        with self.assertRaisesRegex(ValueError, "retention bumps"):
            leg.install(body, at=Location(Plane(origin=(0, 0, 0), z_dir=(0, 0, -1))))
        self.assertAlmostEqual(body.volume, volume)
        self.assertEqual(body.joints, {})

    def test_reject_impossible_settings(self) -> None:
        with self.assertRaises(ValueError):
            RodRetentionParameters(interference=float("nan"))
        for extra in (-0.1, float("nan")):
            with self.assertRaises(ValueError):
                CavityParameters(nose_clearance=extra)
        with self.assertRaisesRegex(ValueError, "embedded"):
            build_hinge_leg(rod_retention=RodRetentionParameters(interference=0.5))
        with self.assertRaisesRegex(ValueError, "Housing wall"):
            build_hinge_leg(cavity=CavityParameters(nose_clearance=2))


if __name__ == "__main__":
    unittest.main()
