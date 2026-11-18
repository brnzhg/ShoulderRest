# 2026-11-18: W head underside from a height field; caps become floors

The W head's underside is now one surface fitted to the shoulder, instead of the shoulder cast subtracted from an 80 mm blank and trimmed by cap boxes. Under random placement changes of up to 3 mm and 3 degrees around a fitted rest, 47 of 48 fits now build, against 13 of 24 before; the old caps' step and seam fillets caused most failures.

- `parts.rest.height_field` samples a cutter along vertical lines, limits the slope (the underside bridges where the shoulder drops away or ends), shapes the samples numerically and fits one cubic B-spline face. The fit follows the shoulder within the fit tolerance (0.05 mm).
- A cap (`WHeadCapParameters`) is now a floor plane the underside never drops below, blended in with a smooth maximum: `height`, `angle` and the new `slope` place the plane, and `blend` (mm) sets the rounding width. `depth` and `blend_radius` are gone; there is no step to trim to. Each cap holds at its own end and hands over to the other end's floor across the middle of the head (`CAP_HANDOVER`).
- `WHeadParameters.depth` is now the deepest the underside may go where neither the shoulder nor a cap holds it up. `corner_radius` rounds the band's end corners in plan rather than with 3D fillets, and `sample_spacing` sets the sampling grid.
- The tail starts slightly inside the head and is rounded on its own before joining, so the head-tail join needs no fillet.
- The underside may not come within 1 mm of the mounting face (`MIN_THICKNESS`).
- numpy is now a direct dependency.

| Before | After |
|---|---|
| `WHeadCapParameters(angle, height, depth, blend_radius)` | `WHeadCapParameters(angle, height, slope=0, blend=6)` |
