import sys
import threading
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import app
from tests.ui_shell_e2e import PROJECT_ID, seed_database

BASE="http://127.0.0.1:8773"
SVG='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000"><rect width="1600" height="1000" fill="white"/></svg>'

def run_server():
    s=make_server("127.0.0.1",8773,app)
    t=threading.Thread(target=s.serve_forever,daemon=True);t.start()
    return s,t

def stub(page):
    page.route(f"**/projects/{PROJECT_ID}/pdfium-info",lambda r:r.fulfill(status=200,content_type="application/json",body='{"pageCount":1}'))
    page.route(f"**/projects/{PROJECT_ID}/pdfium-page**",lambda r:r.fulfill(status=200,content_type="image/svg+xml",body=SVG))

def assert_aligned(page):
    base=page.locator("#canvas").bounding_box()
    memo=page.locator("#drawingMemoCanvas").bounding_box()
    assert base and memo
    assert abs(base["x"]-memo["x"]) <= 1.5, (base,memo)
    assert abs(base["y"]-memo["y"]) <= 1.5, (base,memo)
    assert abs(base["width"]-memo["width"]) <= 1.5, (base,memo)

def main():
    seed_database()
    s,t=run_server();time.sleep(.2)
    try:
        with sync_playwright() as p:
            b=p.chromium.launch()
            page=b.new_page(viewport={"width":390,"height":844})
            stub(page)
            page.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            expect(page.locator("#drawingMemoCanvas")).to_be_visible(timeout=7000)
            expect(page.locator("#canvas")).to_be_visible()
            assert_aligned(page)

            # Reproduce the user's sub-100% centered drawing case.
            page.locator("#canvas").evaluate("el => { el.style.width='50%'; }")
            page.wait_for_timeout(100)
            assert_aligned(page)

            # Layout width changes must keep the memo over the drawing.
            page.set_viewport_size({"width":430,"height":844})
            page.wait_for_timeout(100)
            assert_aligned(page)

            page.locator("#canvas").evaluate("el => { el.style.width='75%'; }")
            page.wait_for_timeout(100)
            assert_aligned(page)

            b.close()
    finally:
        s.shutdown();t.join(timeout=2)

    print("DRAWING_MEMO_ZOOM_ALIGNMENT_E2E: PASS")

if __name__=="__main__": main()
