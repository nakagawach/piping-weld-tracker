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

BASE="http://127.0.0.1:8779"
SVG='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000"><rect width="1600" height="1000" fill="white"/></svg>'

def seed_progress():
    seed_database()
    key=f"project:{PROJECT_ID}"
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM number_map WHERE drawing_key=?",(key,))
        c.executemany(
            """INSERT INTO number_map(
              drawing_key,page_number,item_order,number_text,source,
              x,y,width,height,saved_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            [
                (key,1,0,"1","manual",1000,900,120,120,"2026-08-30T00:00:00+00:00"),
                (key,1,1,"2","manual",2000,900,120,120,"2026-08-30T00:00:00+00:00"),
            ],
        )

def run_server():
    server=make_server("127.0.0.1",8779,app)
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

def pixel(page,x,y):
    return page.locator("#canvas").evaluate(
        "(el,p)=>Array.from(el.getContext('2d').getImageData(p.x,p.y,1,1).data)",
        {"x":x,"y":y},
    )

def row(page,n):
    return page.locator(".progress-list-record").filter(
        has=page.locator(".progress-list-number",has_text=str(n))
    ).first

def main():
    seed_progress()
    server,thread=run_server()
    time.sleep(.2)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch()
            page=browser.new_page(viewport={"width":390,"height":844})
            stub(page)
            page.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            page.locator("#progressListToggle").click()
            expect(page.locator(".progress-list-record")).to_have_count(2,timeout=7000)

            # Before selection both targets have status rectangles.
            p1_before=pixel(page,283,256)
            p2_before=pixel(page,549,256)
            assert p1_before[:3] != [255,255,255],p1_before
            assert p2_before[:3] != [255,255,255],p2_before

            # Select target 1: its rectangle disappears, blue circular outline remains.
            row(page,1).locator(".progress-list-focus").click()
            expect(page.locator("#canvas")).to_have_attribute("data-selected-target","1:1060:960",timeout=7000)
            page.wait_for_timeout(80)
            p1_selected=pixel(page,283,256)
            p2_unselected=pixel(page,549,256)
            assert p1_selected[:3] == [255,255,255],p1_selected
            assert p2_unselected[:3] != [255,255,255],p2_unselected

            # Select target 2: target 1 rectangle returns, target 2 becomes circle-only.
            row(page,2).locator(".progress-list-focus").click()
            expect(page.locator("#canvas")).to_have_attribute("data-selected-target","1:2060:960",timeout=7000)
            page.wait_for_timeout(80)
            p1_restored=pixel(page,283,256)
            p2_selected=pixel(page,549,256)
            assert p1_restored[:3] != [255,255,255],p1_restored
            assert p2_selected[:3] == [255,255,255],p2_selected

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("SELECTED_MARKER_CIRCLE_ONLY_E2E: PASS")

if __name__=="__main__":
    main()
