"""Preview rod retention or export a small housing coupon and its mating leg.

uv run python examples/hinge_snaps.py
uv run python examples/hinge_snaps.py --export
"""

import argparse
from pathlib import Path

from build123d import Compound, Part, Pos, Rotation, export_step, export_stl

from shoulder_rest.parts.leg.hinge_leg import (
    CavityParameters, RodRetentionParameters, build_hinge_leg,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", action="store_true", help="Export to exports/hinge_snaps instead of opening the viewer")
    parser.add_argument("--nose-clearance", type=float, default=0.0, help="Extra nose recess clearance in mm")
    args = parser.parse_args()
    leg = build_hinge_leg(
        rod_retention=RodRetentionParameters(),
        cavity=CavityParameters(nose_clearance=args.nose_clearance),
        angular_range=(0, 90),
    )
    if args.export:
        output = Path("exports/hinge_snaps")
        output.mkdir(parents=True, exist_ok=True)
        # Standalone copies avoid exporting an assembly child's parent hierarchy.
        printed_leg = Part(leg.part.wrapped, label="Printed hinge leg")
        housing = leg.housing
        export_step(printed_leg, output / "printed_leg.step")
        export_step(housing, output / "housing_coupon.step")
        export_step(Compound(children=[housing, leg.assembly]), output / "assembly.step")
        # Put the leg on its broad side. Keep the coupon upright.
        printed_leg = printed_leg.moved(Rotation(0, 90, 0))
        for name, part in (("printed_leg", printed_leg), ("housing_coupon", housing)):
            on_bed = part.moved(Pos(0, 0, -part.bounding_box().min.Z))
            export_stl(on_bed, output / f"{name}.stl")
        print(f"Exported STEP assembly, coupon, leg and two on-bed STLs to {output.resolve()}")
    else:
        from ocp_vscode import show

        opened = leg.assembly.moved(Pos(30, 0, 0) * Rotation(90, 0, 0))
        show(leg.housing, leg.assembly, leg.housing.moved(Pos(30, 0, 0)), opened)


if __name__ == "__main__":
    main()
