"""Background analysis: real mean image, progressive composites, scoring, ranking, exports."""
import csv
import hashlib
import io
import json
import traceback
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

from .. import config as C
from ..imaging import average, normalization, scoring
from . import sessions as S

EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis")


def _progress(sid: str, **fields) -> None:
    with S.LOCK:
        m = S.load(sid)
        m["analysis"].update(fields)
        if "log" in fields:
            m["analysis"]["log"] = fields["log"][-12:]
        S.save(m)


def start(sid: str, start_show: bool) -> dict:
    with S.LOCK:
        m = S.load(sid)
        from .ai_jobs import assert_idle
        assert_idle(m)
        m["result_mode"] = "legacy"
        if m["analysis"].get("status") in ("queued", "running"):
            raise S.ApiError(409, "En analys pågår redan.")
        pending = [d["id"] for d in m["drawings"].values() if d["status"] == "needs_review"]
        if pending:
            raise S.ApiError(409, "Granska först (godkänn, rätta eller uteslut): " + ", ".join(pending))
        included = [d for d in m["drawings"].values() if d["status"] == "ok" and d["has_inkmap"]]
        if len(included) < 2:
            raise S.ApiError(409, "Minst två godkända bidrag krävs.")
        m["analysis"] = {"status": "queued", "step": "I kö", "done": 0, "total": len(included),
                         "revision": m["revision"], "queued_at": S.now(), "log": ["Analys köad."]}
        # A new analysis replaces the old results, so any running show goes back to standby.
        m["presentation"] = {"mode": "analyzing"} if start_show else {"mode": "standby"}
        S.save(m)
    EXECUTOR.submit(_run_safe, sid, [d["id"] for d in included], m["revision"])
    return m["analysis"]


def _run_safe(sid: str, ids: list[str], revision: int) -> None:
    try:
        _run(sid, ids, revision)
    except Exception as e:  # visible failure, never a silent half-result
        traceback.print_exc()
        try:
            _progress(sid, status="failed", step="Analysen misslyckades", error=f"{type(e).__name__}: {e}")
        except S.ApiError:
            pass  # session deleted mid-run


def stage_counts(n: int, stages: int = C.COMPOSITE_STAGES) -> list[int]:
    return sorted({max(1, round(n ** (k / (stages - 1)))) for k in range(stages)} | {n})


def _png(path, ink: np.ndarray) -> None:
    cv2.imwrite(str(path), normalization.ink_to_png_array(ink))


def _run(sid: str, ids: list[str], revision: int) -> None:
    m = S.load(sid)
    base = S.session_dir(sid)
    out = base / "analysis"
    out.mkdir(exist_ok=True)
    for f in [*out.glob("composite-*.png"), out / "results.json", out / "results.csv"]:
        f.unlink(missing_ok=True)
    drawings = {i: m["drawings"][i] for i in ids}
    n = len(ids)
    log = [f"{n} godkända bidrag, {sum(d['status'] == 'excluded' for d in m['drawings'].values())} uteslutna."]
    _progress(sid, status="running", step="Verifierar indata", started_at=S.now(), log=log)

    # Deterministic show order, seeded by the exact input set (not by time or chance).
    h = hashlib.sha256(C.ALGORITHM_VERSION.encode())
    for i in sorted(ids):
        h.update(drawings[i]["sha256"].encode())
    seed = int.from_bytes(h.digest()[:8], "big")
    rng = np.random.default_rng(seed)
    show_order = [ids[i] for i in rng.permutation(n)]

    def ink(did):
        return np.load(base / "drawings" / did / "ink.npy")

    # 1) mean image, streamed in show order, with progressive composites for the show
    log.append("Beräknar pixelmedelvärde M = (1/N) Σ I_i")
    targets = stage_counts(n)
    stages, total = [], None
    for k, did in enumerate(show_order, 1):
        total = ink(did).astype(np.float64) if total is None else total + ink(did)
        if k in targets:
            asset = f"composite-{len(stages)}"
            _png(out / f"{asset}.png", average.display_enhance(total / k))
            stages.append({"asset": asset, "count": k, "added": show_order[k - 1]})
        _progress(sid, step=f"Medelbild: {k}/{n}", done=k, total=2 * n, log=log)
    mean = total / n
    display = average.display_enhance(mean)
    _png(out / "average_raw.png", mean)
    _png(out / "average_display.png", display)
    np.save(out / "average_raw.npy", mean)

    # 2) scoring against the RAW mean only
    cfg = C.scoring_config()
    log.append("Flerskalig jämförelse σ = " + ", ".join(f"{s:g}" for s in cfg["sigmas_px"]) + " px")
    scorer = scoring.Scorer(mean)
    dist, comps = {}, {}
    for k, did in enumerate(show_order, 1):
        dist[did], comps[did] = scorer.distance(ink(did))
        _progress(sid, step=f"Avståndsmått: {k}/{n}", done=n + k, total=2 * n, log=log)

    # 3) ranking
    log.append("Rangordnar efter D (lägst = mest genomsnittlig)")
    _progress(sid, step="Rangordnar", log=log)
    ranking = scoring.rank(dist)
    for r in ranking:
        d = drawings[r["id"]]
        r.update(number=d["number"], label=d["label"], sha256=d["sha256"], components=comps[r["id"]],
                 registration=d["registration"]["method"], quality=d["quality"],
                 approved_with_reasons=d.get("approved_with_reasons", []))
    top = [r["id"] for r in ranking[:C.SHORTLIST_SIZE]]
    shortlist = [top[i] for i in rng.permutation(len(top))]
    excluded = [{"id": d["id"], "number": d["number"], "label": d["label"], "reason": d["exclude_reason"]}
                for d in m["drawings"].values() if d["status"] == "excluded"]
    results = {
        "session_id": sid, "demo": m["demo"], "revision": revision, "created_at": S.now(),
        "algorithm_version": C.ALGORITHM_VERSION, "config": cfg, "n_included": n,
        "seed": seed, "show_order": show_order, "shortlist": shortlist, "composite_stages": stages,
        "ranking": ranking, "winner": ranking[0]["id"], "most_deviant": ranking[-1]["id"],
        "excluded": excluded,
        "average_stats": {"mean": float(mean.mean()), "max": float(mean.max())},
    }
    S._write_json(out / "results.json", results)
    (out / "results.csv").write_text(results_csv(results), encoding="utf-8")

    with S.LOCK:
        m = S.load(sid)
        m["analysis"].update(status="completed", step="Analys klar", done=2 * n, total=2 * n,
                             finished_at=S.now(), log=(log + ["Analys klar."])[-12:])
        if m["presentation"].get("mode") == "analyzing":
            m["presentation"] = {"mode": "show", "anchor": S.now(), "paused_at": None}
        S.save(m)


def results_csv(results: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["placering", "rank", "bidrag_id", "nummer", "etikett", "distans_D", "mse_sigma_small",
                "mse_sigma_mid", "mse_sigma_large", "delad_placering", "sha256", "algoritm"])
    for r in results["ranking"]:
        w.writerow([r["position"], r["rank"], r["id"], r["number"], r["label"], repr(r["distance"]),
                    *[repr(c) for c in r["components"]], "ja" if r["tied"] else "", r["sha256"],
                    results["algorithm_version"]])
    for e in results["excluded"]:
        w.writerow(["", "", e["id"], e["number"], e["label"], "", "", "", "", f"UTESLUTEN: {e['reason']}", "",
                    results["algorithm_version"]])
    return buf.getvalue()


def load_results(sid: str) -> dict:
    if S.load(sid).get("result_mode") == "ai":
        from .ai_jobs import load_results as load_ai_results
        return load_ai_results(sid)
    p = S.session_dir(sid) / "analysis" / "results.json"
    if not p.is_file():
        raise S.ApiError(404, "Ingen analys finns ännu.")
    return json.loads(p.read_text(encoding="utf-8"))


def recover_interrupted() -> None:
    """At startup: a job that was running when the server stopped is marked failed."""
    for s in S.list_sessions():
        with S.LOCK:
            m = S.load(s["id"])
            if m["analysis"].get("status") in ("queued", "running"):
                m["analysis"].update(status="failed", step="Avbruten",
                                     error="Servern startades om under analysen. Kör analysen igen.")
                S.save(m)
