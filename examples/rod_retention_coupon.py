"""Preview rod retention, or export a small housing coupon and its mating leg.

uv run python examples/rod_retention_coupon.py [--nose-clearance 0.2]
uv run python examples/rod_retention_coupon.py --export
"""

import argparse
from pathlib import Path

from build123d import Compound, Part, Pos, Rotation, export_step, export_stl

from shoulder_rest.parts.leg.hinge_leg import CavityParameters, HingeLeg
from shoulder_rest.parts.leg.rod_retention import RodRetentionParameters


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", action="store_true", help="Export to exports/rod_retention instead of opening the viewer")
    parser.add_argument("--nose-clearance", type=float, default=0.0, help="Extra nose recess clearance in mm")
    args = parser.parse_args()
    leg = HingeLeg(
        cavity=CavityParameters(nose_clearance=args.nose_clearance),
        rod_retention=RodRetentionParameters(),
        angular_range=(0, 90),
    )
    if args.export:
        output = Path("exports/rod_retention")
        output.mkdir(parents=True, exist_ok=True)
        # A standalone copy avoids exporting the assembly child's parent hierarchy.
        printed_leg = Part(leg.part.wrapped, label="Printed hinge leg")
        export_step(printed_leg, output / "printed_leg.step")
        export_step(leg.housing, output / "housing_coupon.step")
        export_step(Compound(children=[leg.housing, leg.assembly]), output / "assembly.step")
        # Lay the leg on its broad side and the coupon on its flat mounting face.
        on_side = printed_leg.moved(Rotation(0, 90, 0))
        face_down = leg.housing.moved(Rotation(180, 0, 0))
        for name, part in (("printed_leg", on_side), ("housing_coupon", face_down)):
            on_bed = part.moved(Pos(0, 0, -part.bounding_box().min.Z))
            export_stl(on_bed, output / f"{name}.stl")
        print(f"Exported STEP assembly, coupon, leg and two on-bed STLs to {output.resolve()}")
    else:
        from ocp_vscode import show

        offset = Pos(30, 0, 0)
        swung = leg.assembly.moved(offset * Rotation(90, 0, 0))
        show(leg.housing, leg.assembly, leg.housing.moved(offset), swung)


if __name__ == "__main__":
    main()
