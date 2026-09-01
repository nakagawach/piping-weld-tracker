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

BASE="http://127.0.0.1:8780"
SVG='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1131"><rect width="1600" height="1131" fill="white"/></svg>'
SCALE=1600/6000

def seed_progress():
    seed_database()
    key=f"project:{PROJECT_ID}"
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM number_map WHERE drawing_key=?",(key,))
        c.execute("DELETE FROM weld_progress WHERE drawing_key=?",(key,))
        rows=[]
        for i in range(1,31):
            page=1 if i<=26 else 2
            x=700+((i-1)%10)*470
            y=700+((i-1)//10)*650
            rows.append((key,page,i-1,str(i),"manual",x,y,120,120,"2026-08-31T00:00:00+00:00"))
        rows.append((key,3,0,"31","manual",1200,1000,120,120,"2026-08-31T00:00:00+00:00"))
        c.executemany(
            """INSERT INTO number_map(
              drawing_key,page_number,item_order,number_text,source,
              x,y,width,height,saved_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )
        # center=(760,760) for 1, center=(1230,760) for 2
        c.executemany(
            """INSERT INTO weld_progress(
              drawing_key,page_number,position_x,position_y,number_text,
              status,completed_date,work_detail,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            [
                (key,1,760,760,"1","完了","2026-08-31","完了確認","2026-08-31T00:00:00+00:00"),
                (key,1,1230,760,"2","施工中","","施工中","2026-08-31T00:00:00+00:00"),
            ],
        )

def run_server():
    server=make_server("127.0.0.1",8780,app)
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

def pixel(page,x,y):
    return page.locator("#canvas").evaluate(
        "(el,p)=>Array.from(el.getContext('2d').getImageData(p.x,p.y,1,1).data)",
        {"x":int(round(x)),"y":int(round(y))},
    )

def row(page,n,pageno):
    return page.locator(".progress-list-record").filter(
        has=page.locator(".progress-list-number",has_text=str(n))
    ).filter(
        has=page.locator(".progress-list-page",has_text=f"P{pageno}")
    ).first

def assert_fit(page):
    canvas=page.locator("#canvas").bounding_box()
    viewer=page.locator("#viewer").bounding_box()
    assert canvas and viewer
    assert canvas["width"] <= viewer["width"]+3,(canvas,viewer)
    assert canvas["height"] <= viewer["height"]+3,(canvas,viewer)
    assert min(
        abs(canvas["width"]-viewer["width"]),
        abs(canvas["height"]-viewer["height"]),
    ) <= 3.5,(canvas,viewer)

def main():
    seed_progress()
    server,thread=run_server()
    time.sleep(.2)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch()

            # iPad landscape: compact header + 312px right panel.
            landscape=browser.new_page(viewport={"width":1024,"height":768})
            stub(landscape)
            landscape.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            expect(landscape.locator("#canvas")).to_be_visible(timeout=7000)
            landscape.locator("#progressListToggle").click()
            expect(landscape.locator("#progressListPanel")).to_be_visible()
            expect(landscape.locator(".progress-list-record")).to_have_count(31,timeout=7000)
            top=landscape.locator("main>.top").bounding_box()
            toolbar=landscape.locator(".toolbar").bounding_box()
            thumbs=landscape.locator("#progressThumbs").bounding_box()
            panel=landscape.locator("#progressListPanel").bounding_box()
            assert top and 42<=top["height"]<=46,top
            assert toolbar and 42<=toolbar["height"]<=46,toolbar
            assert thumbs and 50<=thumbs["height"]<=54,thumbs
            assert panel and 307<=panel["width"]<=317,panel
            assert panel["x"]>=700,panel
            assert_fit(landscape)

            # Filled circular marker: center colored, square-corner location remains white.
            cx=760*SCALE;cy=760*SCALE
            center_px=pixel(landscape,cx,cy)
            corner_px=pixel(landscape,cx+24,cy+24)
            assert center_px[:3] != [255,255,255],center_px
            assert corner_px[:3] == [255,255,255],corner_px

            # Selected marker keeps status fill, adds blue ring, and blinks outside it.
            row(landscape,1,1).locator(".progress-list-focus").click()
            expect(landscape.locator("#canvas")).to_have_attribute("data-selected-target","1:760:760",timeout=7000)
            landscape.wait_for_timeout(50)
            selected_center=pixel(landscape,cx,cy)
            ring_px=pixel(landscape,cx+36,cy)
            pulse_px=pixel(landscape,cx+46,cy)
            assert selected_center[:3] != [255,255,255],selected_center
            assert ring_px[2] > ring_px[0]+40,ring_px
            assert pulse_px[:3] != [255,255,255],pulse_px

            # A new selection cancels the previous blink immediately.
            cx2=1230*SCALE
            row(landscape,2,1).locator(".progress-list-focus").click()
            expect(landscape.locator("#canvas")).to_have_attribute("data-selected-target","1:1230:760",timeout=7000)
            landscape.wait_for_timeout(60)
            old_outer=pixel(landscape,cx+46,cy)
            new_outer=pixel(landscape,cx2+46,cy)
            assert old_outer[:3] == [255,255,255],old_outer
            assert new_outer[:3] != [255,255,255],new_outer
            landscape.wait_for_timeout(950)
            pulse_finished=pixel(landscape,cx2+46,cy)
            blue_ring_stays=pixel(landscape,cx2+36,cy)
            assert pulse_finished[:3] == [255,255,255],pulse_finished
            assert blue_ring_stays[2] > blue_ring_stays[0]+40,blue_ring_stays
            landscape.close()

            # Large portrait tablet: bottom 40%, one-shot A4 landscape fit.
            portrait=browser.new_page(viewport={"width":1024,"height":1366})
            stub(portrait)
            portrait.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            portrait.locator("#progressListToggle").click()
            expect(portrait.locator("#progressListPanel")).to_be_visible()
            portrait.wait_for_timeout(180)
            pp=portrait.locator("#progressListPanel").bounding_box()
            assert pp and 414<=pp["height"]<=426,pp
            assert pp["x"]<=1 and pp["width"]>=1020,pp
            assert_fit(portrait)
            zoom_after_fit=portrait.locator("#zoomReset").text_content()
            width_after_fit=portrait.locator("#canvas").evaluate("el=>el.style.width")
            assert zoom_after_fit
            portrait.set_viewport_size({"width":1024,"height":1240})
            portrait.wait_for_timeout(180)
            assert portrait.locator("#zoomReset").text_content()==zoom_after_fit
            portrait.locator("#progressListClose").click()
            portrait.locator("#progressListToggle").click()
            portrait.wait_for_timeout(180)
            assert portrait.locator("#canvas").evaluate("el=>el.style.width")==width_after_fit
            portrait.close()

            # 768px portrait iPad/tablet: low mobile appbar + bottom 40%.
            tablet=browser.new_page(viewport={"width":768,"height":1024})
            stub(tablet)
            tablet.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            tablet.locator("#progressListToggle").click()
            expect(tablet.locator("#progressListPanel")).to_be_visible()
            tablet.wait_for_timeout(160)
            appbar=tablet.locator(".ui3-appbar").bounding_box()
            toolbar=tablet.locator(".toolbar").bounding_box()
            panel=tablet.locator("#progressListPanel").bounding_box()
            assert appbar and 42<=appbar["height"]<=46,appbar
            assert toolbar and 42<=toolbar["height"]<=46,toolbar
            assert panel and 302<=panel["height"]<=316,panel
            assert_fit(tablet)
            tablet.close()

            # Phone: bottom 40%. Hidden selection/page state must sync on reopen.
            phone=browser.new_page(viewport={"width":390,"height":844})
            stub(phone)
            phone.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            expect(phone.locator("#progressListState")).to_have_text(re.compile(r"31件"),timeout=7000)
            # Keep list hidden, select item 25 from drawing-side selection event.
            x25=700+((25-1)%10)*470+60
            y25=700+((25-1)//10)*650+60
            phone.evaluate(
                """d=>window.dispatchEvent(new CustomEvent('weld:progress-selection',{detail:d}))""",
                {"pageNumber":1,"number":"25","x":x25,"y":y25},
            )
            phone.locator("#progressListToggle").click()
            expect(phone.locator("#progressListPanel")).to_be_visible()
            phone.wait_for_timeout(180)
            panel=phone.locator("#progressListPanel").bounding_box()
            assert panel and 314<=panel["height"]<=326,panel
            r25=row(phone,25,1)
            expect(r25).to_have_attribute("class",re.compile(r".*\bselected\b.*"),timeout=3000)
            scroll_top=phone.locator("#progressListRecords").evaluate("el=>el.scrollTop")
            assert scroll_top>0,scroll_top

            # Close list, change page, reopen: current-page state follows P2.
            phone.locator("#progressListClose").click()
            phone.locator('.progress-thumb[data-page="2"]').click()
            expect(phone.locator("#page")).to_have_value("2",timeout=7000)
            phone.locator("#progressListToggle").click()
            phone.wait_for_timeout(180)
            current=phone.locator(".progress-list-record.current-page")
            assert current.count()>=1
            for i in range(current.count()):
                assert current.nth(i).locator(".progress-list-page").text_content()=="P2"
            phone.close()

            # Saved 90-degree rotation: initial fit uses rotated dimensions and anchors at viewer top-left.
            rotated=browser.new_page(viewport={"width":390,"height":844})
            rotated.add_init_script("localStorage.setItem('weldDrawingRotation:${PROJECT_ID}','90')")
            stub(rotated)
            rotated.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            expect(rotated.locator("#progressListPanel")).to_be_visible(timeout=5000)
            rotated.wait_for_timeout(220)
            assert_fit(rotated)
            rv=rotated.locator("#viewer").bounding_box()
            rc=rotated.locator("#canvas").bounding_box()
            rp=rotated.locator("#progressListPanel").bounding_box()
            assert rv and rc and rp
            assert abs(rc["x"]-rv["x"])<=2,(rc,rv)
            assert abs(rc["y"]-rv["y"])<=2,(rc,rv)
            assert 170<=rp["height"]<=322,rp
            rotated.close()

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("PROGRESS_RESPONSIVE_LAYOUT_V5_E2E: PASS")

if __name__=="__main__":
    main()
