"""Lodge-branded QR codes (install the ``bdh-sdk[qr]`` extra)."""
from functools import lru_cache
from pathlib import Path

QR_COLOR = "#0b1622"
QR_BORDER = 4  # quiet zone, in modules (the QR spec minimum)
LOGO_FRACTION = 0.26  # logo width as a share of the code width; safe with ECC level H
LOGO_FILE = Path(__file__).parent / "bdl-monogram.svg"


@lru_cache(maxsize=1)
def _logo_inner():
    """Contents of the monogram SVG (everything inside the root <svg>)."""
    svg = LOGO_FILE.read_text(encoding="utf-8")
    return svg[svg.index(">") + 1:svg.rindex("</svg>")]


def qr_svg(text):
    """SVG of a QR code for text: round dots, square finder patterns and the
    lodge monogram over a cleared centre. Error correction H (30%) keeps it
    scannable with the centre covered."""
    import qrcode

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, border=QR_BORDER)
    qr.add_data(text)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    n = len(matrix)
    finders = [(QR_BORDER, QR_BORDER), (QR_BORDER, n - QR_BORDER - 7), (n - QR_BORDER - 7, QR_BORDER)]

    hole = round((n - 2 * QR_BORDER) * LOGO_FRACTION) | 1  # odd, so it centres on a module
    h0 = (n - hole) // 2
    h1 = h0 + hole

    def skip(r, c):
        in_finder = any(fr <= r < fr + 7 and fc <= c < fc + 7 for fr, fc in finders)
        in_hole = h0 - 1 <= r <= h1 and h0 - 1 <= c <= h1  # plus a one-module margin
        return in_finder or in_hole

    dots = "".join(
        f'<circle cx="{c + .5}" cy="{r + .5}" r=".46"/>'
        for r, row in enumerate(matrix)
        for c, on in enumerate(row)
        if on and not skip(r, c)
    )
    # Finder patterns stay square: rounded corners break some decoders (OpenCV).
    eyes = "".join(
        f'<rect x="{c + .5}" y="{r + .5}" width="6" height="6" fill="none" stroke="{QR_COLOR}" stroke-width="1"/>'
        f'<rect x="{c + 2}" y="{r + 2}" width="3" height="3"/>'
        for r, c in finders
    )
    pad = 0.6
    size = hole + 2 - 2 * pad
    origin = h0 - 1 + pad
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" shape-rendering="geometricPrecision">'
        f'<rect width="{n}" height="{n}" fill="#fff"/>'
        f'<g fill="{QR_COLOR}">{dots}</g>'
        f'<g fill="{QR_COLOR}">{eyes}</g>'
        f'<svg x="{origin}" y="{origin}" width="{size}" height="{size}" viewBox="0 0 100 100" class="qr-logo">'
        f'{_logo_inner()}</svg></svg>'
    )
