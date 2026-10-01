"""Check shared rest construction, geometry, ownership, and assembly placement."""

from dataclasses import dataclass, replace
from copy import deepcopy
import unittest

from build123d import (
    Axis, Box, BuildPart, Compound, Location, Locations, Part, Plane,
    RevoluteJoint, RigidJoint, Solid, Vector,
)

from shoulder_rest.parts.leg.hinge_leg import HingeLegInstallation, LegParameters, build_hinge_leg
from shoulder_rest.parts.rest import Rest
from shoulder_rest.parts.rest_geometry import RestGeometry
from shoulder_rest.parts.simple_rest import SimpleRestGeometry, SimpleRestParameters, build_simple_rest
from shoulder_rest.parts.violin_outline.spline_violin_outline import build_violin_outline


@dataclass(frozen=True)
class GeometryFixture:
    """Structural RestGeometry implementation with implementation-specific labels."""

    part: Part | Solid
    left_mount_joint: RigidJoint
    right_mount_joint: RigidJoint
    violin_joint: RigidJoint


@dataclass
class DirectInstallation:
    """Test implementation that attaches by placement and creates no body joint."""

    rest: Part | Solid
    leg: Compound
    tool: Part
    housing: Part
    local_mount: Location
    attached_body: Part | Solid | None = None

    def attach_to(self, final_body: Part | Solid) -> None:
        self.attached_body = final_body
        self.leg.locate(final_body.location * self.local_mount)


class DirectLeg:
    """Simple peg fixture satisfying Leg without hinge or rod interfaces."""

    def __init__(self):
        self.part = Part([Solid.make_cylinder(1.5, 4)])
        self.assembly = Compound(children=[self.part])
        self.mount_joint = RigidJoint("mount", self.assembly, Location())

    @property
    def tool(self) -> Part:
        return Part([Solid.make_cylinder(2, 4)]).moved(self.assembly.location)

    @property
    def housing(self) -> Part:
        return Part([Solid.make_cylinder(3, 4) - Solid.make_cylinder(2, 4)]).moved(self.assembly.location)

    def install(self, mount: RigidJoint, *, joint_label: str = "leg") -> DirectInstallation:
        source = mount.parent
        tool = self.tool.moved(mount.location)
        rest = (
            source.located(Location()) - tool.moved(source.location.inverse())
        ).moved(source.location)
        return DirectInstallation(
            rest, deepcopy(self.assembly), tool, self.housing.moved(mount.location),
            mount.relative_location,
        )


class RestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.violin = build_violin_outline()
        cls.leg = build_hinge_leg()

    def test_complete_rest_and_parameter_variations(self) -> None:
        for p in (
            SimpleRestParameters(),
            SimpleRestParameters(width=48, thickness=15, left_fraction=0.1, right_fraction=0.8, violin_gap=20),
        ):
            with self.subTest(parameters=p):
                rest = build_simple_rest(self.violin, self.leg, p)
                self.assertIsInstance(rest, Rest)
                self.assertTrue(rest.part.is_valid)
                self.assertEqual(len(rest.part.solids()), 1)
                self.assertAlmostEqual(rest.part.bounding_box().min.Z, -p.thickness)
                self.assertAlmostEqual(rest.part.bounding_box().max.Z, 0)
                self.assertEqual(len(rest.assembly.children), 3)
                self.assertIs(rest.assembly, rest.assembly)
                self.assertIs(rest.part.parent, rest.assembly)
                self.assertIs(rest.violin_joint.parent, rest.assembly)
                for side, fraction, mount in (
                    ("left", p.left_fraction, rest.left_mount_joint),
                    ("right", p.right_fraction, rest.right_mount_joint),
                ):
                    self.assertIsInstance(mount, RigidJoint)
                    self.assertIs(mount.parent, rest.part)
                    self.assertEqual(mount.location.position, self.violin.attachment_point(side, fraction))
                    self.assertEqual(mount.location.z_axis.direction, Vector(0, 0, -1))
                self.assertEqual(
                    rest.violin_joint.location,
                    self.violin.mount_location * Location((0, 0, p.violin_gap)),
                )
                for item in rest.installations:
                    self.assertIsInstance(item, HingeLegInstallation)
                    hinge = rest.part.joints[item.joint_label]
                    self.assertLess(item.housing.cut(rest.part).volume, 1e-6)
                    overlap = rest.part.intersect(item.tool)
                    self.assertTrue(overlap is None or overlap.volume < 1e-6)
                    self.assertIsInstance(hinge, RevoluteJoint)
                    self.assertIs(hinge.parent, rest.part)
                    self.assertIs(hinge.connected_to, item.rod_joint)
                    self.assertIs(item.leg.parent, rest.assembly)

    def test_angles_and_independent_legs(self) -> None:
        rest = build_simple_rest(
            self.violin, build_hinge_leg(angle=15), right_leg=build_hinge_leg(angle=-10),
        )
        for item, mount, angle in zip(
            rest.installations, (rest.left_mount_joint, rest.right_mount_joint), (15, -10),
        ):
            pose = mount.location * self.leg.mount_joint.relative_location.inverse()
            expected = self.leg.assembly.located(pose).rotate(
                Axis(item.rod_joint.location.position, mount.location.x_axis.direction), angle,
            )
            self.assertLess(item.leg.cut(expected).volume, 1e-6)
            self.assertLess(expected.cut(item.leg).volume, 1e-6)
            self.assertIsNot(item.leg, self.leg.assembly)
        self.assertIsNot(rest.installations[0].leg, rest.installations[1].leg)
        self.assertEqual(self.leg.assembly.location, Location())

    def test_repeated_positioning_moves_body_and_both_legs(self) -> None:
        violin = build_violin_outline()
        rest = build_simple_rest(violin, self.leg)
        assembly = rest.assembly
        child_locations = [child.location for child in assembly.children]
        for pose in (Location((20, -30, 40), (12, 23, 34)), Location((-20, 15, 8), (0, 40, 5))):
            violin.block.locate(pose)
            rest.position_on(violin)
            self.assertIs(rest.assembly, assembly)
            self.assertEqual(rest.violin_joint.location, violin.shoulder_joint.location)
            expected = pose * Location((0, 0, -12))
            self.assertEqual(assembly.location, expected)
            for child, local in zip(assembly.children, child_locations):
                self.assertEqual(child.location, local)
                self.assertEqual(child.global_location, expected * local)
        scene = Compound(children=[violin.block, rest.assembly])
        scene_pose = Location((100, 200, 300), (10, 20, 30))
        scene.locate(scene_pose)
        for child, local in zip(assembly.children, child_locations):
            self.assertEqual(child.global_location, scene_pose * expected * local)

    def test_private_builder(self) -> None:
        with BuildPart() as caller:
            Box(1, 1, 1)
            with Locations((100, 200, 300)):
                rest = build_simple_rest(self.violin, self.leg)
        expected = build_simple_rest(self.violin, self.leg)
        self.assertAlmostEqual(caller.part.volume, 1)
        self.assertLess(rest.part.cut(expected.part).volume, 1e-6)
        self.assertLess(expected.part.cut(rest.part).volume, 1e-6)
        self.assertEqual(rest.violin_joint.location, expected.violin_joint.location)
        for actual, original in zip(rest.installations, expected.installations):
            self.assertLess(actual.leg.cut(original.leg).volume, 1e-6)
            self.assertLess(original.leg.cut(actual.leg).volume, 1e-6)

    def test_positioned_contoured_geometry_preserves_frames_and_inputs(self) -> None:
        # Analytic shoulder cutter lets this test check contact independently of STEP data.
        pose = Location((5, 10, 15), (10, 20, 30))
        blank = Part([Solid.make_box(100, 60, 12).moved(Location((-50, -30, -12)))])
        shoulder_tool = Solid.make_sphere(20).moved(Location((0, 0, -26))).moved(pose)
        body = (blank - shoulder_tool.moved(pose.inverse())).moved(pose)
        self.assertLess(body.volume, blank.volume)
        self.assertTrue(body.is_valid)
        geometry: RestGeometry = GeometryFixture(
            body,
            RigidJoint("bass", body, pose * Location(Plane(origin=(-30, 0, 0), z_dir=(0, 0, -1)))),
            RigidJoint("treble", body, pose * Location(Plane(origin=(30, 0, 0), z_dir=(0, 0, -1)))),
            RigidJoint("instrument", body, pose * Location((0, 20, 10), (4, 8, 12))),
        )
        violin = build_violin_outline()
        # A geometry implementation may position reference parts using its own joint.
        geometry.violin_joint.connect_to(violin.shoulder_joint)
        original_volume = body.volume
        violin_pose = violin.block.location
        rest = Rest(geometry, build_hinge_leg(LegParameters(width=14)))
        self.assertEqual(body.volume, original_volume)
        self.assertEqual(body.location, pose)
        self.assertIsNone(body.parent)
        self.assertEqual(violin.block.location, violin_pose)
        self.assertIs(geometry.violin_joint.connected_to, violin.shoulder_joint)
        self.assertLess(rest.part.volume, original_volume)
        self.assertEqual(rest.part.global_location, pose)
        self.assertEqual(rest.violin_joint.location, geometry.violin_joint.location)
        self.assertIsNone(rest.part.joints["instrument"].connected_to)
        for actual, source in (
            (rest.left_mount_joint, geometry.left_mount_joint),
            (rest.right_mount_joint, geometry.right_mount_joint),
        ):
            self.assertIs(actual.parent, rest.part)
            self.assertIsNot(actual, source)
            self.assertEqual(actual.location, source.location)
        overlap = rest.part.intersect(shoulder_tool)
        self.assertTrue(overlap is None or overlap.volume < 1e-6)
        children_before = [child.global_location for child in rest.assembly.children]
        rest.position_on(violin)
        for child, before in zip(rest.assembly.children, children_before):
            self.assertEqual(child.global_location, before)
        self.assertEqual(rest.violin_joint.location, violin.shoulder_joint.location)

    def test_geometry_can_be_inspected_and_reused_before_leg_installation(self) -> None:
        geometry = SimpleRestGeometry(self.violin)
        self.assertIs(geometry.violin_joint.parent, geometry.part)
        self.assertIsNone(geometry.part.parent)
        volume = geometry.part.volume
        first = Rest(geometry, self.leg)
        second = Rest(geometry, build_hinge_leg(angle=20), right_leg=self.leg)
        self.assertEqual(geometry.part.volume, volume)
        self.assertEqual(set(geometry.part.joints), {"left_mount", "right_mount", "violin"})
        self.assertIsNone(geometry.part.parent)
        self.assertIsNot(first.part, second.part)
        self.assertIsNot(first.left_mount_joint, second.left_mount_joint)
        self.assertLess(first.part.cut(second.part).volume, 1e-6)
        self.assertLess(second.part.cut(first.part).volume, 1e-6)

    def test_saved_joint_references_follow_placement_and_copying(self) -> None:
        rest = build_simple_rest(self.violin, self.leg)
        copied = deepcopy(rest)
        body_joints = (
            copied.left_mount_joint, copied.right_mount_joint,
        )
        for joint in body_joints:
            self.assertIs(joint.parent, copied.part)
            self.assertIs(joint, copied.part.joints[joint.label])
            self.assertIsNot(joint, rest.part.joints[joint.label])
        violin_joint = copied.violin_joint
        pose = Location((10, 20, 30), (15, 25, 35))
        copied.assembly.locate(pose)
        self.assertIs(violin_joint, copied.violin_joint)
        self.assertIs(violin_joint, copied.assembly.joints[violin_joint.label])
        self.assertEqual(violin_joint.location, pose * rest.violin_joint.location)
        self.assertEqual(rest.assembly.location, Location())

    def test_geometry_rejects_stale_foreign_or_duplicate_joints(self) -> None:
        source = SimpleRestGeometry(self.violin)
        geometry = GeometryFixture(
            source.part, source.left_mount_joint, source.right_mount_joint, source.violin_joint,
        )
        other = SimpleRestGeometry(self.violin)
        with self.assertRaisesRegex(ValueError, "registered on geometry.part"):
            Rest(replace(geometry, left_mount_joint=other.left_mount_joint), self.leg)
        with self.assertRaisesRegex(ValueError, "distinct"):
            Rest(replace(geometry, right_mount_joint=geometry.left_mount_joint), self.leg)
        # Replacing the body without replacing its joint properties is also invalid.
        with self.assertRaisesRegex(ValueError, "registered on geometry.part"):
            Rest(replace(geometry, part=source.part.moved(Location((1, 0, 0)))), self.leg)

    def test_direct_attachment_uses_final_body_after_both_cuts(self) -> None:
        geometry = SimpleRestGeometry(self.violin)
        pose = Location((10, 20, 30), (15, 25, 35))
        geometry.part.locate(pose)
        template = DirectLeg()
        rest = Rest(geometry, template)
        self.assertEqual(set(rest.part.joints), set(geometry.part.joints))
        self.assertLess(rest.part.volume, rest.installations[0].rest.volume)
        for installed, mount in zip(rest.installations, (rest.left_mount_joint, rest.right_mount_joint)):
            self.assertIsInstance(installed, DirectInstallation)
            self.assertIs(installed.attached_body, rest.part)
            self.assertEqual(installed.leg.global_location, mount.location)
            self.assertIs(installed.leg.parent, rest.assembly)
        self.assertEqual(template.assembly.location, Location())
        self.assertIsNone(template.assembly.parent)

    def test_different_attachment_mechanisms_can_share_one_rest(self) -> None:
        rest = build_simple_rest(self.violin, build_hinge_leg(angle=15), right_leg=DirectLeg())
        left, right = rest.installations
        self.assertIsInstance(left, HingeLegInstallation)
        self.assertIsInstance(right, DirectInstallation)
        self.assertIs(rest.part.joints[left.joint_label].connected_to, left.rod_joint)
        self.assertIsNone(left.rest.joints[left.joint_label].connected_to)
        self.assertIs(right.attached_body, rest.part)
        self.assertTrue(rest.part.is_valid)
        self.assertEqual(len(rest.part.solids()), 1)
        self.assertEqual(len(rest.assembly.children), 3)

    def test_invalid_dimensions(self) -> None:
        for changes in (
            {"width": 0}, {"thickness": -1}, {"left_fraction": -0.1},
            {"right_fraction": 1.1}, {"violin_gap": -1}, {"width": float("nan")},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(SimpleRestParameters(), **changes)


if __name__ == "__main__":
    unittest.main()
