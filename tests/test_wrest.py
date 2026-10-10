"""Smoke checks for the independently rounded W blank."""

from dataclasses import replace
from math import cos, radians, sin, tan
import unittest

from build123d import (
    Align, Box, Compound, Edge, GeomType, Location, Plane, Pos, Rotation, Vector, Wire,
)

from shoulder_rest.parts.leg.hinge_leg import build_hinge_leg
from shoulder_rest.parts.rest import Rest
from shoulder_rest.parts.shoulder.step_shoulder import load_shoulder_cast
from shoulder_rest.parts.violin_outline.spline_violin_outline import build_violin_outline
from shoulder_rest.parts.wrest import (
    WHeadCapParameters, WRestGeometry, WRestParameters, _blank_from_centerline,
    _blank_sections, _capped_head, _contoured_head, _rounded_centerline,
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
        baseline = _blank_from_centerline(_rounded_centerline(left, right, parameters), parameters)
        self.assertTrue(baseline.is_valid)
        self.assertEqual(len(baseline.solids()), 1)

        for change in (
            {"first_radius": 2},
            {"second_radius": 3},
            {"third_radius": 1},
        ):
            with self.subTest(change=change):
                changed = replace(parameters, **change)
                blank = _blank_from_centerline(_rounded_centerline(left, right, changed), changed)
                self.assertTrue(blank.is_valid)
                self.assertEqual(len(blank.solids()), 1)
                self.assertNotAlmostEqual(blank.volume, baseline.volume, places=4)

    def test_head_offsets_and_tail_dimensions(self) -> None:
        parameters = WRestParameters()
        centerline = Wire([
            Edge.make_line((95, 0), (-30, 0)),
            Edge.make_line((-30, 0), (-105, 0)),
        ])
        tail, head = _blank_sections(centerline, parameters)
        self.assertAlmostEqual(tail.bounding_box().size.Y, parameters.tail_width)
        self.assertAlmostEqual(tail.bounding_box().min.Z, -parameters.tail_thickness)
        self.assertAlmostEqual(head.bounding_box().min.Y, -parameters.head_front_width)
        self.assertAlmostEqual(head.bounding_box().max.Y, parameters.head_back_width)
        self.assertAlmostEqual(head.bounding_box().min.Z, -parameters.head_depth)

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

    def test_head_caps_follow_end_frames_and_blend_to_planar_contact(self) -> None:
        # A rotated head and a planar shoulder exercise both end frames without
        # relying on the bundled cast's face types or tessellation.
        rotation = Rotation(0, 0, 23)
        parameters = WRestParameters(
            left_cap=WHeadCapParameters(angle=8, height=16, depth=18, blend_radius=2),
            right_cap=WHeadCapParameters(angle=15, height=14, depth=20, blend_radius=1),
        )
        centerline = _rounded_centerline(
            Vector(-95, 12), Vector(95, 12), parameters,
        ).moved(rotation)
        tail, head = _blank_sections(centerline, parameters)
        shoulder_tool = Box(400, 400, 100, align=(Align.CENTER, Align.CENTER, Align.MAX)).moved(
            Pos(0, 0, -30),
        )
        contoured, contact_faces = _contoured_head(head, shoulder_tool)
        capped = _capped_head(contoured, contact_faces, centerline, parameters)
        self.assertTrue(capped.is_valid)
        self.assertEqual(len(capped.solids()), 1)
        uncapped = head - shoulder_tool
        self.assertLess(capped.volume, uncapped.volume)
        self.assertGreater(
            sum(f.geom_type == GeomType.CYLINDER for f in capped.faces()),
            sum(f.geom_type == GeomType.CYLINDER for f in uncapped.faces()),
        )
        body = capped + tail
        self.assertAlmostEqual((body & tail).volume, tail.volume, places=4)
        self.assertEqual(len(body.solids()), 1)

        path = Wire(centerline.order_edges()[:-1])
        for parameter, cap in ((1, parameters.left_cap), (0, parameters.right_cap)):
            assert cap is not None
            tangent = path.tangent_at(parameter)
            inward = -tangent if parameter == 1 else tangent
            front = Vector(-tangent.Y, tangent.X, 0)
            tip = path.position_at(parameter)
            for across in (-5, 0, 5):
                point = tip + inward * 5 + front * across + Vector(
                    0, 0, -cap.height - across * tan(radians(cap.angle)),
                )
                self.assertLess(min(f.distance_to(point) for f in capped.faces()), 1e-6)
            # Away from the blend, fixed depth leaves the original contact face.
            unchanged = tip + inward * (cap.depth + 5) + Vector(0, 0, -30)
            self.assertLess(min(f.distance_to(unchanged) for f in capped.faces()), 1e-6)

            # The offset curve may stick out beyond the end plane. It must also
            # be capped, rather than leaving a thin ridge at full head height.
            for vertex in capped.vertices():
                distance = (Vector(vertex) - tip).dot(inward)
                if distance < -1e-6:
                    across = (Vector(vertex) - tip).dot(front)
                    cap_z = -cap.height - across * tan(radians(cap.angle))
                    self.assertGreaterEqual(vertex.Z, cap_z - 1e-6)

    def test_local_geometry_mounts_and_assembly_placement(self) -> None:
        shoulder = load_shoulder_cast(
            cast_location=Location((0, 0, 0), (30, 30, -5)),
            violin_location=(
                Pos(-55, -87.5, 57.5) * Rotation(0, 0, 66) * Rotation(8, 0, 0)
                * Location((18, 2, 24), (0, -24, 0))
            ),
        )
        violin = build_violin_outline()
        geometry = WRestGeometry(violin, shoulder)
        self.assertEqual(geometry.part.location, Location())
        fitted_pose = violin.mount_joint.location * geometry.violin_joint.relative_location.inverse()
        left = violin.attachment_point("left", 0.46)
        right = violin.attachment_point("right", 0.4)
        centerline = _rounded_centerline(left, right, geometry.parameters)
        tail, head = _blank_sections(centerline, geometry.parameters)
        local_body = geometry.part.moved(geometry.part.location.inverse())
        self.assertAlmostEqual((local_body & tail).volume, tail.volume, places=4)
        self.assertLess(local_body.volume, (tail + head).volume)

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
        self.assertEqual(rest.assembly.location, Location())
        legs = (
            rest.left.attach_to(rest.assembly, angle=20),
            rest.right.attach_to(rest.assembly),
        )
        housing = rest.left.attach_housing_to(rest.assembly)
        rest.position_on(violin)
        scene = Compound(children=[shoulder.assembly, violin.block, rest.assembly])
        self.assertEqual(rest.violin_joint.location, violin.mount_joint.location)
        self.assertEqual(rest.part.global_location, fitted_pose)
        for leg, installation, angle in zip(legs, rest.installations, (20, 0)):
            self.assertEqual(leg.global_location, installation.tool.location * Rotation(angle, 0, 0))
        self.assertEqual(housing.global_location, rest.left.housing.location)
        self.assertTrue(scene.is_valid)


if __name__ == "__main__":
    unittest.main()
