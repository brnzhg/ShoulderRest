# 2026-11-08: Hinge leg nut standoff and naming

`LegParameters.nut_standoff` raises the nut slot and its walls off the mounting face, lengthening the leg's upright. It defaults to 0, so existing legs, cavities and rests are unchanged (bit-identical).

The hinge leg's three "housings" were renamed so that "housing" only means the housing guide:

| Before | After |
|---|---|
| `rod_house_length`, `rod_house_half` | `knuckle_size`, `knuckle_half` |
| `housing_gap`, `housing_start_y` | `nut_block_gap`, `nut_block_front_y` |
| `wall` | `nut_wall` |
| `rod_hole_diameter` | `rod_bore_diameter` |
| `_lower_profile`, `_leg_profile` | `_base_profile`, `_side_profile` |

`top_z` now includes the standoff, and `nut_joint` sits on the raised slot floor (`nut_slot_floor_z`).
