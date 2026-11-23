"""Local session storage: data/<session-id>/manifest.json + per-drawing files.

One process, one organiser: a single re-entrant lock serialises manifest changes and
manifests are written atomically (tmp + os.replace)."""
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from .. import config as C
from ..imaging import normalization, registration

LOCK = threading.RLock()
SESSION_ID_RE = re.compile(r"^[a-z0-9]{12}$")
DRAWING_ID_RE = re.compile(r"^d\d{4}$")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def now() -> float:
    return time.time()


def _write_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def session_dir(sid: str) -> Path:
    if not SESSION_ID_RE.match(sid or ""):
        raise ApiError(404, "Okänd session.")
    d = C.DATA_DIR / sid
    if not (d / "manifest.json").is_file():
        raise ApiError(404, "Okänd session.")
    return d


def load(sid: str) -> dict:
    with LOCK:
        return json.loads((session_dir(sid) / "manifest.json").read_text(encoding="utf-8"))


def save(m: dict) -> None:
    with LOCK:
        _write_json(C.DATA_DIR / m["id"] / "manifest.json", m)


def drawing_dir(sid: str, did: str) -> Path:
    if not DRAWING_ID_RE.match(did or ""):
        raise ApiError(404, "Okänt bidrag.")
    return session_dir(sid) / "drawings" / did


def create(name: str, demo: bool) -> dict:
    sid = secrets.token_hex(6)
    d = C.DATA_DIR / sid
    (d / "drawings").mkdir(parents=True)
    m = {
        "id": sid,
        "name": (name or "").strip()[:80] or ("Demo" if demo else "Julfest"),
        "demo": bool(demo),
        "created_at": now(),
        "revision": 0,
        "next_number": 1,
        "drawings": {},
        "analysis": {"status": "none"},
        "presentation": {"mode": "standby"},
    }
    save(m)
    return m


def list_sessions() -> list[dict]:
    out = []
    if C.DATA_DIR.is_dir():
        for d in C.DATA_DIR.iterdir():
            try:
                m = load(d.name)
            except (ApiError, OSError, ValueError):
                continue
            out.append({"id": m["id"], "name": m["name"], "demo": m["demo"], "created_at": m["created_at"],
                        "drawings": len(m["drawings"])})
    return sorted(out, key=lambda s: -s["created_at"])


def delete(sid: str) -> None:
    with LOCK:
        shutil.rmtree(session_dir(sid))


def counts(m: dict) -> dict:
    c = {"total": len(m["drawings"]), "ok": 0, "needs_review": 0, "excluded": 0}
    for d in m["drawings"].values():
        c[d["status"]] += 1
    return c


def analysis_stale(m: dict) -> bool:
    if m.get("result_mode") == "ai":
        from . import ai_jobs
        a = m.get("ai", {})
        # Missing approvals are unfinished work, not evidence that the input changed.
        if not a.get("match", {}).get("approval"):
            c = a.get("consensus")
            return bool(c and c["fingerprint"] != ai_jobs.fingerprint(m))
        try:
            ai_jobs.ready(m)
            return False
        except ApiError:
            return True
    a = m["analysis"]
    return a.get("status") == "completed" and a.get("revision") != m["revision"]


# --- Ingest -----------------------------------------------------------------------

def _decode(data: bytes) -> tuple[Image.Image, str]:
    if len(data) > C.MAX_UPLOAD_BYTES:
        raise ApiError(413, f"Filen är större än {C.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    if not data:
        raise ApiError(400, "Tom fil.")
    Image.MAX_IMAGE_PIXELS = C.MAX_IMAGE_PIXELS
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        if fmt not in C.ALLOWED_FORMATS:
            raise ApiError(415, "Endast JPG, PNG och WebP stöds.")
        img.load()
    except ApiError:
        raise
    except Exception:  # PIL raises many types for broken/bomb files
        raise ApiError(400, "Bilden kunde inte läsas (trasig eller ogiltig fil).")
    img = ImageOps.exif_transpose(img).convert("RGB")
    return img, C.ALLOWED_FORMATS[fmt]


def _process(ddir: Path, gray: np.ndarray, reg: registration.Registration) -> dict:
    """Run warp + ink map for a registration; writes ink.npy and preview.png."""
    result = {"registration": {"method": reg.method, "corners": reg.corners, "markers_found": reg.markers_found}}
    reasons = list(reg.reasons)
    if reg.homography is None:
        for f in ("ink.npy", "preview.png"):
            (ddir / f).unlink(missing_ok=True)
        result.update(has_inkmap=False, quality={}, review_reasons=reasons)
        return result
    warped, outside = registration.warp_area(gray, reg.homography)
    ink = normalization.ink_map(warped)
    metrics, q_reasons = normalization.quality(ink, outside)
    np.save(ddir / "ink.npy", ink)
    cv2.imwrite(str(ddir / "preview.png"), normalization.ink_to_png_array(ink))
    result.update(has_inkmap=True, quality=metrics, review_reasons=reasons + q_reasons)
    return result


def _status_for(processed: dict) -> str:
    return "ok" if processed["has_inkmap"] and not processed["review_reasons"] else "needs_review"


def add_drawing(sid: str, filename: str, data: bytes, synthetic: bool = False) -> dict:
    m = load(sid)
    from .ai_jobs import assert_idle
    assert_idle(m)
    if m["demo"] != synthetic:
        raise ApiError(409, "Demo- och tävlingsbidrag kan inte blandas i samma session.")
    if len(m["drawings"]) >= C.MAX_DRAWINGS:
        raise ApiError(409, f"Max {C.MAX_DRAWINGS} bidrag per session.")
    sha = hashlib.sha256(data).hexdigest()
    for d in m["drawings"].values():
        if d["sha256"] == sha:
            raise ApiError(409, f"Dubblett av {d['id']} – samma fil är redan uppladdad.")
    img, ext = _decode(data)
    with LOCK:  # reserve id
        m = load(sid)
        number = m["next_number"]
        m["next_number"] += 1
        save(m)
    did = f"d{number:04d}"
    ddir = session_dir(sid) / "drawings" / did
    ddir.mkdir(parents=True)
    (ddir / f"original.{ext}").write_bytes(data)
    scale = min(1.0, C.WORK_MAX_SIDE / max(img.size))
    if scale < 1:
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    img.save(ddir / "work.jpg", quality=92)
    thumb = img.copy()
    thumb.thumbnail((C.THUMB_MAX_SIDE, C.THUMB_MAX_SIDE))
    thumb.save(ddir / "thumb.jpg", quality=85)
    gray = np.array(img.convert("L"))
    del img
    try:
        processed = _process(ddir, gray, registration.register(gray))
    except Exception as e:  # keep the upload; the organiser can set corners or exclude
        processed = {"registration": {"method": "none", "corners": None, "markers_found": []},
                     "has_inkmap": False, "quality": {},
                     "review_reasons": [f"Bearbetningen misslyckades ({type(e).__name__}). Sätt hörn manuellt."]}
    entry = {
        "id": did, "number": number, "label": "", "filename": os.path.basename(filename or "")[:120],
        "original_ext": ext, "sha256": sha, "uploaded_at": now(), "synthetic": synthetic,
        "work_size": [gray.shape[1], gray.shape[0]], "exclude_reason": "",
        **processed, "status": _status_for(processed),
    }
    with LOCK:
        m = load(sid)
        m["drawings"][did] = entry
        m["revision"] += 1
        m["presentation"] = {"mode": "standby"}
        save(m)
    return entry


def update_drawing(sid: str, did: str, patch: dict) -> dict:
    ddir = drawing_dir(sid, did)
    with LOCK:
        m = load(sid)
        from .ai_jobs import assert_idle
        assert_idle(m)
        if did not in m["drawings"]:
            raise ApiError(404, "Okänt bidrag.")
        d = m["drawings"][did]
    changed = False
    if "corners" in patch:
        corners = patch["corners"]
        w, h = d["work_size"]
        try:
            pts = np.asarray(corners, np.float64).reshape(4, 2)
        except (ValueError, TypeError):
            raise ApiError(400, "Ange exakt fyra hörn [[x,y],...].")
        if not np.all(np.isfinite(pts)) or (pts < -w).any() or (pts[:, 0] > 2 * w).any() or (pts[:, 1] > 2 * h).any():
            raise ApiError(400, "Hörnen ligger utanför bilden.")
        if cv2.contourArea(pts.astype(np.float32)) < 0.01 * w * h:
            raise ApiError(400, "Hörnen bildar ingen giltig yta.")
        gray = cv2.imread(str(ddir / "work.jpg"), cv2.IMREAD_GRAYSCALE)
        processed = _process(ddir, gray, registration.from_corners(pts))
        d.update(processed)
        if d["status"] != "excluded":
            d["status"] = _status_for(processed)
        changed = True
    if "label" in patch:
        d["label"] = str(patch["label"] or "").strip()[:60]
    action = patch.get("action")
    if action == "approve":
        if not d["has_inkmap"]:
            raise ApiError(409, "Bidraget saknar registrering – sätt hörn först.")
        d["status"], d["exclude_reason"], changed = "ok", "", True
        d["approved_with_reasons"] = d.get("review_reasons", [])
    elif action == "exclude":
        reason = str(patch.get("reason") or "").strip()[:200]
        if not reason:
            raise ApiError(400, "Ange en anledning för uteslutning.")
        d["status"], d["exclude_reason"], changed = "excluded", reason, True
    elif action == "include":
        d["status"], d["exclude_reason"], changed = _status_for(d), "", True
    elif action is not None:
        raise ApiError(400, "Okänd åtgärd.")
    with LOCK:
        m = load(sid)
        m["drawings"][did] = d
        if changed:
            m["revision"] += 1
            m["presentation"] = {"mode": "standby"}
        save(m)
    return d


def asset_path(sid: str, asset_id: str) -> Path:
    """Whitelisted asset ids only; no user-controlled path segments reach the filesystem."""
    base = session_dir(sid)
    mt = re.fullmatch(r"(d\d{4})-(thumb|preview|work|original)", asset_id or "")
    if mt:
        did, kind = mt.groups()
        m = load(sid)
        if did not in m["drawings"]:
            raise ApiError(404, "Okänd bild.")
        name = {"thumb": "thumb.jpg", "preview": "preview.png", "work": "work.jpg",
                "original": f"original.{m['drawings'][did]['original_ext']}"}[kind]
        p = base / "drawings" / did / name
    elif re.fullmatch(r"ai-[a-f0-9]{32}", asset_id or ""):
        p = base / "ai" / f"{asset_id}.png"
    elif re.fullmatch(r"average_raw|average_display", asset_id or ""):
        p = base / "analysis" / f"{asset_id}.png"
    elif re.fullmatch(r"composite-\d{1,3}", asset_id or ""):
        p = base / "analysis" / f"{asset_id}.png"
    else:
        raise ApiError(404, "Okänd bild.")
    if not p.is_file():
        raise ApiError(404, "Bilden finns inte (ännu).")
    return p
