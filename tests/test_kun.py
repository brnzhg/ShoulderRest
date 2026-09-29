"""Kun profiles can be placed and extruded independently of the hinge leg."""

from dataclasses import replace
import unittest

from build123d import BuildSketch, Location, Locations, Solid, Vector, insert

from shoulder_rest.parts.kun import KunParameters, nut_slot_face, screw_hole_face


class KunProfileTests(unittest.TestCase):
    def test_nut_slot_in_its_own_coordinate_frame(self) -> None:
        p = KunParameters(nut_slot_width=9, nut_slot_height=4)
        face = nut_slot_face(p)
        self.assertEqual(face.bounding_box().size, Vector(0, 9, 4))
        self.assertLess(face.center().length, 1e-7)
        tool = Solid.extrude(face.moved(Location((-7, 10, 20))), (14, 0, 0))
        self.assertTrue(tool.is_valid)
        self.assertAlmostEqual(tool.volume, 14 * 9 * 4)
        self.assertTrue(tool.is_inside((0, 10, 20)))

    def test_screw_opening_and_independent_faces(self) -> None:
        face = screw_hole_face()
        tool = Solid.extrude(face, (0, 0, 10))
        self.assertTrue(tool.is_valid)
        self.assertTrue(tool.is_inside((0, 0, 5)))
        self.assertFalse(tool.is_inside((2, 0, 5)))
        self.assertTrue(tool.is_inside((-2, 0, 5)))
        face.move(Location((100, 0, 0)))
        self.assertAlmostEqual(screw_hole_face().bounding_box().min.X, -2.1)

    def test_invalid_profiles(self) -> None:
        for changes in (
            {"nut_slot_height": 0}, {"screw_circle_offset": 2},
            {"screw_tangent_angle": 90}, {"screw_roof_extension": 3},
            {"screw_diameter": float("nan")},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(KunParameters(), **changes)

    def test_profiles_are_private_and_placement_is_applied_once(self) -> None:
        expected = screw_hole_face()
        with BuildSketch() as caller:
            with Locations((10, 20)):
                screw = screw_hole_face()
                nut = nut_slot_face()
                self.assertEqual(len(caller.faces()), 0)
                self.assertLess(nut.center().length, 1e-7)
                self.assertEqual(screw.bounding_box().min, expected.bounding_box().min)
                insert(screw)
        self.assertEqual(
            caller.sketch.bounding_box().min,
            expected.bounding_box().min + Vector(10, 20, 0),
        )


if __name__ == "__main__":
    unittest.main()
