"""MEDELTOMTEN – FastAPI app. Serves the API and the built frontend from one origin."""
import io
import zipfile
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

from . import config as C
from .imaging import template
from .services import analysis_jobs as A
from .services import presentation as P
from .services import sessions as S


@asynccontextmanager
async def lifespan(_: FastAPI):
    C.DATA_DIR.mkdir(parents=True, exist_ok=True)
    A.recover_interrupted()
    yield


app = FastAPI(title="MEDELTOMTEN", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)


@app.exception_handler(S.ApiError)
def _api_error(_: Request, e: S.ApiError):
    return JSONResponse({"error": e.message}, status_code=e.status)


def _session_out(sid: str) -> dict:
    m = S.load(sid)
    return {**m, "counts": S.counts(m), "analysis_stale": S.analysis_stale(m)}


# --- API ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"ok": True, "algorithm_version": C.ALGORITHM_VERSION}


@app.get("/api/template.svg")
def template_svg():
    return Response(template.render_svg(), media_type="image/svg+xml")


@app.get("/api/sessions")
def list_sessions():
    return S.list_sessions()


@app.post("/api/sessions")
def create_session(body: dict = Body(default={})):
    return _session_out(S.create(str(body.get("name") or ""), bool(body.get("demo"))).get("id"))


@app.get("/api/sessions/{sid}")
def get_session(sid: str):
    return _session_out(sid)


@app.delete("/api/sessions/{sid}")
def delete_session(sid: str):
    S.delete(sid)
    return {"deleted": sid}


@app.post("/api/sessions/{sid}/drawings")
def upload(sid: str, files: list[UploadFile] = File(...)):
    # Sync endpoint -> runs in FastAPI's threadpool, so the event loop (and the projector) stay responsive.
    added, errors = [], []
    for f in files:
        try:
            data = f.file.read(C.MAX_UPLOAD_BYTES + 1)
            added.append(S.add_drawing(sid, f.filename or "", data))
        except S.ApiError as e:
            if e.status == 404:
                raise
            errors.append({"filename": f.filename, "error": e.message})
    return {"added": added, "errors": errors}


@app.post("/api/sessions/{sid}/demo-drawings")
def demo_drawings(sid: str, body: dict = Body(default={})):
    from .imaging import synthetic
    m = S.load(sid)
    if not m["demo"]:
        raise S.ApiError(409, "Syntetiska teckningar kan bara skapas i en demosession.")
    count = int(body.get("count", 10))
    if not 1 <= count <= 100:
        raise S.ApiError(400, "Antal 1–100.")
    start = m["next_number"]
    added = []
    for i in range(count):
        n = start + i
        added.append(S.add_drawing(sid, f"syntetisk_{n:04d}.jpg",
                                   synthetic.demo_photo_jpeg(n * 7919, synthetic.kind_for(n)), synthetic=True))
    if body.get("problems"):
        for problem in ("empty", "no_markers"):
            n = S.load(sid)["next_number"]
            added.append(S.add_drawing(sid, f"syntetisk_{n:04d}_{problem}.jpg",
                                       synthetic.demo_photo_jpeg(n * 7919, "normal", problem), synthetic=True))
    return {"added": added, "errors": []}


@app.patch("/api/sessions/{sid}/drawings/{did}")
def patch_drawing(sid: str, did: str, body: dict = Body(...)):
    return S.update_drawing(sid, did, body)


@app.post("/api/sessions/{sid}/analyze")
def analyze(sid: str, body: dict = Body(default={})):
    return A.start(sid, bool(body.get("start_show")))


@app.get("/api/sessions/{sid}/analysis")
def analysis(sid: str):
    m = S.load(sid)
    return {**m["analysis"], "stale": S.analysis_stale(m)}


@app.get("/api/sessions/{sid}/results")
def results(sid: str):
    """Organiser view: full ranking. The projector never calls this."""
    m = S.load(sid)
    if m["analysis"].get("status") != "completed":
        raise S.ApiError(404, "Ingen färdig analys.")
    return {**A.load_results(sid), "stale": S.analysis_stale(m)}


@app.get("/api/sessions/{sid}/presentation")
def presentation(sid: str):
    return P.view(sid)


@app.post("/api/sessions/{sid}/presentation")
def presentation_cmd(sid: str, body: dict = Body(...)):
    return P.command(sid, str(body.get("action")))


@app.get("/api/sessions/{sid}/assets/{asset_id}")
def asset(sid: str, asset_id: str):
    return FileResponse(S.asset_path(sid, asset_id), headers={"Cache-Control": "no-cache"})


@app.get("/api/sessions/{sid}/export/{name}")
def export(sid: str, name: str):
    r = A.load_results(sid)
    base = S.session_dir(sid) / "analysis"
    if name == "results.json":
        return FileResponse(base / "results.json", filename=f"medeltomten_{sid}.json")
    if name == "results.csv":
        return FileResponse(base / "results.csv", media_type="text/csv", filename=f"medeltomten_{sid}.csv")
    if name == "gallery.zip":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in ("results.json", "results.csv", "average_raw.png", "average_display.png"):
                z.write(base / f, f)
            for row in r["ranking"]:
                p = S.session_dir(sid) / "drawings" / row["id"] / "preview.png"
                z.write(p, f"normaliserade/plats_{row['position']:03d}_{row['id']}.png")
        return Response(buf.getvalue(), media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="medeltomten_{sid}.zip"'})
    raise S.ApiError(404, "Okänd export.")


# --- Frontend (built Vite app, same origin) ------------------------------------------

@app.get("/")
def root():
    return RedirectResponse("/control")


@app.get("/{path:path}")
def spa(path: str):
    if path.startswith("api/"):
        raise S.ApiError(404, "Okänd endpoint.")
    dist = C.FRONTEND_DIST.resolve()
    f = (dist / path).resolve()
    if path and f.is_file() and f.is_relative_to(dist):
        return FileResponse(f)
    index = dist / "index.html"
    if not index.is_file():
        return Response("Frontend är inte byggd. Kör scripts/start (bygger frontend) eller npm run build.",
                        status_code=503, media_type="text/plain; charset=utf-8")
    return FileResponse(index, headers={"Cache-Control": "no-cache"})
