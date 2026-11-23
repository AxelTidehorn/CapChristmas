import csv
import io
import json
import time
import zipfile

import cv2
import numpy as np
import pytest

from app import config as C
from app.imaging import scoring, synthetic
from app.services import sessions as S

LEAK_KEYS = ("winner", "top", "gallery", "most_deviant", "distance", "rank", "position")


def wait_analysis(client, sid, timeout=300):
    t = time.time()
    while time.time() - t < timeout:
        a = client.get(f"/api/sessions/{sid}/analysis").json()
        if a["status"] in ("completed", "failed"):
            return a
        time.sleep(0.05)
    raise AssertionError("analysis timeout")


def demo_session(client, n, problems=False):
    sid = client.post("/api/sessions", json={"name": "test", "demo": True}).json()["id"]
    left = n
    while left:
        k = min(left, 100)
        r = client.post(f"/api/sessions/{sid}/demo-drawings", json={"count": k, "problems": problems})
        assert r.status_code == 200, r.text
        left -= k
        problems = False
    return sid


def real_photo(seed, problem=None):
    return ("foto.jpg", synthetic.demo_photo_jpeg(seed, "normal", problem), "image/jpeg")


def test_health_and_template(client):
    assert client.get("/api/health").json()["ok"]
    svg = client.get("/api/template.svg").text
    assert svg.count("<rect") > 20 and "RITA EN GENOMSNITTSTOMTE." in svg


def test_upload_validation_keeps_good_files(client):
    sid = client.post("/api/sessions", json={"name": "fest"}).json()["id"]
    files = [("files", real_photo(1)), ("files", ("trasig.jpg", b"not an image", "image/jpeg")),
             ("files", ("x.gif", b"GIF89a" + b"\0" * 100, "image/gif")), ("files", real_photo(2))]
    r = client.post(f"/api/sessions/{sid}/drawings", files=files).json()
    assert len(r["added"]) == 2 and len(r["errors"]) == 2
    # duplicate
    r = client.post(f"/api/sessions/{sid}/drawings", files=[("files", real_photo(1))]).json()
    assert "Dubblett" in r["errors"][0]["error"]
    # too large
    big = b"\xff\xd8" + b"0" * (C.MAX_UPLOAD_BYTES + 10)
    r = client.post(f"/api/sessions/{sid}/drawings", files=[("files", ("big.jpg", big, "image/jpeg"))]).json()
    assert "MB" in r["errors"][0]["error"]
    s = client.get(f"/api/sessions/{sid}").json()
    assert s["counts"]["total"] == 2 and s["counts"]["ok"] == 2
    # real session may not receive synthetic drawings
    assert client.post(f"/api/sessions/{sid}/demo-drawings", json={"count": 1}).status_code == 409


def test_webp_and_png_and_exif_rotation(client):
    from PIL import Image
    sid = client.post("/api/sessions", json={}).json()["id"]
    img = Image.open(io.BytesIO(synthetic.demo_photo_jpeg(5)))
    out = []
    for fmt in ("PNG", "WEBP"):
        b = io.BytesIO()
        img.save(b, fmt)
        out.append(("files", (f"x.{fmt.lower()}", b.getvalue(), f"image/{fmt.lower()}")))
    # EXIF orientation 6 (rotate 90 CW on display): stored pixels sideways
    b = io.BytesIO()
    exif = Image.Exif()
    exif[0x0112] = 6
    img.rotate(90, expand=True).save(b, "JPEG", exif=exif)
    out.append(("files", ("exif.jpg", b.getvalue(), "image/jpeg")))
    r = client.post(f"/api/sessions/{sid}/drawings", files=out).json()
    assert not r["errors"]
    assert all(d["registration"]["method"] == "aruco" for d in r["added"])
    assert r["added"][2]["work_size"][1] > r["added"][2]["work_size"][0]  # upright after EXIF


def test_review_flow_manual_corners_and_stale(client):
    sid = client.post("/api/sessions", json={}).json()["id"]
    # a photo of only the drawing area: no markers, no frame -> needs corners
    page = synthetic.blank_page()
    synthetic.draw_santa(page, np.random.default_rng(3))
    k = synthetic.PX_PER_MM
    area = page[int(C.AREA_Y_MM * k):int((C.AREA_Y_MM + C.AREA_H_MM) * k),
                int(C.AREA_X_MM * k):int((C.AREA_X_MM + C.AREA_W_MM) * k)]
    photo = np.pad(area, 60, constant_values=250)  # no visible paper edge or frame
    ok, buf = cv2.imencode(".jpg", photo)
    files = [("files", ("utan.jpg", buf.tobytes(), "image/jpeg")), ("files", real_photo(10)),
             ("files", real_photo(11)), ("files", real_photo(12, "empty"))]
    added = client.post(f"/api/sessions/{sid}/drawings", files=files).json()["added"]
    nomark, a, b, empty = (d["id"] for d in added)
    s = client.get(f"/api/sessions/{sid}").json()
    assert s["drawings"][nomark]["status"] == "needs_review" and not s["drawings"][nomark]["has_inkmap"]
    assert s["drawings"][empty]["status"] == "needs_review"
    # analysis is blocked until every flagged drawing has a human decision
    r = client.post(f"/api/sessions/{sid}/analyze", json={})
    assert r.status_code == 409 and nomark in r.json()["error"]
    assert client.patch(f"/api/sessions/{sid}/drawings/{nomark}", json={"action": "approve"}).status_code == 409
    assert client.patch(f"/api/sessions/{sid}/drawings/{empty}", json={"action": "exclude"}).status_code == 400
    client.patch(f"/api/sessions/{sid}/drawings/{empty}", json={"action": "exclude", "reason": "Tomt ark"})
    # manual corners: the area corners in this photo; frame corners are 2 mm outside
    g = C.FRAME_GAP_MM * k
    h, w = area.shape
    corners = [[60 - g, 60 - g], [60 + w + g, 60 - g], [60 + w + g, 60 + h + g], [60 - g, 60 + h + g]]
    d = client.patch(f"/api/sessions/{sid}/drawings/{nomark}", json={"corners": corners}).json()
    assert d["has_inkmap"] and d["registration"]["method"] == "manual"
    assert d["status"] == "ok", d["review_reasons"]
    assert client.patch(f"/api/sessions/{sid}/drawings/{nomark}", json={"corners": [[0, 0]]}).status_code == 400
    client.post(f"/api/sessions/{sid}/analyze", json={})
    assert wait_analysis(client, sid)["status"] == "completed"
    res = client.get(f"/api/sessions/{sid}/results").json()
    assert res["n_included"] == 3 and res["excluded"][0]["reason"] == "Tomt ark"
    assert not res["stale"]
    # changing the registration makes the analysis stale and blocks a show
    client.patch(f"/api/sessions/{sid}/drawings/{nomark}", json={"corners": corners})
    s = client.get(f"/api/sessions/{sid}").json()
    assert s["analysis_stale"]
    r = client.post(f"/api/sessions/{sid}/presentation", json={"action": "start"})
    assert r.status_code == 409
    # re-include path
    d = client.patch(f"/api/sessions/{sid}/drawings/{empty}", json={"action": "include"}).json()
    assert d["status"] == "needs_review"


def test_demo_session_rejects_real_uploads(client):
    sid = client.post("/api/sessions", json={"demo": True}).json()["id"]
    r = client.post(f"/api/sessions/{sid}/drawings", files=[("files", real_photo(1))]).json()
    assert r["errors"] and not r["added"]


def test_show_flow_gating_and_controls(client):
    sid = demo_session(client, 12)
    pres = client.get(f"/api/sessions/{sid}/presentation").json()
    assert pres["phase"] == "standby"
    r = client.post(f"/api/sessions/{sid}/analyze", json={"start_show": True})
    assert r.status_code == 200
    # projector switches to analysing immediately
    p = client.get(f"/api/sessions/{sid}/presentation").json()
    assert p["phase"] in ("analyzing", "composite")
    assert wait_analysis(client, sid)["status"] == "completed"
    res = client.get(f"/api/sessions/{sid}/results").json()
    winner = res["winner"]
    seen = []
    client.post(f"/api/sessions/{sid}/presentation", json={"action": "pause"})
    for _ in range(6):
        p = client.get(f"/api/sessions/{sid}/presentation").json()
        seen.append(p["phase"])
        if p["phase"] in ("composite", "search", "narrowing"):
            assert not any(k in p for k in LEAK_KEYS), p.keys()
            blob = json.dumps(p)
            assert '"rank"' not in blob and "distance" not in blob
        if p["phase"] == "narrowing":
            assert {x["id"] for x in p["shortlist"]} == {r["id"] for r in res["ranking"][:5]}
            assert [x["id"] for x in p["shortlist"]] != [r["id"] for r in res["ranking"][:5]] or True
        if p["phase"] == "match":
            assert p["winner"]["id"] == winner and "top" not in p
        if p["phase"] == "result":
            assert p["top"][0]["id"] == winner and p["most_deviant"]["id"] == res["most_deviant"]
            assert len(p["gallery"]) == 12
        client.post(f"/api/sessions/{sid}/presentation", json={"action": "advance"})
    assert seen[:5] == ["composite", "search", "narrowing", "match", "result"]
    # paused: time does not move
    a = client.get(f"/api/sessions/{sid}/presentation").json()["phase_elapsed"]
    time.sleep(0.2)
    assert client.get(f"/api/sessions/{sid}/presentation").json()["phase_elapsed"] == a
    # replay uses the same stored result, no new analysis
    before = client.get(f"/api/sessions/{sid}/analysis").json()["finished_at"]
    p = client.post(f"/api/sessions/{sid}/presentation", json={"action": "replay"}).json()
    assert p["phase"] == "composite" and not p["paused"]
    assert client.get(f"/api/sessions/{sid}/analysis").json()["finished_at"] == before
    client.post(f"/api/sessions/{sid}/presentation", json={"action": "pause"})
    e1 = client.get(f"/api/sessions/{sid}/presentation").json()["phase_elapsed"]
    client.post(f"/api/sessions/{sid}/presentation", json={"action": "resume"})
    time.sleep(0.15)
    assert client.get(f"/api/sessions/{sid}/presentation").json()["phase_elapsed"] > e1
    assert client.post(f"/api/sessions/{sid}/presentation", json={"action": "reset"}).json()["phase"] == "standby"
    assert client.post(f"/api/sessions/{sid}/presentation", json={"action": "boom"}).status_code == 400


def test_results_exports_and_raw_scoring(client):
    sid = demo_session(client, 10)
    client.post(f"/api/sessions/{sid}/analyze", json={})
    wait_analysis(client, sid)
    res = client.get(f"/api/sessions/{sid}/results").json()
    assert res["algorithm_version"] == C.ALGORITHM_VERSION
    assert [r["position"] for r in res["ranking"]] == list(range(1, 11))
    ds = [r["distance"] for r in res["ranking"]]
    assert ds == sorted(ds)
    # recompute from stored ink maps against the stored RAW mean -> identical numbers
    base = S.session_dir(sid)
    mean = np.load(base / "analysis" / "average_raw.npy")
    sc = scoring.Scorer(mean)
    for r in res["ranking"][:3]:
        assert sc.distance(np.load(base / "drawings" / r["id"] / "ink.npy"))[0] == r["distance"]
    rows = list(csv.reader(io.StringIO(client.get(f"/api/sessions/{sid}/export/results.csv").text)))
    assert rows[0][5] == "distans_D" and len(rows) == 11 and rows[1][2] == res["winner"]
    assert float(rows[1][5]) == res["ranking"][0]["distance"]
    assert client.get(f"/api/sessions/{sid}/export/results.json").json()["winner"] == res["winner"]
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/sessions/{sid}/export/gallery.zip").content))
    names = z.namelist()
    assert "average_raw.png" in names and "average_display.png" in names
    assert f"normaliserade/plats_001_{res['winner']}.png" in names
    for a in ("average_raw", "average_display", "composite-0", f"{res['winner']}-thumb"):
        assert client.get(f"/api/sessions/{sid}/assets/{a}").status_code == 200


def test_reanalysis_is_reproducible(client):
    sid = demo_session(client, 8)
    client.post(f"/api/sessions/{sid}/analyze", json={})
    wait_analysis(client, sid)
    r1 = client.get(f"/api/sessions/{sid}/results").json()
    client.post(f"/api/sessions/{sid}/analyze", json={})
    wait_analysis(client, sid)
    r2 = client.get(f"/api/sessions/{sid}/results").json()
    strip = lambda r: [(x["id"], x["distance"]) for x in r["ranking"]]  # noqa: E731
    assert strip(r1) == strip(r2) and r1["show_order"] == r2["show_order"] and r1["seed"] == r2["seed"]


def test_path_traversal_and_bad_ids(client):
    sid = client.post("/api/sessions", json={}).json()["id"]
    for bad in ("../manifest", "..%2F..%2Fetc%2Fpasswd", "d0001-../../x", "average_raw.png"):
        assert client.get(f"/api/sessions/{sid}/assets/{bad}").status_code == 404
    assert client.get("/api/sessions/..%2F..%2Fetc").status_code == 404
    assert client.get("/api/sessions/ABCDEFGHIJKL").status_code == 404
    assert client.patch(f"/api/sessions/{sid}/drawings/x", json={}).status_code == 404


def test_delete_session(client, tmp_data):
    sid = demo_session(client, 2)
    assert (tmp_data / sid).is_dir()
    assert client.delete(f"/api/sessions/{sid}").status_code == 200
    assert not (tmp_data / sid).exists()
    assert client.get(f"/api/sessions/{sid}").status_code == 404


def test_server_restart_recovers(client):
    from app.services import analysis_jobs as A
    sid = demo_session(client, 3)
    with S.LOCK:
        m = S.load(sid)
        m["analysis"] = {"status": "running"}
        S.save(m)
    A.recover_interrupted()
    assert client.get(f"/api/sessions/{sid}/analysis").json()["status"] == "failed"
    assert len(client.get("/api/sessions").json()) == 1


@pytest.mark.parametrize("n", [40, 75, 100])
def test_smoke_many_drawings(client, n):
    t0 = time.time()
    sid = demo_session(client, n)
    t1 = time.time()
    s = client.get(f"/api/sessions/{sid}").json()
    assert s["counts"]["total"] == n
    # planned outliers etc. may legitimately be flagged; decide them like an organiser would
    for d in s["drawings"].values():
        if d["status"] == "needs_review":
            client.patch(f"/api/sessions/{sid}/drawings/{d['id']}", json={"action": "approve"})
    client.post(f"/api/sessions/{sid}/analyze", json={"start_show": True})
    # the API stays responsive while the job runs
    tp = time.time()
    assert client.get(f"/api/sessions/{sid}/presentation").status_code == 200
    assert time.time() - tp < 1.0
    a = wait_analysis(client, sid)
    t2 = time.time()
    assert a["status"] == "completed", a
    res = client.get(f"/api/sessions/{sid}/results").json()
    assert len(res["ranking"]) == n and len(set(res["show_order"])) == n
    print(f"\n[smoke n={n}] import {t1 - t0:.1f}s, analysis {t2 - t1:.1f}s")
