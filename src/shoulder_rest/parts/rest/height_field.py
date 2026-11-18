"""Rest undersides as height fields: sample a shoulder from above, shape the samples, fit one surface.

A rest body hangs over the shoulder from its Z=0 mounting face, so its
underside is a height field over the body's XY footprint. Sampling the
shoulder cutter along vertical lines and fitting a single smooth B-spline
surface through the samples gives an underside that:

- follows only the shoulder's upper surface, so it never hooks under an
  overhang the rest could not be lifted off;
- never falls more steeply than ``MAX_SLOPE``, so it bridges where the
  shoulder drops away (or ends) instead of following it down;
- can be shaped numerically before fitting, for example levelled off with a
  floor and a smooth blend, instead of with Boolean cuts and fillets that
  depend on how the scan happens to meet them;
- is one face, so later fillets along its outline meet no seams.

Lengths are in millimeters. The fit approximates the samples within
``FIT_TOLERANCE``; detail finer than the sample spacing is smoothed away.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from build123d import Face, Shape, Solid
from numpy.typing import NDArray
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace  # type: ignore[import-untyped]
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism  # type: ignore[import-untyped]
from OCP.GeomAbs import GeomAbs_C2  # type: ignore[import-untyped]
from OCP.GeomAPI import GeomAPI_PointsToBSplineSurface  # type: ignore[import-untyped]
from OCP.gp import gp_Dir, gp_Lin, gp_Pnt, gp_Vec  # type: ignore[import-untyped]
from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector  # type: ignore[import-untyped]

try:  # OCP 7.9 and later
    from OCP.collections import Array2_double  # type: ignore[import-untyped]
except ImportError:
    from OCP.TColStd import TColStd_Array2OfReal as Array2_double  # type: ignore[import-untyped]

Grid = NDArray[np.float64]

FIT_TOLERANCE = 0.05
MAX_SLOPE = 2.0
"""Steepest underside, in mm of height per mm across; about 63 degrees."""


@dataclass(frozen=True)
class HeightField:
    """Heights ``z[i, j]`` at ``(xs[i], ys[j])`` on a regular grid of ``spacing`` mm."""

    xs: Grid
    ys: Grid
    z: Grid

    @property
    def spacing(self) -> float:
        return float(self.xs[1] - self.xs[0])

    @classmethod
    def grid(cls, bounds: tuple[float, float, float, float], spacing: float) -> "HeightField":
        """An empty (NaN) field covering ``(min_x, min_y, max_x, max_y)``."""
        min_x, min_y, max_x, max_y = bounds
        xs = np.arange(min_x, max_x + spacing, spacing)
        ys = np.arange(min_y, max_y + spacing, spacing)
        if len(xs) < 4 or len(ys) < 4:
            raise ValueError("Height field needs at least four samples along each axis")
        return cls(xs, ys, np.full((len(xs), len(ys)), np.nan))

    def points(self) -> tuple[Grid, Grid]:
        """X and Y of every sample, shaped like ``z``."""
        x, y = np.meshgrid(self.xs, self.ys, indexing="ij")
        return x, y

    def with_z(self, z: Grid) -> "HeightField":
        return HeightField(self.xs, self.ys, z)


def sample_top(shape: Shape, field: HeightField) -> HeightField:
    """Z of the highest point of ``shape`` on each vertical line; NaN where a line misses it."""
    top = shape.bounding_box().max.Z + 1
    span = top - shape.bounding_box().min.Z + 1
    intersector = IntCurvesFace_ShapeIntersector()
    intersector.Load(shape.wrapped, 1e-4)
    down = gp_Dir(0, 0, -1)
    z = np.full(field.z.shape, np.nan)
    for i, x in enumerate(field.xs):
        for j, y in enumerate(field.ys):
            intersector.Perform(gp_Lin(gp_Pnt(float(x), float(y), top), down), 0, span)
            if intersector.IsDone() and intersector.NbPnt():
                z[i, j] = max(intersector.Pnt(k).Z() for k in range(1, intersector.NbPnt() + 1))
    return field.with_z(z)


def limit_slope(field: HeightField, max_slope: float = MAX_SLOPE) -> HeightField:
    """Raise samples until no slope exceeds ``max_slope``; missed samples are filled the same way.

    Each sample becomes the highest point of the downward cones of slope
    ``max_slope`` hung from every hit. Heights only rise, so a rest built on
    the result never cuts into what was sampled.
    """
    z = field.z
    hit = ~np.isnan(z)
    if not hit.any():
        raise ValueError("The shoulder lies nowhere under the rest's footprint")
    hit_i, hit_j = np.nonzero(hit)
    hit_z = z[hit_i, hit_j]
    all_i, all_j = np.indices(z.shape).reshape(2, -1)
    limited = np.empty(all_i.shape)
    for start in range(0, len(all_i), 256):
        i, j = all_i[start:start + 256], all_j[start:start + 256]
        distance = np.hypot(i[:, None] - hit_i[None], j[:, None] - hit_j[None]) * field.spacing
        limited[start:start + 256] = np.max(hit_z[None] - max_slope * distance, axis=1)
    return field.with_z(limited.reshape(z.shape))


def smooth_max(a: Grid, b: Grid, blend: float | Grid) -> Grid:
    """max(a, b), rounded where they cross; ``blend`` (mm) sets the rounding's width.

    Matches the larger value wherever the two differ by ``blend`` or more,
    and exceeds both by ``blend / 6`` where they are equal (a cubic blend,
    continuous in slope and curvature).
    """
    blend = np.broadcast_to(np.asarray(blend, dtype=float), np.shape(a))
    width = np.where(blend > 0, blend, 1.0)
    h = np.where(blend > 0, np.clip(1 - np.abs(a - b) / width, 0, 1), 0.0)
    return np.maximum(a, b) + h**3 * blend / 6


def surface(field: HeightField, tolerance: float = FIT_TOLERANCE) -> Face:
    """A cubic B-spline face approximating the field over its whole grid."""
    if np.isnan(field.z).any():
        raise ValueError("Fill the height field before fitting a surface")
    rows, columns = field.z.shape
    heights = Array2_double(1, rows, 1, columns)
    for i in range(rows):
        for j in range(columns):
            heights.SetValue(i + 1, j + 1, float(field.z[i, j]))
    fit = GeomAPI_PointsToBSplineSurface(
        heights, float(field.xs[0]), field.spacing, float(field.ys[0]), field.spacing,
        3, 3, GeomAbs_C2, tolerance,
    )
    if not fit.IsDone():
        raise ValueError("Could not fit a surface to the height field")
    return Face(BRepBuilderAPI_MakeFace(fit.Surface(), 1e-6).Face())


def above(face: Face, top: float) -> Solid:
    """The solid swept up from a height-field face to beyond the plane Z=``top``."""
    lowest = face.bounding_box().min.Z
    prism = Solid(BRepPrimAPI_MakePrism(face.wrapped, gp_Vec(0, 0, top - lowest)).Shape())
    if not prism.is_valid or prism.volume <= 0:
        raise ValueError("Height-field surface did not make a valid solid")
    return prism


def path_coordinates(
    field: HeightField, points: Sequence[tuple[float, float]], normals: Sequence[tuple[float, float]],
) -> tuple[Grid, Grid]:
    """Each sample's arc-length fraction along a sampled path and signed offset from it.

    ``points`` sample the path evenly by length and ``normals`` are unit XY
    normals there; the offset is positive along the normal.
    """
    x, y = field.points()
    path = np.asarray(points, dtype=float)
    normal = np.asarray(normals, dtype=float)
    dx = x[..., None] - path[:, 0]
    dy = y[..., None] - path[:, 1]
    nearest = np.argmin(dx**2 + dy**2, axis=-1)
    fraction = nearest / (len(path) - 1)
    offset = (
        np.take_along_axis(dx, nearest[..., None], -1)[..., 0] * normal[nearest, 0]
        + np.take_along_axis(dy, nearest[..., None], -1)[..., 0] * normal[nearest, 1]
    )
    return fraction, offset
