import cv2
import numpy as np
import pytest

from app import config as C
from app.imaging import average, normalization, registration, scoring, synthetic


# --- mean ---------------------------------------------------------------------------

def test_mean_exact_small_matrices():
    a = np.array([[0.0, 1.0], [0.5, 0.25]])
    b = np.array([[1.0, 1.0], [0.0, 0.75]])
    c = np.array([[0.5, 0.0], [1.0, 0.5]])
    expected = np.array([[0.5, 2 / 3], [0.5, 0.5]])
    assert np.allclose(average.mean_image([a, b, c]), expected, atol=1e-15)


def test_mean_requires_input():
    with pytest.raises(ValueError):
        average.mean_image([])


def test_display_enhance_is_separate_from_raw():
    m = np.full((10, 10), 0.1)
    m[5, 5] = 0.2
    d = average.display_enhance(m)
    assert d.max() == pytest.approx(1.0) and m.max() == pytest.approx(0.2)


# --- scoring ------------------------------------------------------------------------

def _blob(cx, cy, r=60, shape=(C.CANVAS_H, C.CANVAS_W)):
    img = np.zeros(shape, np.float32)
    cv2.circle(img, (cx, cy), r, 1.0, 6)
    return img


def test_identical_images_score_equal_and_tie_break_by_id():
    imgs = {"d0003": _blob(256, 320), "d0001": _blob(256, 320), "d0002": _blob(100, 100)}
    mean = average.mean_image(imgs.values())
    sc = scoring.Scorer(mean)
    dist = {k: sc.distance(v)[0] for k, v in imgs.items()}
    assert dist["d0001"] == dist["d0003"]
    ranking = scoring.rank(dist)
    assert [r["id"] for r in ranking] == ["d0001", "d0003", "d0002"]
    assert ranking[0]["tied"] and ranking[1]["tied"] and ranking[0]["rank"] == ranking[1]["rank"] == 1
    assert ranking[1]["position"] == 2 and not ranking[2]["tied"]
    # stable regardless of input order
    assert scoring.rank(dict(reversed(list(dist.items())))) == ranking


def test_controlled_outlier_ranks_last_and_near_mean_wins():
    imgs = {f"d{i:04d}": _blob(256 + d, 320 + d) for i, d in enumerate([-8, -4, 0, 4, 8], 1)}
    imgs["d0099"] = _blob(80, 80, r=30)
    mean = average.mean_image(imgs.values())
    sc = scoring.Scorer(mean)
    ranking = scoring.rank({k: sc.distance(v)[0] for k, v in imgs.items()})
    assert ranking[-1]["id"] == "d0099"
    assert ranking[0]["id"] == "d0003"  # the centred one


def test_scoring_is_deterministic():
    rng = np.random.default_rng(1)
    imgs = [rng.random((C.CANVAS_H, C.CANVAS_W)).astype(np.float32) for _ in range(3)]
    m = average.mean_image(imgs)
    assert scoring.Scorer(m).distance(imgs[0]) == scoring.Scorer(m).distance(imgs[0])


def test_display_enhancement_would_change_scores_so_it_must_not_be_used():
    """Guards the contract: scores are against raw M; display M gives different numbers."""
    imgs = [_blob(256, 320), _blob(260, 330), _blob(200, 300)]
    m = average.mean_image(imgs)
    raw = scoring.Scorer(m).distance(imgs[0])[0]
    disp = scoring.Scorer(average.display_enhance(m)).distance(imgs[0])[0]
    assert raw != disp


def test_near_empty_drawing_risk_is_flagged():
    """Known V1 risk: a nearly empty sheet can sit close to a pale mean. It must be flagged."""
    ink = np.zeros((C.CANVAS_H, C.CANVAS_W), np.float32)
    ink[300:302, 250:262] = 1.0
    _, reasons = normalization.quality(ink)
    assert any("Tomt" in r for r in reasons)


# --- registration / normalisation ---------------------------------------------------------

def _ground_truth(page):
    k = synthetic.PX_PER_MM
    x, y, w, h = (int(round(v * k)) for v in (C.AREA_X_MM, C.AREA_Y_MM, C.AREA_W_MM, C.AREA_H_MM))
    crop = page[y:y + h, x:x + w].astype(np.float32) / 255
    gt = cv2.resize(1 - crop, (C.CANVAS_W, C.CANVAS_H), interpolation=cv2.INTER_AREA)
    e = C.EDGE_MASK_PX
    gt[:e], gt[-e:], gt[:, :e], gt[:, -e:] = 0, 0, 0, 0
    return gt


def _register_ink(photo_bgr):
    gray = cv2.cvtColor(photo_bgr, cv2.COLOR_BGR2GRAY)
    reg = registration.register(gray)
    warped, outside = registration.warp_area(gray, reg.homography)
    return reg, normalization.ink_map(warped), outside


@pytest.mark.parametrize("rotate", [0, 8, -14, 90, 180, 270])
def test_aruco_registration_recovers_drawing(rotate):
    rng = np.random.default_rng(rotate + 100)
    page = synthetic.blank_page()
    synthetic.draw_santa(page, rng)
    sideways = rotate in (90, 270)  # whole photo turned, e.g. phone held in landscape
    photo = synthetic.photograph(page, rng, rotate=0 if sideways else rotate)
    if sideways:
        photo = np.ascontiguousarray(np.rot90(photo, rotate // 90))
    reg, ink, outside = _register_ink(photo)
    assert reg.method == "aruco" and reg.markers_found == [0, 1, 2, 3]
    assert outside == 0
    gt = _ground_truth(page)
    g = lambda x: cv2.GaussianBlur(x, (0, 0), 3)  # noqa: E731
    corr = np.corrcoef(g(ink).ravel(), g(gt).ravel())[0, 1]
    assert corr > 0.9, corr
    # geometry: bounding box of the strokes within ~1 mm (3 px) of ground truth
    def bbox(x):
        ys, xs = np.nonzero(x > 0.3)
        return np.array([ys.min(), ys.max(), xs.min(), xs.max()])
    assert np.abs(bbox(ink) - bbox(gt)).max() <= 3


def test_template_text_frame_and_markers_do_not_leak():
    rng = np.random.default_rng(5)
    photo = synthetic.photograph(synthetic.blank_page(), rng)
    reg, ink, _ = _register_ink(photo)
    assert reg.method == "aruco"
    assert float(ink.max()) < 0.15
    assert float(ink.mean()) < 1e-3


def test_empty_sheet_flagged_not_dropped():
    jpg = synthetic.demo_photo_jpeg(3, problem="empty")
    img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
    _, ink, outside = _register_ink(img)
    _, reasons = normalization.quality(ink, outside)
    assert reasons and "Tomt" in reasons[0]


def test_blurred_photo_flagged():
    rng = np.random.default_rng(1)
    page = synthetic.blank_page()
    synthetic.draw_santa(page, rng)
    gray = cv2.cvtColor(synthetic.photograph(page, rng, blur=6), cv2.COLOR_BGR2GRAY)
    reg = registration.register(gray)
    _, reasons = normalization.quality(normalization.ink_map(registration.warp_area(gray, reg.homography)[0]))
    assert reg.needs_review or any("suddig" in r for r in reasons)


def test_missing_markers_fall_back_to_frame_with_review():
    jpg = synthetic.demo_photo_jpeg(11, problem="no_markers")
    gray = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_GRAYSCALE)
    reg = registration.register(gray)
    assert reg.method == "frame" and reg.needs_review and len(reg.corners) == 4


def test_manual_corners_match_marker_registration():
    rng = np.random.default_rng(9)
    page = synthetic.blank_page()
    synthetic.draw_santa(page, rng)
    gray = cv2.cvtColor(synthetic.photograph(page, rng), cv2.COLOR_BGR2GRAY)
    auto = registration.register(gray)
    manual = registration.from_corners(auto.corners)
    a = normalization.ink_map(registration.warp_area(gray, auto.homography)[0])
    b = normalization.ink_map(registration.warp_area(gray, manual.homography)[0])
    assert np.abs(a - b).mean() < 0.01


def test_cropped_photo_flagged():
    rng = np.random.default_rng(4)
    page = synthetic.blank_page()
    synthetic.draw_santa(page, rng)
    gray = cv2.cvtColor(synthetic.photograph(page, rng, rotate=0, strength=0.2), cv2.COLOR_BGR2GRAY)
    auto = registration.register(gray)
    corners = np.array(auto.corners)
    corners[:, 0] += 0.25 * (corners[:, 0].max() - corners[:, 0].min())  # shift frame partly off-image
    corners[:, 0] = corners[:, 0] + gray.shape[1] * 0.3
    reg = registration.from_corners(corners)
    _, outside = registration.warp_area(gray, reg.homography)
    _, reasons = normalization.quality(np.zeros((C.CANVAS_H, C.CANVAS_W), np.float32), outside)
    assert outside > 0.05 and any("beskuret" in r for r in reasons)
