"""Server-held show state. The projector only ever receives data for the phase it is in,
so a reload (or a curious look at the network tab) cannot reveal the winner early."""
from .. import config as C
from . import analysis_jobs as A
from . import sessions as S

PHASES = [p for p, _ in C.SHOW_PHASES]
DURATIONS = [d for _, d in C.SHOW_PHASES]
STARTS = [sum(d for d in DURATIONS[:i]) for i in range(len(PHASES))]


def _elapsed(p: dict, t: float) -> float:
    return (p["paused_at"] if p.get("paused_at") is not None else t) - p["anchor"]


def _phase_at(elapsed: float) -> int:
    idx = 0
    for i, start in enumerate(STARTS):
        if elapsed >= start:
            idx = i
    return idx


def _ready(m: dict) -> None:
    if m["analysis"].get("status") != "completed":
        raise S.ApiError(409, "Ingen färdig analys att visa.")
    if S.analysis_stale(m):
        raise S.ApiError(409, "Bidragen har ändrats sedan analysen – beräkna igen före showen.")


def command(sid: str, action: str) -> dict:
    with S.LOCK:
        m = S.load(sid)
        p, t = m["presentation"], S.now()
        if action in ("start", "replay"):
            _ready(m)
            p = {"mode": "show", "anchor": t, "paused_at": None}
        elif action == "reset":
            p = {"mode": "standby"}
        elif action in ("pause", "resume", "advance"):
            if p.get("mode") != "show":
                raise S.ApiError(409, "Showen är inte igång.")
            if action == "pause" and p["paused_at"] is None:
                p["paused_at"] = t
            elif action == "resume" and p["paused_at"] is not None:
                p["anchor"] += t - p["paused_at"]
                p["paused_at"] = None
            elif action == "advance":
                idx = _phase_at(_elapsed(p, t))
                if idx + 1 < len(PHASES):
                    ref = p["paused_at"] if p["paused_at"] is not None else t
                    p["anchor"] = ref - STARTS[idx + 1]
        else:
            raise S.ApiError(400, "Okänd åtgärd.")
        m["presentation"] = p
        S.save(m)
    return view(sid)


def _who(d: dict) -> dict:
    return {"id": d["id"], "number": d["number"], "label": d["label"]}


def view(sid: str) -> dict:
    """Public, phase-gated projector payload."""
    m = S.load(sid)
    p, t = m["presentation"], S.now()
    out = {"session_id": sid, "demo": m["demo"], "mode": p.get("mode", "standby"), "phase": "standby",
           "paused": False, "phase_elapsed": 0.0, "phase_duration": None}
    if out["mode"] == "analyzing":
        a = m["analysis"]
        out["phase"] = "analyzing"
        out["analysis"] = {k: a.get(k) for k in ("status", "step", "done", "total", "log", "error")}
        out["n_uploaded"] = len(m["drawings"])
        return out
    if out["mode"] != "show":
        return out
    r = A.load_results(sid)
    el = _elapsed(p, t)
    idx = _phase_at(el)
    phase = PHASES[idx]
    out.update(phase=phase, paused=p.get("paused_at") is not None, phase_elapsed=el - STARTS[idx],
               phase_duration=DURATIONS[idx], n=r["n_included"], result_key=str(r["created_at"]))
    info = {d["id"]: _who(m["drawings"][d["id"]]) if d["id"] in m["drawings"] else {"id": d["id"]}
            for d in r["ranking"]}
    if phase == "composite":
        out["stages"] = [{"asset": s["asset"], "count": s["count"], "added": info[s["added"]]}
                         for s in r["composite_stages"]]
        out["order"] = [info[i] for i in r["show_order"]]
    elif phase == "search":
        out["candidates"] = [info[i] for i in r["show_order"]]
    elif phase == "narrowing":
        out["shortlist"] = [info[i] for i in r["shortlist"]]
    elif phase in ("match", "result"):
        out["winner"] = info[r["winner"]]
        out["winner_tied"] = r["ranking"][0]["tied"]
    if phase == "result":
        def row(x):
            return {**info[x["id"]], "position": x["position"], "rank": x["rank"], "distance": x["distance"],
                    "tied": x["tied"]}
        out["top"] = [row(x) for x in r["ranking"][:5]]
        out["most_deviant"] = row(r["ranking"][-1])
        out["gallery"] = [row(x) for x in r["ranking"]]
        out["excluded_count"] = len(r["excluded"])
        out["method"] = {"algorithm_version": r["algorithm_version"], "sigmas_px": r["config"]["sigmas_px"],
                         "weights": r["config"]["weights"], "canvas": r["config"]["canvas"]}
    return out
