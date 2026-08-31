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

BASE="http://127.0.0.1:8776"
SVG='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000"><rect width="1600" height="1000" fill="white"/></svg>'

def seed_progress():
    seed_database()
    key=f"project:{PROJECT_ID}"
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM number_map WHERE drawing_key=?",(key,))
        for page in (1,2,3):
            c.execute(
                """INSERT INTO number_map(
                  drawing_key,page_number,item_order,number_text,source,
                  x,y,width,height,saved_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (key,page,0,str(page),"manual",1000,900,120,120,"2026-08-30T00:00:00+00:00"),
            )

def run_server():
    server=make_server("127.0.0.1",8776,app)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    return server,thread

def stub(page):
    page.route(
        f"**/projects/{PROJECT_ID}/pdfium-info",
        lambda r:r.fulfill(status=200,content_type="application/json",body='{"pageCount":3}'),
    )
    def delayed_page(route):
        url=route.request.url
        if "page=2" in url:
            time.sleep(.25)
        elif "page=3" in url:
            time.sleep(.12)
        route.fulfill(status=200,content_type="image/svg+xml",body=SVG)
    page.route(f"**/projects/{PROJECT_ID}/pdfium-page**",delayed_page)

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
            expect(page.locator('.progress-thumb[data-page="1"]')).to_be_visible(timeout=7000)

            events=[]
            page.expose_function("capturePageEvent",lambda name,detail: events.append((name,detail)))
            page.evaluate("""
              for (const name of ['weld:progress-page-changing','weld:progress-page-loaded']) {
                window.addEventListener(name,e=>window.capturePageEvent(name,e.detail||{}));
              }
            """)

            # Start P2, then request P3 before P2 finishes.
            page.evaluate("""()=>{
              document.querySelector('.progress-thumb[data-page="2"]').click();
              document.querySelector('.progress-thumb[data-page="3"]').click();
            }""")
            page.wait_for_timeout(60)
            assert page.locator("#page").input_value()=="1"
            assert page.locator('.progress-thumb.active').get_attribute("data-page")=="1"

            expect(page.locator("#page")).to_have_value("3",timeout=7000)
            page.wait_for_timeout(250)
            assert page.locator("#page").input_value()=="3"
            assert page.locator(".progress-list-record.current-page").count()>=1
            loaded=[d.get("page") for n,d in events if n=="weld:progress-page-loaded"]
            assert 2 not in loaded,events
            assert loaded and loaded[-1]==3,events

            # Repeat in the other direction: stale P2 must not commit before the latest P1.
            events.clear()
            page.evaluate("""()=>{
              document.querySelector('.progress-thumb[data-page="2"]').click();
              document.querySelector('.progress-thumb[data-page="1"]').click();
            }""")
            page.wait_for_timeout(60)
            assert page.locator("#page").input_value()=="3"
            assert page.locator('.progress-thumb.active').get_attribute("data-page")=="3"
            expect(page.locator("#page")).to_have_value("1",timeout=7000)
            page.wait_for_timeout(250)
            loaded=[d.get("page") for n,d in events if n=="weld:progress-page-loaded"]
            assert 2 not in loaded,events
            assert loaded and loaded[-1]==1,events

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("PROGRESS_PAGE_LATEST_WINS_E2E: PASS")

if __name__=="__main__":
    main()
