# 2026-11-17: Player data moves out of the library

The library no longer bundles a shoulder scan or a fitted violin placement, so it can serve any player. Geometry is unchanged.

| Before | After |
|---|---|
| `load_shoulder_cast(cast_location=CAST_LOCATION, violin_location=None)` with bundled casts | `load_shoulder(reference, extended, violin_location, cast_location=Location())` from any STEP files |
| `CAST_LOCATION`, `fitted_violin_location(...)` in `step_shoulder` | Removed; the example scan's values are in `examples/example_shoulder.py`, and a player's fit belongs to their own project |
| `src/shoulder_rest/assets/shoulder_cast/*.step` | `examples/data/shoulder_cast/{reference,extended}.step` |
| `w_rest`, `bar_rest`, `step_shoulder` main-section previews | `examples/w_rest_fitting.py`, `examples/bar_rest_fitting.py`, `examples/example_shoulder.py` |
| `examples/onshape_w_rest.py` | Moved to ShoulderRestWorkbench as its first rest version |
| `scripts/render.py` | `shoulder_rest.render` (`python -m shoulder_rest.render`), with VTK in the `render` extra |

`render` also gained `focus` (`--focus`), to fit the cameras to some parts of a larger scene, and blanks unused tiles. The package now ships `py.typed` for type-checked downstream projects.
