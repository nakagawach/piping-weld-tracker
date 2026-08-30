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

BASE="http://127.0.0.1:8775"
SVG='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000"><rect width="1600" height="1000" fill="white"/></svg>'

def seed_progress():
    seed_database()
    key=f"project:{PROJECT_ID}"
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM number_map WHERE drawing_key=?",(key,))
        c.execute("DELETE FROM weld_progress WHERE drawing_key=?",(key,))
        c.executemany(
            """INSERT INTO number_map(
              drawing_key,page_number,item_order,number_text,source,
              x,y,width,height,saved_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            [
                (key,1,0,"11","manual",1752,1003,120,120,"2026-08-30T00:00:00+00:00"),
                (key,1,1,"8","manual",662,1148,120,120,"2026-08-30T00:00:00+00:00"),
                (key,2,0,"6","manual",2374,591,120,120,"2026-08-30T00:00:00+00:00"),
                (key,3,0,"14","manual",1990,784,121,120,"2026-08-30T00:00:00+00:00"),
            ],
        )

def run_server():
    server=make_server("127.0.0.1",8775,app)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    return server,thread

def stub(page):
    page.route(
        f"**/projects/{PROJECT_ID}/pdfium-info",
        lambda r:r.fulfill(status=200,content_type="application/json",body='{"pageCount":3}'),
    )
    page.route(
        f"**/projects/{PROJECT_ID}/pdfium-page**",
        lambda r:r.fulfill(status=200,content_type="image/svg+xml",body=SVG),
    )

def row(page,number,page_number):
    return page.locator(".progress-list-record").filter(
        has=page.locator(".progress-list-number",has_text=str(number))
    ).filter(has=page.locator(".progress-list-page",has_text=f"P{page_number}")).first

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
            expect(page.locator(".progress-list-record")).to_have_count(4,timeout=7000)

            # Baseline row selection.
            r14=row(page,14,3)
            r14.locator(".progress-list-focus").click()
            expect(page.locator("#page")).to_have_value("3",timeout=7000)
            expect(page.locator("#canvas")).to_have_attribute("data-selected-target","3:2051:844",timeout=7000)

            # List API center rounds to x=2050, drawing center rounds to x=2051.
            # The row must remain selected despite the 1px drift.
            expect(r14).to_have_attribute("class",lambda value:"selected" in value,timeout=3000)
            assert page.locator(".progress-list-record.selected").count()==1

            # Explicitly replay a selection event with a 1px mismatch.
            page.evaluate("""
              window.dispatchEvent(new CustomEvent('weld:progress-selection',{
                detail:{pageNumber:3,number:'14',x:2051,y:844}
              }))
            """)
            expect(r14).to_have_attribute("class",lambda value:"selected" in value,timeout=3000)
            assert page.locator(".progress-list-record.selected").count()==1

            # Page sync should react at page-changing and remain correct after loaded.
            for target in [1,3,2,1]:
                thumb=page.locator(f'.progress-thumb[data-page="{target}"]')
                thumb.click()
                expect(page.locator("#page")).to_have_value(str(target),timeout=7000)
                expect(page.locator(f'.progress-list-record.current-page .progress-list-page').first).to_have_text(f"P{target}",timeout=3000)
                current_rows=page.locator(".progress-list-record.current-page")
                assert current_rows.count()>=1
                for i in range(current_rows.count()):
                    assert current_rows.nth(i).locator(".progress-list-page").text_content()==f"P{target}"

            # Rapid list selections: exactly the latest row stays selected.
            r11=row(page,11,1)
            r8=row(page,8,1)
            r11.locator(".progress-list-focus").click()
            r8.locator(".progress-list-focus").click()
            expect(r8).to_have_attribute("class",lambda value:"selected" in value,timeout=3000)
            assert "selected" not in (r11.get_attribute("class") or "")
            assert page.locator(".progress-list-record.selected").count()==1

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("PROGRESS_LIST_STABLE_SYNC_E2E: PASS")

if __name__=="__main__":
    main()
