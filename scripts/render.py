"""Render shapes to a PNG sheet of standard views, for inspecting geometry without a viewer.

    uv run python scripts/render.py shoulder_rest.parts.leg.hinge_leg
    uv run python scripts/render.py examples/rod_retention_coupon.py --views iso,bottom
    uv run python scripts/render.py shoulder_rest.parts.rest.w_rest --hide shoulder -o out.png
    uv run python scripts/render.py shoulder_rest.parts.leg.hinge_leg --ghost housing,tool
    uv run python scripts/render.py shoulder_rest.parts.rest.w_rest --frame "rest body" --hide shoulder,violin

The target is a module or script whose main section calls ``ocp_vscode.show``;
it runs with ``show`` captured, and the last call's shapes are rendered with
orthographic cameras. Shapes keep their own colors where set. ``render`` can
also be called directly with shapes.
"""

import argparse
import math
import runpy
import sys
import types
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import vtkmodules.vtkRenderingFreeType  # Registers text rendering.
import vtkmodules.vtkRenderingOpenGL2  # noqa: F401  Registers the render window backend.
from build123d import Compound, GeomType, Shape, Vector
from vtkmodules.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
from vtkmodules.vtkCommonCore import vtkPoints
from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData
from vtkmodules.vtkFiltersCore import vtkPolyDataNormals
from vtkmodules.vtkIOImage import vtkPNGWriter
from vtkmodules.vtkRenderingCore import (
    vtkActor, vtkLightKit, vtkPolyDataMapper, vtkRenderer, vtkRenderWindow, vtkTextActor,
    vtkWindowToImageFilter,
)

# Camera direction (from the model toward the camera) and screen-up for each view.
VIEWS: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
    "iso": ((1, -1, 1), (0, 0, 1)),
    "iso_below": ((1, -1, -1), (0, 0, 1)),
    "top": ((0, 0, 1), (0, 1, 0)),
    "bottom": ((0, 0, -1), (0, 1, 0)),
    "front": ((0, -1, 0), (0, 0, 1)),
    "back": ((0, 1, 0), (0, 0, 1)),
    "right": ((1, 0, 0), (0, 0, 1)),
    "left": ((-1, 0, 0), (0, 0, 1)),
}
DEFAULT_VIEWS = ("iso", "iso_below", "top", "bottom", "front", "right")
PALETTE = (
    (0.62, 0.71, 0.82), (0.86, 0.71, 0.50), (0.60, 0.78, 0.62),
    (0.84, 0.60, 0.60), (0.74, 0.67, 0.85), (0.80, 0.80, 0.55),
)
BACKGROUND = (0.97, 0.97, 0.96)
TEXT = (0.2, 0.2, 0.2)


def render(
    shapes: Iterable[Shape], path: Path | str, *, views: Sequence[str] = DEFAULT_VIEWS,
    size: int = 600, hide: Sequence[str] = (), ghost: Sequence[str] = (), frame: str | None = None,
) -> list[tuple[str, tuple[float, float, float]]]:
    """Write a PNG with one orthographic viewport per view; return each part's label and color.

    Assemblies are drawn leaf by leaf at their global locations, colored by
    label. Label matching is by case-insensitive substring: leaves matching a
    ``hide`` string are skipped, and those matching a ``ghost`` string are drawn
    translucent to show what is inside. ``frame`` names a leaf whose local frame
    the views use instead of the world frame, such as a positioned rest body.
    """
    unknown = [view for view in views if view not in VIEWS]
    if unknown or not views:
        raise ValueError(f"Unknown or missing views {unknown}; choose from {', '.join(VIEWS)}")
    leaves = [leaf for shape in shapes for leaf in _leaves(shape)]
    if frame is not None:
        anchor = next((leaf for leaf in leaves if _matches(leaf, [frame])), None)
        if anchor is None:
            raise ValueError(f"No part label contains {frame!r}")
        to_frame = anchor.location.inverse()
        leaves = [leaf.located(to_frame * leaf.location) for leaf in leaves]
    leaves = [leaf for leaf in leaves if not _matches(leaf, hide)]
    if not leaves:
        raise ValueError("Nothing to render")
    bounds = Compound(leaves).bounding_box()
    tolerance = max(bounds.diagonal * 5e-4, 1e-3)

    colors: dict[str, tuple[float, float, float]] = {}
    layers: list[tuple[vtkPolyData | None, vtkPolyData, tuple[float, float, float], float]] = []
    for leaf in leaves:
        name = leaf.label or type(leaf).__name__
        color, opacity = _color(leaf, PALETTE[len(colors) % len(PALETTE)])
        color = colors.setdefault(name, color)
        if _matches(leaf, ghost):
            opacity = min(opacity, 0.25)
        layers.append((_surface(leaf, tolerance), _outline(leaf), color, opacity))
    legend = list(colors.items())

    columns = min(3, len(views))
    rows = math.ceil(len(views) / columns)
    tile_height = round(size * 0.75)
    window = vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(columns * size, rows * tile_height)
    window.SetMultiSamples(8)
    window.SetAlphaBitPlanes(1)
    for index, view in enumerate(views):
        column, row = index % columns, index // columns
        renderer = vtkRenderer()
        renderer.SetViewport(
            column / columns, 1 - (row + 1) / rows, (column + 1) / columns, 1 - row / rows,
        )
        renderer.SetBackground(*BACKGROUND)
        renderer.SetUseDepthPeeling(1)
        vtkLightKit().AddLightsToRenderer(renderer)
        for surface, outline, color, opacity in layers:
            if surface is not None:
                renderer.AddActor(_actor(surface, color, opacity))
            edge_color = color if surface is None else tuple(0.35 * c for c in color)
            renderer.AddActor(_actor(outline, edge_color, 1.0, line_width=1.5 if surface is None else 1.0))
        _aim(renderer, view, bounds, aspect=size / tile_height)
        _label(renderer, view, 8, 8)
        if index == 0:
            for line, (name, color) in enumerate(legend):
                _label(renderer, name, 8, tile_height - 24 - 20 * line, [0.6 * c for c in color])
        window.AddRenderer(renderer)
    window.Render()

    image = vtkWindowToImageFilter()
    image.SetInput(window)
    image.ReadFrontBufferOff()
    writer = vtkPNGWriter()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    writer.SetFileName(str(path))
    writer.SetInputConnection(image.GetOutputPort())
    writer.Write()
    window.Finalize()
    return legend


def _matches(shape: Shape, words: Sequence[str]) -> bool:
    label = (shape.label or "").casefold()
    return any(word.casefold() in label for word in words)


def _leaves(shape: Shape) -> list[Shape]:
    """Assembly leaves, each copied to its global location."""
    if isinstance(shape, Compound) and shape.children:
        return [leaf for child in shape.children for leaf in _leaves(child)]
    return [shape.located(shape.global_location)]


def _color(
    shape: Shape, fallback: tuple[float, float, float],
) -> tuple[tuple[float, float, float], float]:
    if shape.color is None:
        return fallback, 1.0
    red, green, blue, alpha = tuple(shape.color)
    return (red, green, blue), alpha


def _surface(shape: Shape, tolerance: float) -> vtkPolyData | None:
    """Smooth-shaded triangles, or None for wire-only shapes such as joint symbols."""
    if not shape.faces():
        return None
    try:
        vertices, triangles = shape.tessellate(tolerance, angular_tolerance=0.2)
    except AttributeError:
        # A face that cannot be meshed, such as a zero-area sliver, fails the
        # whole shape; mesh face by face and skip it instead.
        vertices, triangles, skipped = [], [], 0
        for face in shape.faces():
            try:
                face_vertices, face_triangles = face.tessellate(tolerance, angular_tolerance=0.2)
            except AttributeError:
                skipped += 1
                continue
            start = len(vertices)
            vertices.extend(face_vertices)
            triangles.extend((start + a, start + b, start + c) for a, b, c in face_triangles)
        print(f"{shape.label}: skipped {skipped} faces that could not be meshed", file=sys.stderr)
    points = vtkPoints()
    points.SetData(numpy_to_vtk(np.array([tuple(v) for v in vertices], dtype=float), deep=True))
    connectivity = np.array(triangles, dtype=np.int64).ravel()
    cells = vtkCellArray()
    cells.SetData(
        numpy_to_vtkIdTypeArray(np.arange(0, len(connectivity) + 1, 3, dtype=np.int64), deep=True),
        numpy_to_vtkIdTypeArray(connectivity, deep=True),
    )
    mesh = vtkPolyData()
    mesh.SetPoints(points)
    mesh.SetPolys(cells)
    normals = vtkPolyDataNormals()
    normals.SetInputData(mesh)
    normals.SetFeatureAngle(35)
    normals.Update()
    result: vtkPolyData = normals.GetOutput()
    return result


def _outline(shape: Shape) -> vtkPolyData:
    """Every model edge as a polyline, so boundaries read like a CAD view."""
    points = vtkPoints()
    lines = vtkCellArray()
    for edge in shape.edges():
        count = 2 if edge.geom_type == GeomType.LINE else 24
        lines.InsertNextCell(count)
        for i in range(count):
            lines.InsertCellPoint(points.InsertNextPoint(*edge @ (i / (count - 1))))
    outline = vtkPolyData()
    outline.SetPoints(points)
    outline.SetLines(lines)
    return outline


def _actor(
    data: vtkPolyData, color: Sequence[float], opacity: float, *, line_width: float = 1.0,
) -> vtkActor:
    mapper = vtkPolyDataMapper()
    mapper.SetInputData(data)
    mapper.SetResolveCoincidentTopologyToPolygonOffset()
    actor = vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(*color)
    prop.SetOpacity(opacity)
    prop.SetLineWidth(line_width)
    prop.SetSpecular(0.15)
    return actor


def _aim(renderer: vtkRenderer, view: str, bounds: Any, aspect: float) -> None:
    """Point an orthographic camera along the view and fit the bounding box."""
    direction, up = (Vector(v).normalized() for v in VIEWS[view])
    right = up.cross(direction).normalized()
    up = direction.cross(right)
    center = bounds.center()
    corners = [
        Vector(x, y, z) - center
        for x in (bounds.min.X, bounds.max.X)
        for y in (bounds.min.Y, bounds.max.Y)
        for z in (bounds.min.Z, bounds.max.Z)
    ]
    half_height = max(abs(c.dot(up)) for c in corners)
    half_width = max(abs(c.dot(right)) for c in corners)
    camera = renderer.GetActiveCamera()
    camera.ParallelProjectionOn()
    camera.SetFocalPoint(*center)
    camera.SetPosition(*(center + direction * 2 * bounds.diagonal))
    camera.SetViewUp(*up)
    camera.SetParallelScale(1.08 * max(half_height, half_width / aspect, 1e-3))
    renderer.ResetCameraClippingRange()


def _label(
    renderer: vtkRenderer, text: str, x: int, y: int, color: Sequence[float] = TEXT,
) -> None:
    label = vtkTextActor()
    label.SetInput(text)
    position = label.GetPositionCoordinate()
    position.SetCoordinateSystemToViewport()  # Pixels from the viewport's lower left.
    position.SetValue(x, y)
    style = label.GetTextProperty()
    style.SetFontSize(15)
    style.SetColor(*color)
    renderer.AddViewProp(label)


def _flatten(objects: Iterable[Any]) -> list[Shape]:
    shapes: list[Shape] = []
    for item in objects:
        if isinstance(item, Shape):
            shapes.append(item)
        elif isinstance(item, (list, tuple)):
            shapes.extend(_flatten(item))
        else:
            print(f"Skipping {type(item).__name__}: not a Shape", file=sys.stderr)
    return shapes


def _run_preview(target: str) -> list[Shape]:
    """Run a module or script's main section and return the shapes of its last show call."""
    calls: list[list[Shape]] = []
    viewer = types.ModuleType("ocp_vscode")
    viewer.show = lambda *objects, **_: calls.append(_flatten(objects))  # type: ignore[attr-defined]
    viewer.__getattr__ = lambda name: (lambda *args, **kwargs: None)  # type: ignore[method-assign]
    sys.modules["ocp_vscode"] = viewer
    sys.argv = [target]
    if target.endswith(".py"):
        runpy.run_path(target, run_name="__main__")
    else:
        runpy.run_module(target, run_name="__main__", alter_sys=True)
    if not calls:
        raise SystemExit(f"{target} did not call ocp_vscode.show")
    return calls[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", help="module name (a.b.c) or script path (*.py) with a show() preview")
    parser.add_argument("-o", "--output", type=Path, help="PNG path; defaults to exports/renders/<target>.png")
    parser.add_argument("--views", default=",".join(DEFAULT_VIEWS), help=f"comma-separated: {', '.join(VIEWS)}")
    parser.add_argument("--size", type=int, default=600, help="tile width in pixels")
    parser.add_argument("--hide", default="", help="comma-separated label substrings to skip")
    parser.add_argument("--ghost", default="", help="comma-separated label substrings to draw translucent")
    parser.add_argument("--frame", help="label substring of the part whose local frame the views use")
    args = parser.parse_args()

    name = Path(args.target).stem if args.target.endswith(".py") else args.target.rsplit(".", 1)[-1]
    output = args.output or Path("exports/renders") / f"{name}.png"
    shapes = _run_preview(args.target)
    legend = render(
        shapes, output, views=args.views.split(","), size=args.size,
        hide=[word for word in args.hide.split(",") if word],
        ghost=[word for word in args.ghost.split(",") if word], frame=args.frame,
    )
    for name, color in legend:
        print(f"{name}: rgb{tuple(round(c, 2) for c in color)}")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
