import re
import sqlite3
import sys
import threading
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server
from app import DB_PATH, app
from tests.ui_shell_e2e import PROJECT_ID, seed_database

BASE="http://127.0.0.1:8772"
SVG='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000"><rect width="1600" height="1000" fill="white"/></svg>'

def seed_progress():
    seed_database()
    key=f"project:{PROJECT_ID}"
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM number_map WHERE drawing_key=?",(key,))
        c.execute("DELETE FROM weld_progress WHERE drawing_key=?",(key,))
        c.executemany("""INSERT INTO number_map(drawing_key,page_number,item_order,number_text,source,x,y,width,height,saved_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)""",[
            (key,1,0,"3","manual",1000,900,120,120,"2026-08-30T00:00:00+00:00"),
            (key,1,1,"8","manual",3200,1900,120,120,"2026-08-30T00:00:00+00:00"),
            (key,2,0,"11","manual",2200,1500,120,120,"2026-08-30T00:00:00+00:00"),
        ])

def server():
    s=make_server("127.0.0.1",8772,app)
    t=threading.Thread(target=s.serve_forever,daemon=True);t.start();return s,t

def stub(page):
    page.route(f"**/projects/{PROJECT_ID}/pdfium-info",lambda r:r.fulfill(status=200,content_type="application/json",body='{"pageCount":2}'))
    page.route(f"**/projects/{PROJECT_ID}/pdfium-page**",lambda r:r.fulfill(status=200,content_type="image/svg+xml",body=SVG))

def row(page,n):
    return page.locator(".progress-list-record").filter(has=page.locator(".progress-list-number",has_text=str(n)))

def main():
    seed_progress();s,t=server();time.sleep(.2)
    try:
        with sync_playwright() as p:
            b=p.chromium.launch()

            d=b.new_page(viewport={"width":1440,"height":900});stub(d)
            d.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            d.locator("#progressListToggle").click()
            expect(d.locator(".progress-list-record")).to_have_count(3,timeout=7000)
            row(d,8).locator(".progress-list-focus").click()
            expect(d.locator("#canvas")).to_have_attribute("data-selected-target","1:3260:1960")
            row(d,11).locator(".progress-list-focus").click()
            expect(d.locator("#page")).to_have_value("2",timeout=7000)
            expect(d.locator("#canvas")).to_have_attribute("data-selected-target","2:2260:1560",timeout=7000)
            d.close()

            phone=b.new_page(viewport={"width":390,"height":844});stub(phone)
            phone.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            phone.locator("#progressListToggle").click()
            expect(phone.locator(".progress-list-record")).to_have_count(3,timeout=7000)
            normal_panel=phone.locator("#progressListPanel").bounding_box()
            normal_viewer=phone.locator("#viewer").bounding_box()
            assert normal_panel and normal_viewer and normal_viewer["y"] + normal_viewer["height"] <= normal_panel["y"] + 2, (normal_viewer,normal_panel)
            row(phone,3).locator(".progress-list-focus").click()
            expect(phone.locator("#canvas")).to_have_attribute("data-selected-target","1:1060:960",timeout=7000)
            phone.wait_for_timeout(120)
            assert float(phone.locator("#canvas").get_attribute("data-selection-pulse") or "0") > 0
            phone.wait_for_timeout(1450)
            assert float(phone.locator("#canvas").get_attribute("data-selection-pulse") or "0") == 0

            # Repeated zoom-out must stop at fit-to-view: one axis fills the viewer.
            for _ in range(4):
                phone.locator("#zoomOut").evaluate("el => el.click()")
            phone.wait_for_timeout(120)
            fit_canvas=phone.locator("#canvas").bounding_box()
            fit_viewer=phone.locator("#viewer").bounding_box()
            assert fit_canvas and fit_viewer
            assert fit_canvas["width"] <= fit_viewer["width"] + 2
            assert fit_canvas["height"] <= fit_viewer["height"] + 2
            assert min(abs(fit_canvas["width"]-fit_viewer["width"]),abs(fit_canvas["height"]-fit_viewer["height"])) <= 2.5,(fit_canvas,fit_viewer)

            phone.evaluate("document.body.classList.add('progress-fullscreen')")
            panel=phone.locator("#progressListPanel").bounding_box()
            assert panel and 410<=panel["height"]<=430 and panel["y"]>=410, panel
            viewer=phone.locator("#viewer").bounding_box()
            assert viewer and viewer["y"] < panel["y"], (viewer,panel)

            row(phone,3).locator(".progress-list-focus").click()
            expect(phone.locator("#canvas")).to_have_attribute("data-selected-target","1:1060:960",timeout=7000)
            assert "selected" in (row(phone,3).get_attribute("class") or "")
            row(phone,8).locator(".progress-list-focus").click()
            expect(phone.locator("#canvas")).to_have_attribute("data-selected-target","1:3260:1960",timeout=7000)
            assert "selected" in (row(phone,8).get_attribute("class") or "")
            phone.wait_for_timeout(1300)
            expect(phone.locator("#canvas")).to_have_attribute("data-selected-target","1:3260:1960")
            phone.close()

            portrait=b.new_page(viewport={"width":768,"height":1024});stub(portrait)
            portrait.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            portrait.locator("#progressListToggle").click()
            for _ in range(4):
                portrait.locator("#zoomOut").evaluate("el => el.click()")
            portrait.wait_for_timeout(120)
            pc=portrait.locator("#canvas").bounding_box()
            pv=portrait.locator("#viewer").bounding_box()
            assert pc and pv
            assert pc["width"] <= pv["width"] + 2
            assert pc["height"] <= pv["height"] + 2
            assert min(abs(pc["width"]-pv["width"]),abs(pc["height"]-pv["height"])) <= 2.5,(pc,pv)
            portrait.evaluate("document.body.classList.add('progress-fullscreen')")
            pb=portrait.locator("#progressListPanel").bounding_box()
            assert pb and 500<=pb["height"]<=525 and pb["y"]>=500,pb
            portrait.close()

            b.close()
    finally:
        s.shutdown();t.join(timeout=2)
    print("INTEGRATED_PROGRESS_LIST_V2_E2E: PASS")

if __name__=="__main__": main()
