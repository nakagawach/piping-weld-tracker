import sqlite3
import sys
import threading
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import DB_PATH, app
from tests.ui_shell_e2e import PROJECT_ID, seed_database

BASE="http://127.0.0.1:8778"
SVG='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000"><rect width="1600" height="1000" fill="white"/></svg>'

def seed_progress():
    seed_database()
    key=f"project:{PROJECT_ID}"
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM number_map WHERE drawing_key=?",(key,))
        c.execute(
            """INSERT INTO number_map(
              drawing_key,page_number,item_order,number_text,source,
              x,y,width,height,saved_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (key,1,0,"1","manual",1000,900,120,120,"2026-08-30T00:00:00+00:00"),
        )
        c.execute(
            """INSERT INTO number_map(
              drawing_key,page_number,item_order,number_text,source,
              x,y,width,height,saved_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (key,2,0,"2","manual",1200,1000,120,120,"2026-08-30T00:00:00+00:00"),
        )

def run_server():
    server=make_server("127.0.0.1",8778,app)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    return server,thread

def stub(page):
    page.route(
        f"**/projects/{PROJECT_ID}/pdfium-info",
        lambda r:r.fulfill(status=200,content_type="application/json",body='{"pageCount":2}'),
    )
    page.route(
        f"**/projects/{PROJECT_ID}/pdfium-page**",
        lambda r:r.fulfill(status=200,content_type="image/svg+xml",body=SVG),
    )

def assert_drawing_visible(page):
    viewer=page.locator("#viewer").bounding_box()
    canvas=page.locator("#canvas").bounding_box()
    assert viewer and canvas
    assert viewer["height"] > 80, viewer
    assert canvas["height"] > 80, canvas
    assert page.locator("#canvas").is_visible()

def main():
    seed_progress()
    server,thread=run_server()
    time.sleep(.2)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch()
            page=browser.new_page(viewport={"width":768,"height":1024})
            stub(page)
            page.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            expect(page.locator("#progressListToggle")).to_be_visible(timeout=7000)
            expect(page.locator("#progressListPanel")).to_be_visible(timeout=5000)
            expect(page.locator("#progressListToggle")).to_have_attribute("aria-expanded","true")
            expect(page.locator("#canvas")).to_be_visible(timeout=7000)
            assert_drawing_visible(page)

            # Repeat portrait -> landscape -> portrait with panel open.
            # This reproduces the stale requestAnimationFrame race from the old implementation.
            for _ in range(6):
                page.set_viewport_size({"width":1024,"height":768})
                page.wait_for_timeout(80)
                expect(page.locator("#progressListPanel")).to_be_visible()
                assert_drawing_visible(page)
                panel=page.locator("#progressListPanel").bounding_box()
                assert panel and panel["x"] > 600, panel

                page.set_viewport_size({"width":768,"height":1024})
                page.wait_for_timeout(80)
                expect(page.locator("#progressListPanel")).to_be_visible()
                assert_drawing_visible(page)
                panel=page.locator("#progressListPanel").bounding_box()
                assert panel and panel["y"] > 450, panel

            # Rotation must survive progress page changes.
            expect(page.locator("#rotateCompact")).to_be_visible()
            page.locator("#rotateCompact").click()
            page.wait_for_timeout(120)
            assert "90°" in page.locator("#rotate").text_content()
            page.locator("#next").click()
            page.wait_for_function("document.getElementById('page').value === '2'")
            page.wait_for_timeout(120)
            assert "90°" in page.locator("#rotate").text_content()
            page.locator("#prev").click()
            page.wait_for_function("document.getElementById('page').value === '1'")
            page.wait_for_timeout(120)
            assert "90°" in page.locator("#rotate").text_content()

            # Fast orientation change immediately after opening the panel.
            page.locator("#progressListClose").click()
            page.locator("#progressListToggle").click()
            page.set_viewport_size({"width":1024,"height":768})
            page.wait_for_timeout(120)
            assert_drawing_visible(page)

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("PROGRESS_LIST_ORIENTATION_VIEWER_E2E: PASS")

if __name__=="__main__":
    main()
