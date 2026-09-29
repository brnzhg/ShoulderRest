"""Check the procedural leg against the source solid and its functional features."""

from dataclasses import replace
from math import pi
from pathlib import Path
import unittest

from build123d import Box, BuildPart, Compound, Axis, Location, Locations, Part, RigidJoint, Solid, Vector, import_step

from shoulder_rest.parts.kun import KunParameters
from shoulder_rest.parts.leg import CavityParameters, LegParameters, RodParameters, build_hinge_leg


class HingeLegTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.leg = build_hinge_leg().part

    def test_matches_onshape_solid(self) -> None:
        path = Path(__file__).resolve().parents[1] / "assets/leg/onshape_leg.step"
        reference = import_step(path)
        self.assertTrue(self.leg.is_valid)
        self.assertEqual(len(self.leg.solids()), 1)
        self.assertAlmostEqual(self.leg.volume, reference.volume, places=6)
        # Equal volume alone would miss misplaced material or holes.
        self.assertLess(self.leg.cut(reference).volume, 1e-6)
        self.assertLess(reference.cut(self.leg).volume, 1e-6)

    def test_clearances_and_nut_retaining_walls(self) -> None:
        leg = self.leg
        y = leg.parameters.screw_y
        for point in ((0, 0, 0), (0, y, 0), (0, y, 7.5), (5.9, y, 4.8)):
            with self.subTest(void=point):
                self.assertFalse(leg.is_inside(point))
        for point in ((0, 1.5, 0), (4, y, 0), (4, y, 7.5)):
            with self.subTest(wall=point):
                self.assertTrue(leg.is_inside(point))
        seat = leg.tags["nut_floor"][0]
        roof = leg.tags["nut_roof"][0]
        self.assertAlmostEqual(roof.center().Z - seat.center().Z, 3.4)
        self.assertAlmostEqual(seat.bounding_box().size.Y, 8.65)

    def test_named_faces_and_joints_follow_placement(self) -> None:
        tags = self.leg.tags
        self.assertEqual(
            {name: len(faces) for name, faces in tags.items()},
            {"rod_bore": 1, "nut_floor": 1, "nut_roof": 1, "screw_passage": 16, "side_faces": 2},
        )
        placement = Location((10, -20, 30), (20, 30, 40))
        moved = self.leg.moved(placement)
        for name, faces in tags.items():
            for original, actual in zip(faces, moved.tags[name]):
                self.assertLess((original.moved(placement).center() - actual.center()).length, 1e-6)
                self.assertEqual(actual.label, name)
        for name, joint in moved.joints.items():
            self.assertIs(joint.parent, moved)
            self.assertEqual(joint.location, placement * self.leg.joints[name].location)
        self.assertLess((self.leg.joints["rod"].location.z_axis.direction - Vector(1, 0, 0)).length, 1e-6)

    def test_parameter_variants(self) -> None:
        for changes in (
            {"rod_bore_clearance": 0.0},
            {"width": 14, "kun": KunParameters(nut_slot_width=9.0, nut_slot_height=4.0)},
            {"edge_chamfer": 0},
        ):
            with self.subTest(changes=changes):
                leg = build_hinge_leg(replace(LegParameters(), **changes)).part
                self.assertTrue(leg.is_valid)
                self.assertEqual(len(leg.solids()), 1)
                self.assertTrue(all(leg.tags.values()))
                self.assertAlmostEqual(leg.bounding_box().size.X, leg.parameters.width, places=5)
                self.assertAlmostEqual(
                    leg.tags["rod_bore"][0].bounding_box().size.Y,
                    leg.parameters.rod_hole_diameter, places=5,
                )

    def test_invalid_parameters(self) -> None:
        for changes in (
            {"width": 0}, {"width": float("nan")}, {"rod_bore_clearance": 8},
            {"edge_chamfer": 3}, {"rod": RodParameters(length=10)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                build_hinge_leg(replace(LegParameters(), **changes))

    def test_cavity_clears_lower_body_when_shared_profile_changes(self) -> None:
        for p in (
            LegParameters(),
            LegParameters(rear_relief_angle=35, nose_radius=1.2, rod_house_length=7),
        ):
            for c in (
                CavityParameters(clearance=0, bottom_clearance=0),
                CavityParameters(clearance=0.15, bottom_clearance=0.25),
            ):
                with self.subTest(parameters=p, cavity=c):
                    leg = build_hinge_leg(p, c)
                    below_nut_housing = Solid.make_box(p.width + 2, 100, 100).moved(
                        Location((-p.width / 2 - 1, -50, p.rod_half - 100))
                    )
                    lower_body = leg.part & below_nut_housing
                    self.assertGreater(lower_body.volume, 0)
                    self.assertLess(lower_body.cut(leg.tool).volume, 1e-6)
                    self.assertGreater(leg.part.cut(leg.tool).volume, 0)
                    self.assertTrue(leg.tool.is_valid)
                    self.assertAlmostEqual(leg.tool.bounding_box().max.Z, p.rod_half + c.clearance)


class LegInstallationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.template = build_hinge_leg()

    def test_tool_matches_source_and_guide_contains_source(self) -> None:
        assets = Path(__file__).resolve().parents[1] / "assets/leg"
        tool = self.template.tool
        reference = import_step(assets / "onshape_leg_tool.step")
        self.assertLess(tool.cut(reference).volume, 1e-6)
        self.assertLess(reference.cut(tool).volume, 1e-6)
        housing = import_step(assets / "onshape_housing.step")
        guide = self.template.housing
        self.assertLess(housing.cut(guide).volume, 1e-6)
        self.assertAlmostEqual(guide.cut(housing).volume, 183.3553079144806)
        self.assertIsNone(guide.intersect(tool))

    def test_assembly_contains_printed_leg_and_actual_metal_stock(self) -> None:
        template = self.template
        self.assertEqual(len(template.assembly.children), 2)
        self.assertIs(template.part.parent, template.assembly)
        self.assertIs(template.rod.parent, template.assembly)
        self.assertEqual(template.rod.bounding_box().size, Vector(20, 2, 2))
        self.assertAlmostEqual(template.rod.volume, 20 * pi)
        self.assertIsNone(template.part.intersect(template.rod))
        self.assertIs(template.mount_joint.parent, template.assembly)

    def test_template_build_does_not_modify_or_inherit_caller_placement(self) -> None:
        with BuildPart() as caller:
            Box(1, 1, 1)
            with Locations((100, 200, 300)):
                leg = build_hinge_leg()
        self.assertAlmostEqual(caller.part.volume, 1)
        self.assertEqual(leg.mount_joint.location, self.template.mount_joint.location)
        for actual, expected in (
            (leg.part, self.template.part), (leg.tool, self.template.tool),
            (leg.housing, self.template.housing), (leg.rod, self.template.rod),
        ):
            self.assertLess(actual.cut(expected).volume, 1e-6)
            self.assertLess(expected.cut(actual).volume, 1e-6)

    def test_changed_stock_updates_bore_slot_length_and_housing(self) -> None:
        leg = build_hinge_leg(LegParameters(rod=RodParameters(diameter=3, length=24)))
        self.assertEqual(leg.rod.bounding_box().size, Vector(24, 3, 3))
        self.assertAlmostEqual(leg.part.tags["rod_bore"][0].bounding_box().size.Y, 3.2)
        self.assertAlmostEqual(leg.tool.bounding_box().size.X, 25)
        self.assertAlmostEqual(leg.housing.bounding_box().size.X, 27)
        self.assertTrue(leg.tool.is_inside((10, 1, 1.5)))
        self.assertFalse(self.template.tool.is_inside((10, 1, 1.5)))
        self.assertIsNone(leg.part.intersect(leg.rod))

    def test_rod_and_printed_child_follow_installed_and_nested_assembly(self) -> None:
        rest = Part([Solid.make_box(40, 50, 12).moved(Location((-20, -15, -8)))])
        mount = RigidJoint("mount", rest, self.template.mount_joint.location)
        installed = self.template.install(mount)
        installed.rest.joints["leg"].connect_to(installed.rod_joint, angle=25)
        final = Compound(children=[installed.rest, installed.leg])
        final.locate(Location((12, 34, 56), (10, 20, 30)))
        for original, child in zip(self.template.assembly.children, installed.leg.children):
            self.assertIsNot(child, original)
            self.assertIs(child.parent, installed.leg)
            self.assertEqual(child.global_location, final.location * installed.leg.location)
        self.assertEqual(self.template.assembly.location, Location())
        self.assertIs(installed.rod_joint.parent, installed.leg)

    def test_invalid_stock_and_clearances(self) -> None:
        for values in ({"diameter": 0}, {"length": -1}, {"diameter": float("nan")}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                RodParameters(**values)
        with self.assertRaises(ValueError):
            CavityParameters(rod_slot_clearance=-0.1)

    def test_install_rotated_rest_and_rotate_leg(self) -> None:
        placement = Location((25, -10, 31), (21, 38, 17))
        rest = Part([Solid.make_box(40, 50, 12).moved(Location((-20, -15, -8)))]).locate(placement)
        rest.label = "Rest"
        mount = RigidJoint("leg_mount", rest, placement * self.template.mount_joint.location)
        keep = RigidJoint("violin", rest, placement * Location((3, 4, 5), (10, 20, 30)))
        original_volume = rest.volume
        result = self.template.install(mount, joint_label="left_leg")
        self.assertEqual(rest.volume, original_volume)
        self.assertNotIn("left_leg", rest.joints)
        self.assertEqual(self.template.assembly.location, Location())
        self.assertEqual(result.rest.location, placement)
        self.assertEqual(result.rest.joints["violin"].location, keep.location)
        self.assertIs(result.rest.joints["violin"].parent, result.rest)
        self.assertIsNot(result.rest.joints["violin"], keep)
        self.assertAlmostEqual(original_volume - result.rest.volume, result.tool.volume, places=5)
        self.assertEqual(result.leg.joints["mount"].location, mount.location)
        hinge = result.rest.joints["left_leg"]
        tool_before = result.tool.bounding_box()
        for angle in (0, 25, -20):
            hinge.connect_to(result.leg.joints["rod"], angle=angle)
            expected = self.template.assembly.rotate(Axis.X, angle).moved(placement)
            self.assertLess(expected.cut(result.leg).volume, 1e-6)
            self.assertLess(result.leg.cut(expected).volume, 1e-6)
        self.assertEqual(result.tool.bounding_box().min, tool_before.min)
        self.assertEqual(result.tool.bounding_box().max, tool_before.max)

    def test_arbitrary_mount_orientation_and_later_rest_placement(self) -> None:
        rest_pose = Location((8, 10, 20), (10, 30, 50))
        leg_pose = Location((0, 0, 0), (12, 24, 36))
        rest = Part([Solid.make_box(70, 70, 70).moved(Location((-35, -35, -35)))]).locate(rest_pose)
        mount = RigidJoint("mount", rest, rest_pose * leg_pose * self.template.mount_joint.location)
        result = self.template.install(mount)
        new_pose = Location((-50, 12, 80), (-20, 35, 5))
        result.rest.locate(new_pose)
        for angle in (0, 15, -30):
            result.rest.joints["leg"].connect_to(result.leg.joints["rod"], angle=angle)
            expected = self.template.assembly.rotate(Axis.X, angle).moved(new_pose * leg_pose)
            self.assertLess(expected.cut(result.leg).volume, 1e-6)
            self.assertLess(result.leg.cut(expected).volume, 1e-6)

    def test_repeated_install_preserves_earlier_hinge(self) -> None:
        rest = Part([Solid.make_box(90, 60, 12).moved(Location((-45, -20, -8)))])
        left_pose = Location((-22, 0, 0), (0, 0, 10))
        right_pose = Location((22, 0, 0), (0, 0, -10))
        left_mount = RigidJoint("left_mount", rest, left_pose * self.template.mount_joint.location)
        RigidJoint("right_mount", rest, right_pose * self.template.mount_joint.location)
        first = self.template.install(left_mount, joint_label="left_leg")
        second = self.template.install(first.rest.joints["right_mount"], joint_label="right_leg")
        self.assertIs(second.rest.joints["left_leg"].parent, second.rest)
        self.assertEqual(second.rest.joints["left_leg"].location, first.rest.joints["left_leg"].location)
        for label, leg, pose in (("left_leg", first.leg, left_pose), ("right_leg", second.leg, right_pose)):
            second.rest.joints[label].connect_to(leg.joints["rod"], angle=0)
            self.assertEqual(leg.location, pose)
        self.assertLess(second.rest.volume, first.rest.volume)

    def test_tools_follow_template_placement_as_independent_snapshots(self) -> None:
        leg = build_hinge_leg()
        original = leg.tool
        pose = Location((10, 20, 30), (20, 30, 40))
        leg.assembly.locate(pose)
        tool = leg.tool
        self.assertLess(tool.cut(original.moved(pose)).volume, 1e-6)
        tool.move(Location((100, 0, 0)))
        self.assertLess(leg.tool.cut(original.moved(pose)).volume, 1e-6)

    def test_invalid_installation_does_not_change_input(self) -> None:
        rest = Part([Solid.make_box(30, 40, 10).moved(Location((-15, -10, -5)))])
        mount = RigidJoint("mount", rest, self.template.mount_joint.location)
        for kwargs in ({"joint_label": "mount"}, {"angular_range": (10, 90)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.template.install(mount, **kwargs)
        outside = RigidJoint("outside", rest, Location((1000, 0, 0)))
        with self.assertRaisesRegex(ValueError, "does not intersect"):
            self.template.install(outside)
        self.assertEqual(set(rest.joints), {"mount", "outside"})


if __name__ == "__main__":
    unittest.main()
