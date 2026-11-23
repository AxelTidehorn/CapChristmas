"""The printable A4 template. SVG for printing and a raster twin for tests/demo share
the geometry in config.py, so print and registration can never drift apart."""
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .. import config as C

TASK_TITLE = "RITA EN GENOMSNITTSTOMTE."
TASK_TEXT = (
    "Du har fem minuter på dig att rita en så genomsnittlig jultomte som möjligt. "
    "Din teckning kommer att analyseras. Bedömningskriterierna offentliggörs efter avslutad uppgift."
)


def aruco_dictionary():
    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, C.ARUCO_DICT))


def marker_cells(marker_id: int) -> np.ndarray:
    """6x6 bool grid (incl. black border), True = black."""
    return cv2.aruco.generateImageMarker(aruco_dictionary(), marker_id, 6) == 0


def marker_corners_mm(marker_id: int) -> np.ndarray:
    """Marker corners in mm, in OpenCV's order: TL, TR, BR, BL."""
    x, y = C.MARKERS_MM[marker_id]
    s = C.MARKER_SIZE_MM
    return np.array([[x, y], [x + s, y], [x + s, y + s], [x, y + s]], np.float64)


def frame_corners_mm() -> np.ndarray:
    x, y, w, h = C.FRAME_X_MM, C.FRAME_Y_MM, C.FRAME_W_MM, C.FRAME_H_MM
    return np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], np.float64)


def render_svg() -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{C.PAGE_W_MM}mm" height="{C.PAGE_H_MM}mm" '
        f'viewBox="0 0 {C.PAGE_W_MM} {C.PAGE_H_MM}">',
        f'<rect width="{C.PAGE_W_MM}" height="{C.PAGE_H_MM}" fill="#fff"/>',
    ]
    for mid in C.MARKERS_MM:
        x0, y0 = C.MARKERS_MM[mid]
        cell = C.MARKER_SIZE_MM / 6
        for r, row in enumerate(marker_cells(mid)):
            for c, black in enumerate(row):
                if black:
                    # tiny overlap avoids hairline gaps between cells in some renderers
                    parts.append(f'<rect x="{x0 + c * cell:.3f}" y="{y0 + r * cell:.3f}" '
                                 f'width="{cell + 0.02:.3f}" height="{cell + 0.02:.3f}" fill="#000"/>')
    parts.append(f'<rect x="{C.FRAME_X_MM}" y="{C.FRAME_Y_MM}" width="{C.FRAME_W_MM}" height="{C.FRAME_H_MM}" '
                 'fill="none" stroke="#000" stroke-width="0.4"/>')
    font = "font-family=\"Helvetica, Arial, sans-serif\""
    cx = C.PAGE_W_MM / 2
    parts.append(f'<text x="{cx}" y="31.5" text-anchor="middle" {font} font-size="7.5" font-weight="700" '
                 f'letter-spacing="0.3">{TASK_TITLE}</text>')
    # Task text in two lines between the top markers
    words, lines, cur = TASK_TEXT.split(), [], ""
    for w in words:
        if len(cur) + len(w) > 66:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    lines.append(cur)
    for i, line in enumerate(lines):
        parts.append(f'<text x="{cx}" y="{35.6 + i * 2.9:.1f}" text-anchor="middle" {font} font-size="2.5">{line}</text>')
    parts.append(f'<text x="{cx}" y="272" text-anchor="middle" {font} font-size="4">'
                 'Bidrag nr / namn: ______________________________</text>')
    parts.append(f'<text x="{cx}" y="290" text-anchor="middle" {font} font-size="2.2" fill="#000">'
                 'MEDELTOMTEN · Rita endast inom ramen. Vik inte arket över markörerna i hörnen.</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def render_raster(px_per_mm: float = 8.0) -> np.ndarray:
    """Greyscale uint8 raster of the template (used by tests and the demo generator)."""
    w, h = round(C.PAGE_W_MM * px_per_mm), round(C.PAGE_H_MM * px_per_mm)
    img = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(img)
    for mid, (x0, y0) in C.MARKERS_MM.items():
        cell = C.MARKER_SIZE_MM / 6 * px_per_mm
        for r, row in enumerate(marker_cells(mid)):
            for c, black in enumerate(row):
                if black:
                    X, Y = x0 * px_per_mm + c * cell, y0 * px_per_mm + r * cell
                    d.rectangle([X, Y, X + cell, Y + cell], fill=0)
    fx, fy = C.FRAME_X_MM * px_per_mm, C.FRAME_Y_MM * px_per_mm
    d.rectangle([fx, fy, fx + C.FRAME_W_MM * px_per_mm, fy + C.FRAME_H_MM * px_per_mm],
                outline=0, width=max(1, round(0.4 * px_per_mm)))
    try:
        font = ImageFont.load_default(size=round(6 * px_per_mm))
        small = ImageFont.load_default(size=round(2.6 * px_per_mm))
    except TypeError:  # very old Pillow
        font = small = ImageFont.load_default()
    d.text((w / 2, 28 * px_per_mm), TASK_TITLE, fill=0, font=font, anchor="mt")
    d.text((w / 2, 36 * px_per_mm), "Du har fem minuter pa dig.", fill=0, font=small, anchor="mt")
    d.text((w / 2, 270 * px_per_mm), "Bidrag nr / namn: ____________", fill=0, font=small, anchor="mt")
    return np.array(img)


def mm_to_px(px_per_mm: float, pts) -> np.ndarray:
    return np.asarray(pts, np.float64) * px_per_mm
