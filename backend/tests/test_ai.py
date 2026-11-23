"""Offline V2 orchestration + real HTTP contract checks. NO claim of live model quality.

The scripted provider is injected only in tests, never selectable in the shipped app.
"""
import base64
import hashlib
import io
import json
import threading
import time
import zipfile

import cv2
import httpx
import numpy as np
import pytest
from PIL import Image

from app.ai import providers as B
from app.ai.models import Comparison, FEATURES, Observation, Observations
from app.services import ai_jobs as V, sessions as S


def observation(did, composition="head_only", accessories=False):
    return Observation(id=did, composition=composition, pose="front", hat_shape="drooping", beard_shape="long",
                       head_fraction=.45 if composition == "head_only" else .18,
                       width_height_ratio=.7 if composition == "head_only" else .4,
                       features=[{"key": k, "presence": "yes" if k in ("hat", "beard", "nose", "eyes") or
                                  (composition == "full_body" and k in ("torso", "arms", "legs")) or
                                  (accessories and k == "accessories") else "no", "notes": "Observerad form"} for k in FEATURES],
                       description="Långt skägg och hängande mössa.")


def png(ink):
    b = io.BytesIO()
    Image.fromarray(np.uint8(255 * (1 - ink))).save(b, "PNG")
    return b.getvalue()


def dataset(n):
    """Fast normalized synthetic inputs; V1 tests separately exercise camera/import/ArUco at scale."""
    m = S.create("V2 technical test", True)
    images = {}
    for i in range(1, n + 1):
        did = f"d{i:04d}"
        ink = np.zeros((640, 512), np.float32)
        cv2.circle(ink, (250 + i % 15, 260), 65 + i % 20, 1, 3)
        cv2.line(ink, (170, 220), (250 + i % 12, 100 + i), 1, 4)
        cv2.line(ink, (250 + i % 12, 100 + i), (330, 220), 1, 3)
        cv2.line(ink, (190, 300), (250, 440), 1, 3)
        cv2.line(ink, (250, 440), (310, 300), 1, 3)
        if i > n - max(1, n // 10):
            cv2.line(ink, (250, 440), (250, 580), 1, 3)
            cv2.circle(ink, (380, 500), 30, 1, 3)
        data = png(ink)
        path = S.drawing_dir(m["id"], did)
        path.mkdir()
        (path / "preview.png").write_bytes(data)
        (path / "original.png").write_bytes(data)
        im = Image.open(io.BytesIO(data)).convert("RGB")
        im.save(path / "work.jpg")
        im.thumbnail((240, 240))
        im.save(path / "thumb.jpg")
        np.save(path / "ink.npy", ink)
        images[hashlib.sha256(data).hexdigest()] = did
        m["drawings"][did] = {"id": did, "number": i, "label": "", "sha256": hashlib.sha256(data).hexdigest(),
                               "status": "ok", "has_inkmap": True, "exclude_reason": "", "original_ext": "png", "work_size": [512, 640],
                               "registration": {"method": "synthetic", "corners": None, "markers_found": []},
                               "review_reasons": [], "quality": {}, "synthetic": True}
    m["revision"] = n
    m["next_number"] = n + 1
    S.save(m)
    return m["id"], images


class ScriptedProvider:
    def __init__(self, n, images):
        self.n, self.images = n, images
        self.observed, self.compared, self.generated = [], [], []
        ink = np.zeros((640, 512), np.float32)
        cv2.circle(ink, (256, 250), 75, 1, 4)
        cv2.line(ink, (180, 220), (240, 110), 1, 4)
        cv2.line(ink, (240, 110), (330, 220), 1, 4)
        cv2.line(ink, (190, 290), (256, 440), 1, 4)
        cv2.line(ink, (256, 440), (320, 290), 1, 4)
        self.reference = png(ink)
        self.fail_on = None
        self.block = None
        self.entered = threading.Event()
        self.duplicate = False

    def observe(self, images):
        ids = [did for did, _ in images]
        self.observed.append(ids)
        if self.block:
            self.entered.set()
            self.block.wait(5)
        if self.fail_on is not None and len(self.observed) == self.fail_on:
            raise B.ProviderError("Scripted network failure")
        rows = [observation(did, "full_body" if did != "reference" and int(did[1:]) > self.n - max(1, self.n // 10) else "head_only",
                            accessories=did != "reference" and int(did[1:]) == self.n) for did in ids]
        if self.duplicate:
            rows = [rows[0], rows[0]]
        return Observations(observations=rows), {"provider": "TEST ONLY", "model": "scripted"}

    def generate(self, prompt, images):
        self.generated.append((prompt, images))
        return self.reference, {"provider": "TEST ONLY", "model": "scripted"}

    def compare(self, reference, candidate, reverse):
        assert reference == self.reference
        did = self.images[hashlib.sha256(candidate).hexdigest()]
        self.compared.append((did, reverse, hashlib.sha256(reference).hexdigest()))
        # Fixed rubric with one best score. Deterministic output isolates orchestration from perception.
        value = 4 if did == "d0002" else 3 if did == "d0003" else 2
        return Comparison(composition=value, silhouette=value, proportions=value, features=value,
                          reliable=True, explanation="Liknande mössa och långsmalt skägg."), {"provider": "TEST ONLY"}

    def check(self):
        return None


def scripted(monkeypatch, n):
    sid, images = dataset(n)
    p = ScriptedProvider(n, images)
    monkeypatch.setattr(B, "provider", lambda role, settings: p)
    monkeypatch.setenv("AI_BATCH_SIZE", "7")
    return sid, p


def wait(client, sid):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        a = client.get(f"/api/sessions/{sid}/ai").json()
        if a["job"]["status"] not in V.ACTIVE:
            return a
        time.sleep(.03)
    raise AssertionError("job timed out")


def action(client, sid, name, **body):
    r = client.post(f"/api/sessions/{sid}/ai/{name}", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def prepare(client, sid):
    action(client, sid, "consensus")
    a = wait(client, sid)
    assert a["job"]["status"] == "completed", a
    action(client, sid, "approve-consensus", note="Behåll majoritetens huvudmotiv.")
    action(client, sid, "generate")
    a = wait(client, sid)
    assert a["job"]["status"] == "completed", a
    vid = a["versions"][-1]["id"]
    action(client, sid, "approve-reference", version=vid)
    action(client, sid, "match")
    a = wait(client, sid)
    assert a["job"]["status"] == "completed", a
    return a


@pytest.mark.parametrize("n", [40, 75])
def test_complete_workflow_all_inputs_offline_show_exports_and_override(client, monkeypatch, n):
    sid, p = scripted(monkeypatch, n)
    # Enforce ordering before any paid synthesis or selection.
    assert client.post(f"/api/sessions/{sid}/ai/generate", json={}).status_code == 409
    assert client.post(f"/api/sessions/{sid}/ai/match", json={}).status_code == 409
    a = prepare(client, sid)
    assert a["consensus"]["included_count"] == n
    assert a["consensus"]["composition"]["head_only"] == n - n // 10
    assert sum(a["consensus"]["composition"].values()) == n
    accessory = next(f for f in a["consensus"]["features"] if f["key"] == "accessories")
    assert accessory["present_count"] == 1 and accessory["level"] == "rare"
    flattened = [did for batch in p.observed for did in batch if did != "reference"]
    assert len(flattened) == n and len(set(flattened)) == n
    assert all(len(batch) <= 7 for batch in p.observed)
    prompt, samples = p.generated[0]
    assert '"dominant_composition": "head_only"' in prompt and '"present_count": 1' in prompt
    assert "winner" not in a["consensus"] and len(samples) == 8
    assert sum(int(did[1:]) <= n - n // 10 for did, _ in samples) == 7
    assert len(p.compared) == 2 * n
    assert sorted((did, reverse) for did, reverse, _ in p.compared) == [(f"d{i:04d}", reverse) for i in range(1, n + 1) for reverse in (False, True)]
    assert a["match"]["ranking"][0]["id"] == "d0002"
    assert a["match"]["reference_hash"] == hashlib.sha256(p.reference).hexdigest()
    assert client.post(f"/api/sessions/{sid}/presentation", json={"action": "start"}).status_code == 409
    # Alternative top candidate needs an explicit, persisted explanation.
    assert client.post(f"/api/sessions/{sid}/ai/approve-winner", json={"winner": "d0003"}).status_code == 400
    action(client, sid, "approve-winner", winner="d0003", note="Arrangörens visuella granskning")
    # Simulate disconnected preparation provider. Show, reload, replay, result and export stay local.
    monkeypatch.setattr(B, "provider", lambda *args: (_ for _ in ()).throw(AssertionError("No AI in show")))
    client.post(f"/api/sessions/{sid}/presentation", json={"action": "start"})
    client.post(f"/api/sessions/{sid}/presentation", json={"action": "pause"})
    for phase in ("composite", "search", "narrowing", "match", "result"):
        v = client.get(f"/api/sessions/{sid}/presentation").json()
        assert v["phase"] == phase, v
        if phase in ("composite", "search", "narrowing"):
            for _ in range(2):  # reload must not leak rank, approval, reason, score or winner
                text = client.get(f"/api/sessions/{sid}/presentation").text
                for key in ("winner", "score", "rank", "approval", "explanation", "provenance"):
                    assert f'"{key}"' not in text
        else:
            assert v["winner"]["id"] == "d0003"
        if phase == "result":
            assert v["top"][0]["id"] == "d0003"  # public lead follows approved choice
        client.post(f"/api/sessions/{sid}/presentation", json={"action": "advance"})
    r = client.get(f"/api/sessions/{sid}/results").json()
    assert r["mode"] == "ai" and r["winner"] == "d0003" and not r["stale"]
    assert r["approval"]["override"] and r["reference_hash"] == a["match"]["reference_hash"]
    assert r["seed"] == a["match"]["show_seed"]
    assert r["show_order"] == client.get(f"/api/sessions/{sid}/results").json()["show_order"]
    assert "distance" not in r["ranking"][0] and "legacy" in r
    assert r["ranking"][0]["id"] == "d0002"  # saved model ranking is never rewritten
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/sessions/{sid}/export/gallery.zip").content))
    assert {"reference.png", "consensus.json", "provenance.json", "results.json", "results.csv", "legacy/average_raw.png"} <= set(z.namelist())
    assert z.read("reference.png") == p.reference
    assert len([f for f in z.namelist() if f.startswith("original/")]) == n
    assert client.post(f"/api/sessions/{sid}/presentation", json={"action": "replay"}).json()["phase"] == "composite"


def test_reference_change_invalidates_match_preserves_versions_and_data_changes(client, monkeypatch):
    sid, p = scripted(monkeypatch, 8)
    a = prepare(client, sid)
    action(client, sid, "approve-winner", winner="d0002")
    first = a["versions"][0]
    action(client, sid, "generate", note="En andra version")
    a = wait(client, sid)
    assert a["ready"] and len(a["versions"]) == 2  # new unapproved images cannot change existing winner
    action(client, sid, "approve-reference", version=a["versions"][-1]["id"])
    assert client.post(f"/api/sessions/{sid}/presentation", json={"action": "start"}).status_code == 409
    assert "match" not in client.get(f"/api/sessions/{sid}/ai").json()
    assert client.get(f"/api/sessions/{sid}/assets/{first['asset']}").content == p.reference
    client.patch(f"/api/sessions/{sid}/drawings/d0008", json={"action": "exclude", "reason": "Teständring"})
    a = client.get(f"/api/sessions/{sid}/ai").json()
    assert a["stale"] and not a["ready"] and len(a["versions"]) == 2
    assert client.post(f"/api/sessions/{sid}/ai/approve-reference", json={"version": first["id"]}).status_code == 409


def test_failure_resume_restart_caches_and_bad_ids(client, monkeypatch):
    sid, p = scripted(monkeypatch, 16)
    p.fail_on = 2
    action(client, sid, "consensus")
    a = wait(client, sid)
    assert a["job"]["status"] == "failed" and a["job"]["done"] == 7
    p.fail_on = None
    action(client, sid, "consensus")
    a = wait(client, sid)
    assert a["job"]["status"] == "completed"
    assert p.observed.count([f"d{i:04d}" for i in range(1, 8)]) == 1  # first checkpoint reused
    calls = len(p.observed)
    # Simulate server dying between checkpoints; startup marks it retryable, not erased.
    m = S.load(sid)
    m["ai"]["job"]["status"] = "running"
    S.save(m)
    V.recover_interrupted()
    assert S.load(sid)["ai"]["job"]["status"] == "failed"
    action(client, sid, "consensus")
    assert wait(client, sid)["job"]["status"] == "completed"
    assert len(p.observed) == calls
    # New config isolates caches; malformed/duplicate observations never become fake counts.
    monkeypatch.setenv("AI_BATCH_SIZE", "6")
    p.duplicate = True
    action(client, sid, "consensus")
    a = wait(client, sid)
    assert a["job"]["status"] == "failed" and "ID" in a["job"]["error"]


def test_cancel_and_input_edit_guard(client, monkeypatch):
    sid, p = scripted(monkeypatch, 8)
    p.block = threading.Event()
    action(client, sid, "consensus")
    assert p.entered.wait(3)
    assert client.patch(f"/api/sessions/{sid}/drawings/d0001", json={"action": "exclude", "reason": "x"}).status_code == 409
    assert client.post(f"/api/sessions/{sid}/analyze", json={}).status_code == 409
    action(client, sid, "cancel")
    p.block.set()
    # Drain shared executor: no cancelled response can commit a consensus afterwards.
    from app.services.analysis_jobs import EXECUTOR
    EXECUTOR.submit(lambda: None).result(timeout=5)
    a = client.get(f"/api/sessions/{sid}/ai").json()
    assert a["job"]["status"] == "cancelled" and "consensus" not in a


def test_no_credentials_and_unknown_providers_are_honest(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    sid, _ = dataset(2)
    assert not client.get("/api/ai/config").json()["configured"]
    r = client.post(f"/api/sessions/{sid}/ai/consensus", json={})
    assert r.status_code == 503 and "OPENAI_API_KEY" in r.json()["error"]
    assert S.load(sid).get("ai") is None
    monkeypatch.setenv("AI_UNDERSTANDING_PROVIDER", "made-up")
    assert "Okänd" in client.get("/api/ai/config").json()["error"]


def test_absolute_ranking_does_not_depend_on_batch_partition_or_input_order():
    # There are no per-batch relative scores: same absolute rubric always yields the same ordering.
    obs = [observation(f"d{i:04d}").model_dump() for i in range(1, 76)]
    obs[-1] = observation("d0075", "full_body", True).model_dump()
    sums = V.aggregate(obs)
    for size in (1, 4, 7, 8):
        merged = [o for i in range(0, len(obs), size) for o in obs[i:i + size]]
        assert V.aggregate(merged) == sums
    rows = [{"id": "d0002", "score": .8}, {"id": "d0001", "score": .8}, {"id": "d0003", "score": .4}]
    assert V.rank_matches(rows) == V.rank_matches(list(reversed(rows)))
    assert V.descriptor_score(obs[0], obs[0]) > V.descriptor_score(obs[0], obs[-1])


def mock_client(monkeypatch, handler):
    real = httpx.Client
    monkeypatch.setattr(B.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-never-export")
    monkeypatch.setattr(B.time, "sleep", lambda _: None)


def response_body(parsed):
    return {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": parsed.model_dump_json()}]}],
            "usage": {"input_tokens": 100, "output_tokens": 10}}


def test_openai_real_rest_contracts_and_validation(monkeypatch):
    image = png(np.zeros((640, 512), np.float32))
    seen = []
    def handler(req):
        seen.append(req)
        assert req.headers["authorization"] == "Bearer test-secret-never-export"
        if req.url.path.endswith("/responses"):
            body = json.loads(req.content)
            assert body["store"] is False and body["text"]["format"]["strict"]
            assert "untrusted" in body["instructions"] and "tools" not in body
            parts = body["input"][0]["content"]
            assert all(p["image_url"].startswith("data:image/png;base64,") for p in parts if p["type"] == "input_image")
            schema = body["text"]["format"]["name"]
            data = Observations(observations=[observation("d0001")]) if schema == "Observations" else Comparison(composition=3, silhouette=3, proportions=3, features=3, reliable=True, explanation="Mössa")
            return httpx.Response(200, json=response_body(data))
        if req.url.path.endswith("/images/edits"):
            body = json.loads(req.content)
            assert body["model"] == "gpt-image-1.5" and body["n"] == 1
            assert body["quality"] == "medium" and body["size"] == "1024x1536"
            assert body["images"][0]["image_url"].startswith("data:image/png;base64,")
            return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(image).decode()}]})
        return httpx.Response(200, json={"id": "gpt-4.1-mini"})
    mock_client(monkeypatch, handler)
    s = B.settings()
    p = B.provider("understanding", s)
    parsed, meta = p.observe([("d0001", image)])
    assert parsed.observations[0].id == "d0001"
    assert B.provider("matching", s).compare(image, image, True)[0].composition == 3
    output, provenance = B.provider("generation", s).generate("sketch", [("d0001", image)])
    assert Image.open(io.BytesIO(output)).format == "PNG"
    assert "test-secret" not in json.dumps([meta, provenance, s.public()])
    p.check()
    assert len(seen) == 4


@pytest.mark.parametrize("failure", ["refusal", "incomplete", "badjson", "badscore", "http401", "rate", "network"])
def test_provider_failures_bounded_retry_and_sanitized_errors(monkeypatch, failure):
    calls = []
    def handler(req):
        calls.append(req)
        if failure == "network":
            raise httpx.ReadTimeout("raw test-secret-never-export")
        if failure == "http401":
            return httpx.Response(401, text="test-secret-never-export")
        if failure == "rate":
            return httpx.Response(429, headers={"retry-after": "1"})
        if failure == "incomplete":
            return httpx.Response(200, json={"status": "incomplete"})
        if failure == "refusal":
            return httpx.Response(200, json={"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal"}]}]})
        if failure == "badjson":
            return httpx.Response(200, content=b"not json")
        return httpx.Response(200, json={"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": '{"composition": 99}'}]}]})
    mock_client(monkeypatch, handler)
    with pytest.raises(B.ProviderError) as e:
        B.provider("understanding", B.settings()).observe([("d0001", png(np.zeros((10, 10), np.float32)))])
    assert "test-secret" not in str(e.value)
    assert len(calls) == (3 if failure in ("rate", "network") else 1)


def test_generation_timeout_never_automatically_spends_twice(monkeypatch):
    calls = []
    def handler(req):
        calls.append(req)
        raise httpx.ReadTimeout("lost response")
    mock_client(monkeypatch, handler)
    with pytest.raises(B.ProviderError):
        B.provider("generation", B.settings()).generate("one sketch", [("d0001", png(np.zeros((10, 10), np.float32)))])
    assert len(calls) == 1


def test_match_resume_reuses_completed_pairs_and_reference_tamper_blocks_show(client, monkeypatch):
    sid, p = scripted(monkeypatch, 8)
    a = prepare(client, sid)
    count = len(p.compared)
    action(client, sid, "match")
    assert wait(client, sid)["job"]["status"] == "completed"
    assert len(p.compared) == count
    action(client, sid, "approve-winner", winner="d0002")
    v = a["versions"][0]
    (S.session_dir(sid) / "ai" / f"{v['asset']}.png").write_bytes(b"tampered")
    assert not client.get(f"/api/sessions/{sid}/ai").json()["ready"]
    assert client.post(f"/api/sessions/{sid}/presentation", json={"action": "start"}).status_code == 409


def test_uncertainty_is_counted_separately_and_never_invented():
    a, b = observation("d0001").model_dump(), observation("d0002").model_dump()
    b["composition"] = "uncertain"
    b["features"][0]["presence"] = "uncertain"
    report = V.aggregate([a, b])
    assert report["composition"]["uncertain"] == 1
    hat = next(f for f in report["features"] if f["key"] == "hat")
    assert hat["present_count"] == 1 and hat["uncertain_count"] == 1
    assert hat["absent_count"] == 0 and hat["level"] == "uncertain"


@pytest.mark.parametrize("body", [{"data": []}, {"data": [{"b64_json": "garbage!"}]}, {"data": [{"b64_json": base64.b64encode(b'<svg onload="evil"/>').decode()}]}])
def test_generation_rejects_invalid_or_executable_images(monkeypatch, body):
    mock_client(monkeypatch, lambda _: httpx.Response(200, json=body))
    with pytest.raises(B.ProviderError):
        B.provider("generation", B.settings()).generate("sketch", [("d0001", png(np.zeros((10, 10), np.float32)))])
