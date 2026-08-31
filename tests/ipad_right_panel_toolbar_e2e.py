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

BASE="http://127.0.0.1:8777"
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

def run_server():
    server=make_server("127.0.0.1",8777,app)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    return server,thread

def stub(page):
    page.route(
        f"**/projects/{PROJECT_ID}/pdfium-info",
        lambda r:r.fulfill(status=200,content_type="application/json",body='{"pageCount":1}'),
    )
    page.route(
        f"**/projects/{PROJECT_ID}/pdfium-page**",
        lambda r:r.fulfill(status=200,content_type="image/svg+xml",body=SVG),
    )

def assert_controls_clear_of_panel(page):
    panel=page.locator("#progressListPanel").bounding_box()
    fs=page.locator("#fullscreen").bounding_box()
    rot=page.locator("#rotate").bounding_box()
    assert panel and fs and rot
    panel_left=panel["x"]
    assert fs["x"]+fs["width"] <= panel_left+1,(fs,panel)
    assert rot["x"]+rot["width"] <= panel_left+1,(rot,panel)

def main():
    seed_progress()
    server,thread=run_server()
    time.sleep(.2)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch()

            ipad=browser.new_page(viewport={"width":1024,"height":768})
            stub(ipad)
            ipad.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            expect(ipad.locator("#progressListToggle")).to_be_visible(timeout=7000)
            ipad.locator("#progressListToggle").click()
            expect(ipad.locator("#progressListPanel")).to_be_visible()
            expect(ipad.locator(".desktop-tools")).to_be_visible()
            expect(ipad.locator("#rotate")).to_be_visible()
            expect(ipad.locator("#fullscreen")).to_be_visible()
            expect(ipad.locator("#zoomOut")).to_be_visible()
            expect(ipad.locator("#zoomReset")).to_be_visible()
            expect(ipad.locator("#zoomIn")).to_be_visible()
            expect(ipad.locator("#viewReset")).not_to_be_visible()
            expect(ipad.locator("#reload")).not_to_be_visible()
            assert_controls_clear_of_panel(ipad)

            # Fullscreen must remain actionable while right panel is open.
            ipad.locator("#fullscreen").click()
            expect(ipad.locator("body")).to_have_class(__import__("re").compile(r".*progress-fullscreen.*"),timeout=3000)
            expect(ipad.locator("#progressListPanel")).to_be_visible()
            expect(ipad.locator("#fullscreen")).to_be_visible()
            assert_controls_clear_of_panel(ipad)

            # Exit fullscreen and ensure controls remain usable.
            ipad.locator("#fullscreen").click()
            expect(ipad.locator("body")).not_to_have_class(__import__("re").compile(r".*progress-fullscreen.*"),timeout=3000)
            expect(ipad.locator("#rotate")).to_be_visible()
            ipad.close()

            # Wide desktop keeps the full desktop tool row.
            desktop=browser.new_page(viewport={"width":1440,"height":900})
            stub(desktop)
            desktop.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            desktop.locator("#progressListToggle").click()
            expect(desktop.locator(".desktop-tools")).to_be_visible()
            expect(desktop.locator("#fullscreen")).to_be_visible()
            expect(desktop.locator("#fullscreenCompact")).not_to_be_visible()
            desktop.close()

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("IPAD_RIGHT_PANEL_TOOLBAR_E2E: PASS")

if __name__=="__main__":
    main()
