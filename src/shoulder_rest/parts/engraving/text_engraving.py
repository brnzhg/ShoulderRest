"""Text engravings, typically version IDs.

Text defaults to a bold sans so its strokes stay printable at small sizes.
OCCT silently substitutes another font, often a symbol font, when a named
font is missing, so a named font must be installed; pass ``font_path`` to pin
an exact font file for reproducible exports.
"""

from os import PathLike

from build123d import Align, FontManager, FontStyle, Text

from .engraving import Engraving


def text_engraving(
    text: str, *, font_size: float = 6, depth: float = 0.6, font: str = "Liberation Sans",
    font_path: PathLike[str] | str | None = None, font_style: FontStyle = FontStyle.BOLD,
) -> Engraving:
    """One line of text starting at the origin, vertically centered on X.

    ``font_size`` is the em size in mm; capitals are about 0.7 of it.
    ``font_path`` takes precedence over ``font``.
    """
    if not text.strip():
        raise ValueError("Engraving text must not be blank")
    if font_path is None:
        found = FontManager().find_font(font, font_style)
        if found is None or found.FontName().ToCString().casefold() != font.casefold():
            raise ValueError(f"Font {font!r} is not installed; install it or pass font_path")
    design = Text(
        text, font_size, font=font, font_path=None if font_path is None else str(font_path),
        font_style=font_style, align=(Align.MIN, Align.CENTER),
    )
    return Engraving(design, depth)


if __name__ == "__main__":
    from build123d import Box, Location
    from ocp_vscode import show

    from .engraving import engrave

    coupon = Box(30, 12, 3)
    top = coupon.faces().sort_by()[-1]
    show(engrave(coupon, text_engraving("v1.0"), top, Location((-12, 0, 1.5))))
