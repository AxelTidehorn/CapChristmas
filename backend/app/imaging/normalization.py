"""Registered grey area -> ink map I(x,y) in [0,1] (0 = paper, 1 = black ink) + quality."""
import cv2
import numpy as np

from .. import config as C


def ink_map(warped: np.ndarray, oversample: int = C.OVERSAMPLE) -> np.ndarray:
    """warped: float32 grey 0..1 at CANVAS x oversample. Returns float32 ink at CANVAS size."""
    paper = float(np.percentile(warped, 95))
    paper = max(paper, 0.05)
    k = int(round(C.BACKGROUND_KERNEL_MM * C.CANVAS_W * oversample / C.AREA_W_MM)) | 1
    bg = cv2.morphologyEx(warped, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    bg = cv2.GaussianBlur(bg, (0, 0), k / 2)
    # Floor keeps large filled areas (a solid hat) from being mistaken for shaded paper.
    bg = np.maximum(bg, C.BACKGROUND_FLOOR * paper)
    ratio = warped / bg
    ink = np.clip((C.INK_RATIO_ZERO - ratio) / C.INK_RATIO_SPAN, 0.0, 1.0).astype(np.float32)
    ink = cv2.resize(ink, (C.CANVAS_W, C.CANVAS_H), interpolation=cv2.INTER_AREA)
    e = C.EDGE_MASK_PX
    if e:
        ink[:e, :] = 0
        ink[-e:, :] = 0
        ink[:, :e] = 0
        ink[:, -e:] = 0
    return ink


def quality(ink: np.ndarray, outside_fraction: float = 0.0) -> tuple[dict, list[str]]:
    coverage = float(np.mean(ink > C.INK_PIXEL_THRESHOLD))
    marked = ink[ink > 0.05]
    strength = float(np.percentile(marked, 95)) if marked.size > 200 else 0.0
    gx = cv2.Sobel(ink, cv2.CV_32F, 1, 0, ksize=3) / 8
    gy = cv2.Sobel(ink, cv2.CV_32F, 0, 1, ksize=3) / 8
    grad = np.hypot(gx, gy)
    sharpness = float(np.percentile(grad, 99.5)) / strength if strength > 0 else 0.0
    metrics = {
        "coverage": round(coverage, 5),
        "mean_ink": round(float(ink.mean()), 5),
        "stroke_strength": round(strength, 4),
        "sharpness": round(sharpness, 4),
        "outside_fraction": round(outside_fraction, 4),
    }
    reasons = []
    if coverage < C.Q_EMPTY_COVERAGE:
        reasons.append("Tomt eller nästan tomt ark.")
    else:
        if strength < C.Q_FAINT_P99:
            reasons.append("Mycket svaga streck – kontrollera ljus/exponering.")
        if sharpness < C.Q_BLUR_SHARPNESS:
            reasons.append("Bilden verkar suddig.")
    if coverage > C.Q_HEAVY_COVERAGE:
        reasons.append("Ovanligt mycket mörk yta – skugga, fel exponering eller fel utsnitt?")
    if outside_fraction > C.Q_OUTSIDE_FRACTION:
        reasons.append("Delar av ritytan saknas i fotot (beskuret).")
    return metrics, reasons


def ink_to_png_array(ink: np.ndarray) -> np.ndarray:
    """Plain rendering: paper white, ink black. uint8."""
    return np.round(255 * (1 - np.clip(ink, 0, 1))).astype(np.uint8)
