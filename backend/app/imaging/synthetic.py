"""Clearly synthetic santa drawings on the template, 'photographed' with perspective,
rotation, uneven light and noise. Used for demo mode and tests only."""
import cv2
import numpy as np

from .. import config as C
from .template import render_raster

PX_PER_MM = 7.0


def _wobble(rng, pts, amount):
    pts = np.asarray(pts, np.float64)
    return (pts + rng.normal(0, amount, pts.shape)).astype(np.int32)


def _ellipse_pts(cx, cy, rx, ry, a0=0, a1=360, n=40):
    t = np.radians(np.linspace(a0, a1, n))
    return np.stack([cx + rx * np.cos(t), cy + ry * np.sin(t)], 1)


def draw_santa(page: np.ndarray, rng: np.random.Generator, kind: str = "normal") -> None:
    """Draws onto a page raster (uint8 grey, PX_PER_MM scale) inside the drawing area."""
    k = PX_PER_MM
    ax, ay, aw, ah = C.AREA_X_MM * k, C.AREA_Y_MM * k, C.AREA_W_MM * k, C.AREA_H_MM * k
    s = rng.normal(1.0, 0.12)
    cx = ax + aw * rng.normal(0.5, 0.05)
    cy = ay + ah * rng.normal(0.52, 0.05)
    if kind == "tiny":
        s, cx, cy = 0.35, ax + aw * 0.22, ay + ah * 0.2
    elif kind == "huge":
        s = 1.55
    elif kind == "offset":
        cx, cy = ax + aw * 0.72, ay + ah * 0.68
        s = 0.7
    U = aw * 0.13 * s  # head radius
    th = max(2, int(round(rng.uniform(0.5, 1.0) * k)))
    wob = 0.25 * k
    color = int(rng.uniform(0, 60))

    def line(pts, closed=False, t=th):
        cv2.polylines(page, [_wobble(rng, pts, wob)], closed, color, t, cv2.LINE_AA)

    if kind == "tree":  # off-topic outlier
        for i in range(3):
            w, y = U * (1.6 - 0.4 * i), cy + U * (1.2 - 1.3 * i)
            line([[cx - w, y], [cx, y - U * 1.6], [cx + w, y]], True)
        line([[cx - U * 0.3, cy + U * 1.2], [cx - U * 0.3, cy + U * 2], [cx + U * 0.3, cy + U * 2],
              [cx + U * 0.3, cy + U * 1.2]])
        return
    hy = cy - U * 1.2
    line(_ellipse_pts(cx, hy, U, U * 1.05), True)                         # head
    hat_tip = (cx + U * rng.uniform(-0.9, 0.9), hy - U * rng.uniform(2.0, 2.8))
    line([[cx - U * 1.1, hy - U * 0.55], hat_tip, [cx + U * 1.1, hy - U * 0.55]])  # hat
    line([[cx - U * 1.2, hy - U * 0.45], [cx + U * 1.2, hy - U * 0.45],
          [cx + U * 1.2, hy - U * 0.75], [cx - U * 1.2, hy - U * 0.75]], True)     # brim
    line(_ellipse_pts(*hat_tip, U * 0.25, U * 0.25), True)                # pompom
    for dx in (-0.35, 0.35):                                               # eyes
        cv2.circle(page, (int(cx + dx * U), int(hy - U * 0.1)), max(2, int(U * 0.09)), color, -1, cv2.LINE_AA)
    line(_ellipse_pts(cx, hy + U * 0.2, U * 0.15, U * 0.12), True)        # nose
    beard_len = U * rng.uniform(1.0, 1.8)
    zig = [[cx - U * 0.95, hy + U * 0.1]]
    n = int(rng.integers(5, 9))
    for i in range(1, n):
        x = cx - U * 0.95 + 1.9 * U * i / n
        y = hy + U * 0.6 + beard_len * np.sin(np.pi * i / n) * (1.0 if i % 2 else 0.8)
        zig.append([x, y])
    zig.append([cx + U * 0.95, hy + U * 0.1])
    line(zig)                                                              # beard
    if rng.random() < 0.85:                                                # body
        top, bot = hy + U * 1.4, hy + U * rng.uniform(3.6, 4.4)
        line([[cx - U * 0.9, top], [cx - U * 1.5, bot], [cx + U * 1.5, bot], [cx + U * 0.9, top]])
        line([[cx - U * 1.25, (top + bot) / 2 + U * 0.3], [cx + U * 1.25, (top + bot) / 2 + U * 0.3]])  # belt
        line([[cx - U * 0.95, top + U * 0.2], [cx - U * 2.0, top + U * rng.uniform(0.8, 1.6)]])  # arms
        line([[cx + U * 0.95, top + U * 0.2], [cx + U * 2.0, top + U * rng.uniform(0.8, 1.6)]])
    if rng.random() < 0.4:                                                 # filled hat
        cv2.fillPoly(page, [np.array([[cx - U * 1.0, hy - U * 0.75], hat_tip, [cx + U * 1.0, hy - U * 0.75]],
                                     np.int32)], int(rng.uniform(60, 120)), cv2.LINE_AA)


def blank_page() -> np.ndarray:
    return render_raster(PX_PER_MM)


def photograph(page: np.ndarray, rng: np.random.Generator, rotate: float | None = None,
               strength: float = 1.0, blur: float = 0.0) -> np.ndarray:
    """Simulate a phone photo of the page. Returns BGR uint8."""
    h, w = page.shape
    pad = int(0.12 * max(h, w))
    canvas_w, canvas_h = w + 2 * pad, h + 2 * pad
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    jitter = rng.uniform(-0.05, 0.05, (4, 2)) * [w, h] * strength
    dst = np.float32(src + pad + jitter)
    ang = np.radians(rotate if rotate is not None else rng.uniform(-12, 12) * strength)
    c = np.array([canvas_w / 2, canvas_h / 2])
    R = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    dst = np.float32((dst - c) @ R.T + c)
    M = cv2.getPerspectiveTransform(src, dst)
    table = int(rng.uniform(70, 110))
    photo = cv2.warpPerspective(page, M, (canvas_w, canvas_h), flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=table).astype(np.float32)
    yy, xx = np.mgrid[0:canvas_h, 0:canvas_w].astype(np.float32)
    gx, gy = rng.uniform(-1, 1, 2)
    light = 1 - 0.18 * strength * (0.5 + 0.5 * (gx * (xx / canvas_w - 0.5) + gy * (yy / canvas_h - 0.5)) * 2) / 2
    photo = photo * light * rng.uniform(0.88, 1.0)
    if blur:
        photo = cv2.GaussianBlur(photo, (0, 0), blur)
    photo += rng.normal(0, 3.0, photo.shape)
    gray = np.clip(photo, 0, 255).astype(np.uint8)
    bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR).astype(np.int16)
    bgr += np.array([-6, 0, 8], np.int16)  # warm indoor light
    return np.clip(bgr, 0, 255).astype(np.uint8)


def kind_for(index: int) -> str:
    """Deterministic mix: mostly normal santas, a few planned outliers."""
    return {7: "tiny", 19: "tree", 31: "offset", 53: "huge"}.get(index % 60, "normal")


def demo_photo_jpeg(seed: int, kind: str = "normal", problem: str | None = None) -> bytes:
    rng = np.random.default_rng(seed)
    page = blank_page()
    if problem != "empty":
        draw_santa(page, rng, kind)
    if problem == "no_markers":
        # Fold/cut away the marker rows: keep only the framed area plus a little paper.
        k = PX_PER_MM
        y0, y1 = int((C.FRAME_Y_MM - 1.0) * k), int((C.FRAME_Y_MM + C.FRAME_H_MM + 1.0) * k)
        page = page[y0:y1, :]
    photo = photograph(page, rng, strength=0.6 if problem == "no_markers" else 1.0)
    ok, buf = cv2.imencode(".jpg", photo, [cv2.IMWRITE_JPEG_QUALITY, 88])
    assert ok
    return buf.tobytes()
