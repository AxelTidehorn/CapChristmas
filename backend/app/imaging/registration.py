"""Find where the printed template sits in a photo: ArUco markers first, then a
cautious frame detection that is always sent to manual review, then manual corners."""
from dataclasses import dataclass, field

import cv2
import numpy as np

from .. import config as C
from .template import aruco_dictionary, frame_corners_mm, marker_corners_mm


@dataclass
class Registration:
    method: str                      # aruco | aruco3 | frame | manual | none
    homography: np.ndarray | None    # image px -> template mm
    corners: list | None             # frame corners in image px (TL, TR, BR, BL)
    markers_found: list = field(default_factory=list)
    reasons: list = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return self.method in ("aruco3", "frame", "none")


def _project(H: np.ndarray, pts) -> np.ndarray:
    return cv2.perspectiveTransform(np.asarray(pts, np.float64).reshape(-1, 1, 2), H).reshape(-1, 2)


def detect_markers(gray: np.ndarray) -> dict[int, np.ndarray]:
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    det = cv2.aruco.ArucoDetector(aruco_dictionary(), params)
    corners, ids, _ = det.detectMarkers(gray)
    found = {}
    if ids is not None:
        for c, i in zip(corners, ids.flatten()):
            i = int(i)
            if i in C.MARKERS_MM and i not in found:
                found[i] = c.reshape(4, 2).astype(np.float64)
    return found


def from_corners(corners) -> Registration:
    """Manual registration: four frame corners in image px, TL, TR, BR, BL."""
    src = np.asarray(corners, np.float64).reshape(4, 2)
    H = cv2.getPerspectiveTransform(src.astype(np.float32), frame_corners_mm().astype(np.float32)).astype(np.float64)
    return Registration("manual", H, src.tolist())


def _order_quad(pts: np.ndarray) -> np.ndarray:
    s, d = pts.sum(1), pts[:, 0] - pts[:, 1]
    return np.array([pts[np.argmin(s)], pts[np.argmax(d)], pts[np.argmax(s)], pts[np.argmin(d)]])


def detect_frame(gray: np.ndarray) -> np.ndarray | None:
    """Largest convex quadrilateral with roughly the frame's aspect ratio, or None."""
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.dilate(cv2.Canny(blur, 40, 120), np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    area_img = gray.shape[0] * gray.shape[1]
    want = C.FRAME_W_MM / C.FRAME_H_MM
    best, best_area = None, 0.0
    for c in contours:
        a = cv2.contourArea(c)
        if a < 0.15 * area_img or a <= best_area:
            continue
        approx = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        q = _order_quad(approx.reshape(4, 2).astype(np.float64))
        w = (np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[2] - q[3])) / 2
        h = (np.linalg.norm(q[3] - q[0]) + np.linalg.norm(q[2] - q[1])) / 2
        if h > 0 and abs(w / h - want) / want < 0.08:  # A4 page itself (0.71) must not match
            best, best_area = q, a
    return best


def register(gray: np.ndarray) -> Registration:
    found = detect_markers(gray)
    if len(found) >= 3:
        src = np.concatenate([found[i] for i in sorted(found)])
        dst = np.concatenate([marker_corners_mm(i) for i in sorted(found)])
        H, _ = cv2.findHomography(src, dst, 0)
        if H is not None:
            corners = _project(np.linalg.inv(H), frame_corners_mm()).tolist()
            if len(found) == 4:
                return Registration("aruco", H, corners, sorted(found))
            return Registration("aruco3", H, corners, sorted(found),
                                ["Endast 3 av 4 markörer hittades – kontrollera utsnittet."])
    quad = detect_frame(gray)
    if quad is not None:
        reg = from_corners(quad)
        reg.method, reg.markers_found = "frame", sorted(found)
        reg.reasons = ["Markörer saknas – ritramen hittades automatiskt. Kontrollera hörnen."]
        return reg
    return Registration("none", None, None, sorted(found),
                        ["Kunde inte hitta markörer eller ritram. Sätt fyra hörn manuellt eller uteslut."])


def warp_area(gray: np.ndarray, H: np.ndarray, oversample: int = C.OVERSAMPLE):
    """Warp the exact drawing area to the canvas (x oversample).
    Returns (warped grey float32 0..1, fraction of canvas outside the photo)."""
    s = C.CANVAS_W * oversample / C.AREA_W_MM
    A = np.array([[s, 0, -C.AREA_X_MM * s], [0, s, -C.AREA_Y_MM * s], [0, 0, 1]], np.float64)
    M = A @ H
    size = (C.CANVAS_W * oversample, C.CANVAS_H * oversample)
    warped = cv2.warpPerspective(gray, M, size, flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=255)
    inside = cv2.warpPerspective(np.full(gray.shape, 255, np.uint8), M, size,
                                 flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return warped.astype(np.float32) / 255.0, float(np.mean(inside == 0))
