"""Repeatable OFFLINE UI check with TEST-ONLY provider; never a live AI-quality test.

Install backend/requirements-ui.txt and `python -m playwright install chromium`, or set CHROMIUM_PATH.
Run from repository root: .venv/bin/python scripts/check_v2_ui.py
Screenshots/report go to an optional argv[1] directory, otherwise a temporary directory.
"""
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "backend/tests")]

import uvicorn
from playwright.sync_api import sync_playwright, expect

from app import config as C
from app.ai import providers as B
from app.main import app
from test_ai import ScriptedProvider, dataset


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="v2-ui-"))
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="v2-ui-data-") as storage:
        C.DATA_DIR = Path(storage)
        sid, images = dataset(40)
        provider = ScriptedProvider(40, images)
        B.provider = lambda *_: provider  # TEST ONLY. Not configured or shipped as a runtime provider.
        os.environ["AI_BATCH_SIZE"] = "7"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(.05)
        assert server.started
        url = f"http://127.0.0.1:{port}"
        errors, external, payloads = [], [], []
        try:
            with sync_playwright() as pw:
                executable = os.getenv("CHROMIUM_PATH") or shutil.which("chromium")
                browser = pw.chromium.launch(executable_path=executable, headless=True, args=["--no-sandbox"])
                context = browser.new_context(viewport={"width": 1440, "height": 1000})
                def route(request_route):
                    if not request_route.request.url.startswith(url + "/"):
                        external.append(request_route.request.url)
                        request_route.abort()
                    else:
                        request_route.continue_()
                context.route("**/*", route)
                control, show = context.new_page(), context.new_page()
                for page in (control, show):
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
                show.set_viewport_size({"width": 1280, "height": 720})
                control.goto(f"{url}/control?session={sid}")
                show.goto(f"{url}/show?session={sid}")
                expect(show.get_by_text("Du har fem minuter", exact=False)).to_be_visible()
                control.get_by_role("button", name="1. Analysera gruppen / återuppta").click()
                expect(control.get_by_role("heading", name="2. Granska konsensus")).to_be_visible(timeout=30000)
                expect(control.get_by_text("40 individuellt AI-klassificerade", exact=False)).to_be_visible()
                control.get_by_role("button", name="Godkänn konsensus", exact=True).click()
                control.get_by_role("button", name="Generera tomte (API-kostnad)", exact=True).click()
                control.get_by_role("button", name="Godkänn version 1", exact=True).wait_for(timeout=30000)
                control.get_by_role("button", name="Godkänn version 1", exact=True).click()
                control.get_by_role("button", name="Matcha / återuppta (40 bidrag)").click()
                expect(control.get_by_role("heading", name="5. Förhandsgranska match och godkänn vinnare")).to_be_visible(timeout=90000)
                control.get_by_label("Välj bland topp 5").select_option("d0003")
                control.get_by_label("Notering (krävs för annan än modellens förstaval)").fill("Visuellt granskad testkandidat")
                control.get_by_role("button", name="Godkänn vinnare och lokalt showpaket").click()
                expect(control.get_by_role("heading", name="Klar för offline-show")).to_be_visible(timeout=15000)
                control.screenshot(path=str(out / "control.png"), full_page=True)
                control.get_by_role("button", name="Starta", exact=True).click()
                expect(show.get_by_text("VISUELL REKONSTRUKTION", exact=False)).to_be_visible(timeout=10000)
                time.sleep(2)  # inspect normal-motion montage before pausing server clock
                control.get_by_role("button", name="Paus", exact=True).click()
                show.screenshot(path=str(out / "reconstruction.png"))
                for phase in ("composite", "search", "narrowing", "match", "result"):
                    v = show.request.get(f"{url}/api/sessions/{sid}/presentation").json()
                    assert v["phase"] == phase, v
                    payloads.append(v)
                    if phase in ("composite", "search", "narrowing"):
                        for key in ("winner", "rank", "score", "approval", "explanation", "provenance"):
                            assert f'"{key}"' not in json.dumps(v)
                        show.reload()
                        if phase == "search":
                            expect(show.get_by_text("SÖKER I ARKIVET", exact=False)).to_be_visible(timeout=10000)
                            show.wait_for_function("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
                            show.screenshot(path=str(out / "search.png"))
                    if phase == "match":
                        show.emulate_media(reduced_motion="reduce")
                        expect(show.get_by_text("MEST LIK GENOMSNITTSTOMTEN", exact=True)).to_be_visible(timeout=10000)
                        expect(show.get_by_text("BIDRAG D0003", exact=True)).to_be_visible()
                        show.screenshot(path=str(out / "match-reduced.png"))
                    if phase == "result":
                        expect(show.get_by_text("VALD MATCH · D0003", exact=False)).to_be_visible(timeout=10000)
                        show.screenshot(path=str(out / "result.png"))
                    if phase != "result":
                        with control.expect_response(lambda r: r.url.endswith("/presentation") and r.request.method == "POST"):
                            control.get_by_role("button", name="Nästa fas", exact=True).click()
                def disconnected(*_):
                    raise AssertionError("AI must not be called during replay")
                B.provider = disconnected
                control.get_by_role("button", name="Spela om", exact=True).click()
                show.reload()
                expect(show.get_by_text("GODKÄND AI-REKONSTRUKTION", exact=False)).to_be_visible(timeout=10000)
                assert not errors, errors
                assert not external, external
                assert len(provider.compared) == 80
                # Check projector layout containment at the final side-by-side reveal.
                show.request.post(f"{url}/api/sessions/{sid}/presentation", data=json.dumps({"action": "pause"}), headers={"Content-Type": "application/json"})
                for _ in range(3):
                    show.request.post(f"{url}/api/sessions/{sid}/presentation", data=json.dumps({"action": "advance"}), headers={"Content-Type": "application/json"})
                expect(show.get_by_text("MEST LIK GENOMSNITTSTOMTEN", exact=True)).to_be_visible(timeout=10000)
                box = show.locator(".verdict").bounding_box()
                assert box and box["x"] >= 0 and box["x"] + box["width"] <= 1280
                assert box["y"] + box["height"] < 720
                browser.close()
            report = {"status": "passed", "inputs": 40, "comparison_calls": 80, "external_requests": external,
                      "javascript_errors": errors, "phases": [v["phase"] for v in payloads],
                      "provider": "TEST ONLY scripted; live AI NOT verified", "screenshots": str(out)}
            (out / "report.json").write_text(json.dumps(report, indent=2))
            print(json.dumps(report, indent=2))
        finally:
            server.should_exit = True
            thread.join(timeout=10)


if __name__ == "__main__":
    main()
