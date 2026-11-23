"""Versioned configuration: template geometry, image pipeline, scoring and show timing.

Every number that affects the result lives here. Changing a scoring or pipeline value
means bumping ALGORITHM_VERSION; never change them after a winner is known.
"""
import os
from pathlib import Path

ALGORITHM_VERSION = "medeltomten-v1.0"

# --- Storage -----------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("MEDELTOMTEN_DATA", REPO_ROOT / "data"))
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 80_000_000  # decompression-bomb guard
ALLOWED_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
MAX_DRAWINGS = 150  # soft ceiling, 40-75 is the normal range
WORK_MAX_SIDE = 2400  # downscaled working copy used for registration
THUMB_MAX_SIDE = 240

# --- Printed A4 template (millimetres, origin top-left, portrait) --------------
PAGE_W_MM, PAGE_H_MM = 210.0, 297.0
# The analysed drawing area. Its aspect 170 x 212.5 gives exactly 512 x 640 px.
AREA_X_MM, AREA_Y_MM, AREA_W_MM, AREA_H_MM = 20.0, 46.0, 170.0, 212.5
# Printed frame sits FRAME_GAP_MM outside the area so the line never enters the pixels.
FRAME_GAP_MM = 2.0
FRAME_X_MM = AREA_X_MM - FRAME_GAP_MM
FRAME_Y_MM = AREA_Y_MM - FRAME_GAP_MM
FRAME_W_MM = AREA_W_MM + 2 * FRAME_GAP_MM
FRAME_H_MM = AREA_H_MM + 2 * FRAME_GAP_MM
# Four unique ArUco markers (DICT_4X4_50), placed above/below the frame corners,
# inside a 15 mm printer-safe margin. Value = top-left corner of the marker in mm.
ARUCO_DICT = "DICT_4X4_50"
MARKER_SIZE_MM = 15.0
MARKERS_MM = {
    0: (FRAME_X_MM, 27.0),                                  # top-left
    1: (FRAME_X_MM + FRAME_W_MM - MARKER_SIZE_MM, 27.0),    # top-right
    2: (FRAME_X_MM + FRAME_W_MM - MARKER_SIZE_MM, 263.5),   # bottom-right
    3: (FRAME_X_MM, 263.5),                                 # bottom-left
}

# --- Normalised canvas -----------------------------------------------------------
CANVAS_W = 512
CANVAS_H = round(CANVAS_W * AREA_H_MM / AREA_W_MM)  # 640
OVERSAMPLE = 2  # warp at 2x, then area-downsample to keep thin pencil lines as grey
EDGE_MASK_PX = 4  # outermost ~1.3 mm of the area is zeroed for every drawing alike

# Ink map: ratio = grey / estimated paper. ink = clip((INK_RATIO_ZERO - ratio) / INK_RATIO_SPAN, 0, 1)
INK_RATIO_ZERO = 0.90
INK_RATIO_SPAN = 0.55
BACKGROUND_KERNEL_MM = 10.0
BACKGROUND_FLOOR = 0.80  # paper estimate never drops below 80 % of the page's paper level

# Quality flags (they ask for a human decision; nothing is excluded automatically)
Q_EMPTY_COVERAGE = 0.004
Q_HEAVY_COVERAGE = 0.40
Q_FAINT_P99 = 0.30
Q_BLUR_SHARPNESS = 0.22  # calibrated on synthetic photos: sharp ~0.5, heavily blurred <0.21
Q_OUTSIDE_FRACTION = 0.01
INK_PIXEL_THRESHOLD = 0.25

# --- Scoring (V1) -------------------------------------------------------------------
SCORING_REFERENCE_WIDTH = 512
SCORING_SIGMAS = (4.0, 16.0, 40.0)
SCORING_WEIGHTS = (0.20, 0.35, 0.45)
SHORTLIST_SIZE = 5

# --- Show timing (seconds) ------------------------------------------------------------
SHOW_PHASES = (
    ("composite", 7.0),
    ("search", 16.0),
    ("narrowing", 5.0),
    ("match", 9.0),   # ~4 s lock-on, then the winner stays on screen
    ("result", None),  # open-ended
)
COMPOSITE_STAGES = 12


def scoring_config() -> dict:
    scale = CANVAS_W / SCORING_REFERENCE_WIDTH
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "canvas": [CANVAS_W, CANVAS_H],
        "sigmas_px": [s * scale for s in SCORING_SIGMAS],
        "weights": list(SCORING_WEIGHTS),
        "blur_border": "constant-0 (paper)",
        "ink": {
            "ratio_zero": INK_RATIO_ZERO,
            "ratio_span": INK_RATIO_SPAN,
            "background_kernel_mm": BACKGROUND_KERNEL_MM,
            "background_floor": BACKGROUND_FLOOR,
            "oversample": OVERSAMPLE,
            "edge_mask_px": EDGE_MASK_PX,
        },
        "area_mm": [AREA_X_MM, AREA_Y_MM, AREA_W_MM, AREA_H_MM],
    }
