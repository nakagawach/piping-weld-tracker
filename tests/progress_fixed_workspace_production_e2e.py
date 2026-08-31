import re
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

BASE="http://127.0.0.1:8782"
SVG='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1131"><rect width="1600" height="1131" fill="white"/></svg>'

def seed_progress():
    seed_database()
    key=f"project:{PROJECT_ID}"
    with sqlite3.connect(DB_PATH) as c:
        c.execute("UPDATE projects SET project_name='初めのサンプルPDF' WHERE id=?",(PROJECT_ID,))
        c.execute("DELETE FROM number_map WHERE drawing_key=?",(key,))
        c.execute("DELETE FROM weld_progress WHERE drawing_key=?",(key,))
        rows=[]
        for i in range(1,35):
            page=1 if i<=28 else 2
            x=500+((i-1)%8)*620
            y=500+((i-1)//8)*800
            rows.append((key,page,i-1,str(i),"manual",x,y,120,120,"2026-08-31T00:00:00+00:00"))
        c.executemany(
            """INSERT INTO number_map(
              drawing_key,page_number,item_order,number_text,source,
              x,y,width,height,saved_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""",rows
        )
        c.executemany(
            """INSERT INTO weld_progress(
              drawing_key,page_number,position_x,position_y,number_text,status,
              completed_date,work_detail,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            [
                (key,1,560,560,"1","完了","2026-08-31","完了確認","2026-08-31T00:00:00+00:00"),
                (key,1,1180,560,"2","施工中","","施工中","2026-08-31T00:00:00+00:00"),
            ],
        )

def serve():
    server=make_server("127.0.0.1",8782,app)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    return server,thread

def stub(page):
    page.route(f"**/projects/{PROJECT_ID}/pdfium-info",lambda r:r.fulfill(status=200,content_type="application/json",body='{"pageCount":2}'))
    page.route(f"**/projects/{PROJECT_ID}/pdfium-page**",lambda r:r.fulfill(status=200,content_type="image/svg+xml",body=SVG))

def no_body_scroll(page):
    v=page.evaluate("""()=>({
      sh:document.documentElement.scrollHeight,ch:document.documentElement.clientHeight,
      bsh:document.body.scrollHeight,bch:document.body.clientHeight,y:window.scrollY
    })""")
    assert v["sh"]<=v["ch"]+1,v
    assert v["bsh"]<=v["bch"]+1,v
    assert abs(v["y"])<=1,v

def row(page,n,pageno=1):
    return page.locator(".progress-list-record").filter(
        has=page.locator(".progress-list-number",has_text=str(n))
    ).filter(
        has=page.locator(".progress-list-page",has_text=f"P{pageno}")
    ).first

def main():
    seed_progress();server,thread=serve();time.sleep(.2)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch()

            # Temporary mock entry remains on projects screen and route stays alive.
            home=browser.new_page(viewport={"width":1024,"height":768})
            home.goto(f"{BASE}/projects-screen",wait_until="domcontentloaded")
            expect(home.locator("[data-progress-mock]")).to_be_visible(timeout=5000)
            expect(home.locator("[data-ui3-favorites]")).to_be_visible(timeout=5000)
            mb=home.locator("[data-progress-mock]").bounding_box();fb=home.locator("[data-ui3-favorites]").bounding_box()
            assert mb and fb and mb["x"]<fb["x"],(mb,fb)
            home.locator("[data-progress-mock]").click()
            expect(home).to_have_url(re.compile(r"/mock/progress-fixed-layout$"))
            home.close()

            # Landscape tablet: fixed app, right panel, no body scroll.
            land=browser.new_page(viewport={"width":1024,"height":768})
            stub(land)
            land.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            expect(land.locator("#canvas")).to_be_visible(timeout=7000)
            expect(land.locator("#progressListToggle")).to_be_visible()
            land.locator("#progressListToggle").click()
            expect(land.locator("#progressListPanel")).to_be_visible()
            expect(land.locator(".progress-list-record")).to_have_count(34,timeout=7000)
            no_body_scroll(land)
            card=land.locator(".card").bounding_box();viewer=land.locator("#viewer").bounding_box();panel=land.locator("#progressListPanel").bounding_box()
            assert card and viewer and panel
            assert 307<=panel["width"]<=318,panel
            assert abs((viewer["x"]+viewer["width"])-panel["x"])<=2,(viewer,panel)
            assert viewer["height"]>300,viewer
            top=land.locator("main>.top").bounding_box()
            assert top and 42<=top["height"]<=46,top

            # Visible-row selection must not recenter the list.
            records=land.locator("#progressListRecords")
            before=records.evaluate("el=>el.scrollTop")
            r2=row(land,2);expect(r2).to_be_visible()
            r2.locator(".progress-list-focus").click()
            land.wait_for_timeout(80)
            after=records.evaluate("el=>el.scrollTop")
            assert abs(after-before)<=1,(before,after)
            expect(r2).to_have_class(re.compile(r".*selected.*"))

            # List hide/reopen keeps current selection and reveals it.
            land.locator("#progressListClose").click()
            expect(land.locator("#progressListPanel")).not_to_be_visible()
            land.locator("#progressListToggle").click()
            expect(row(land,2)).to_have_class(re.compile(r".*selected.*"))

            # Progress input button still opens the production editor.
            row(land,2).locator(".progress-list-input").click()
            expect(land.locator("#progressDialog")).to_be_visible(timeout=3000)
            expect(land.locator("#dialogTarget")).to_contain_text("2")
            land.locator("#closeDialog").click()

            # Zoom produces minimap. The + button is intentionally hidden while the
            # narrow right panel is open, so zoom once with the panel closed, then reopen.
            land.locator("#progressListClose").click()
            expect(land.locator("#zoomIn")).to_be_visible()
            land.locator("#zoomIn").click()
            land.locator("#progressListToggle").click()
            expect(land.locator("#progressMinimap")).to_have_class(re.compile(r".*show.*"),timeout=3000)
            mm=land.locator("#progressMinimap").bounding_box();vp=land.locator("#progressMinimapViewport").bounding_box()
            assert mm and vp and vp["width"]>5 and vp["height"]>5,(mm,vp)
            before_mini=land.locator("#progressMinimapCanvas").evaluate("el=>el.toDataURL()")
            land.locator("#rotate").click()
            land.wait_for_timeout(100)
            after_mini=land.locator("#progressMinimapCanvas").evaluate("el=>el.toDataURL()")
            assert before_mini!=after_mini
            no_body_scroll(land)
            land.close()

            # Portrait tablet: list is below drawing; 60/40 split of remaining card area.
            portrait=browser.new_page(viewport={"width":768,"height":1024})
            stub(portrait)
            portrait.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            portrait.locator("#progressListToggle").click()
            expect(portrait.locator("#progressListPanel")).to_be_visible()
            portrait.wait_for_timeout(100)
            no_body_scroll(portrait)
            viewer=portrait.locator("#viewer").bounding_box();panel=portrait.locator("#progressListPanel").bounding_box()
            assert viewer and panel
            assert panel["y"]>=viewer["y"]+viewer["height"]-2,(viewer,panel)
            assert panel["width"]>=760,panel
            combined=viewer["height"]+panel["height"]
            ratio=panel["height"]/combined
            assert .36<=ratio<=.45,(ratio,viewer,panel)
            portrait.close()

            # Phone: fixed viewport; list scroll does not move body.
            phone=browser.new_page(viewport={"width":390,"height":844})
            stub(phone)
            phone.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            phone.locator("#progressListToggle").click()
            expect(phone.locator("#progressListPanel")).to_be_visible()
            no_body_scroll(phone)
            body_before=phone.evaluate("()=>window.scrollY")
            phone.locator("#progressListRecords").evaluate("el=>el.scrollTop=500")
            phone.wait_for_timeout(60)
            assert phone.locator("#progressListRecords").evaluate("el=>el.scrollTop")>0
            assert phone.evaluate("()=>window.scrollY")==body_before
            # Thumbnail strip scroll is independent.
            thumbs=phone.locator("#progressThumbs")
            if thumbs.evaluate("el=>el.scrollWidth>el.clientWidth"):
                thumbs.evaluate("el=>el.scrollLeft=180")
                assert thumbs.evaluate("el=>el.scrollLeft")>0
                assert phone.evaluate("()=>window.scrollY")==body_before
            phone.close()

            browser.close()
    finally:
        server.shutdown();thread.join(timeout=2)

    print("PROGRESS_FIXED_WORKSPACE_PRODUCTION_E2E: PASS")

if __name__=="__main__":
    main()
