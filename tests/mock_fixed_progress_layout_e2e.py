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

BASE="http://127.0.0.1:8781"
SVG='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1131"><rect width="1600" height="1131" fill="white"/></svg>'

def seed_mock():
    seed_database()
    key=f"project:{PROJECT_ID}"
    with sqlite3.connect(DB_PATH) as c:
        c.execute("UPDATE projects SET project_name='初めのサンプルPDF' WHERE id=?",(PROJECT_ID,))
        c.execute("DELETE FROM number_map WHERE drawing_key=?",(key,))
        c.execute("DELETE FROM weld_progress WHERE drawing_key=?",(key,))
        rows=[]
        for i in range(1,34):
            page=1 if i<=28 else 2
            x=500+((i-1)%8)*620
            y=500+((i-1)//8)*800
            rows.append((key,page,i-1,str(i),"manual",x,y,120,120,"2026-08-31T00:00:00+00:00"))
        c.executemany(
            """INSERT INTO number_map(
              drawing_key,page_number,item_order,number_text,source,
              x,y,width,height,saved_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""", rows
        )
        c.executemany(
            """INSERT INTO weld_progress(
              drawing_key,page_number,position_x,position_y,number_text,status,
              completed_date,work_detail,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            [
                (key,1,560,560,"1","完了","2026-08-31","確認済み","2026-08-31T00:00:00+00:00"),
                (key,1,1180,560,"2","施工中","","作業中","2026-08-31T00:00:00+00:00"),
            ]
        )

def serve():
    s=make_server("127.0.0.1",8781,app)
    t=threading.Thread(target=s.serve_forever,daemon=True);t.start()
    return s,t

def stub(page):
    page.route(f"**/projects/{PROJECT_ID}/pdfium-info",lambda r:r.fulfill(status=200,content_type="application/json",body='{"pageCount":2}'))
    page.route(f"**/projects/{PROJECT_ID}/pdfium-page**",lambda r:r.fulfill(status=200,content_type="image/svg+xml",body=SVG))

def assert_no_body_scroll(page):
    vals=page.evaluate("()=>({sh:document.documentElement.scrollHeight,ch:document.documentElement.clientHeight,bsh:document.body.scrollHeight,bch:document.body.clientHeight})")
    assert vals["sh"]<=vals["ch"]+1,vals
    assert vals["bsh"]<=vals["bch"]+1,vals

def main():
    seed_mock();s,t=serve();time.sleep(.2)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch()

            # Projects screen exposes temporary mock button immediately left of favorites.
            home=browser.new_page(viewport={"width":1024,"height":768})
            home.goto(f"{BASE}/projects-screen",wait_until="domcontentloaded")
            expect(home.locator('[data-progress-mock]')).to_be_visible(timeout=5000)
            expect(home.locator('[data-ui3-favorites]')).to_be_visible(timeout=5000)
            mock_box=home.locator('[data-progress-mock]').bounding_box()
            fav_box=home.locator('[data-ui3-favorites]').bounding_box()
            assert mock_box and fav_box and mock_box["x"] < fav_box["x"],(mock_box,fav_box)
            expect(home.locator("#new-project")).to_be_visible()
            home.locator('[data-progress-mock]').click()
            expect(home).to_have_url(__import__("re").compile(r"/mock/progress-fixed-layout$"),timeout=5000)
            home.close()

            # Landscape iPad: fixed header/thumbs, right sidebar, body does not scroll.
            ipad=browser.new_page(viewport={"width":1024,"height":768})
            posts=[];errors=[]
            ipad.on("request",lambda r:posts.append(r.url) if r.method=="POST" else None)
            ipad.on("pageerror",lambda e:errors.append(str(e)))
            stub(ipad)
            ipad.goto(f"{BASE}/mock/progress-fixed-layout",wait_until="domcontentloaded")
            expect(ipad.locator("#loading")).not_to_be_visible(timeout=7000)
            expect(ipad.locator(".row")).to_have_count(33,timeout=7000)
            assert_no_body_scroll(ipad)
            header=ipad.locator(".header").bounding_box();thumbs=ipad.locator(".thumbs").bounding_box();panel=ipad.locator("#panel").bounding_box()
            assert header and 44<=header["height"]<=48,header
            assert thumbs and 56<=thumbs["height"]<=60,thumbs
            assert panel and 310<=panel["width"]<=322,panel
            assert ipad.locator("#mode").text_content()=="FIT"

            # Fit must contain whole page and touch one axis.
            viewer=ipad.locator("#viewer").bounding_box();stage=ipad.locator("#stage").bounding_box()
            assert viewer and stage
            assert stage["width"]<=viewer["width"]+2 and stage["height"]<=viewer["height"]+2,(stage,viewer)
            assert min(abs(stage["width"]-viewer["width"]),abs(stage["height"]-viewer["height"]))<=3,(stage,viewer)

            # Rotate in FIT: each 90deg keeps the complete page fitted.
            for expected in (90,180,270,0):
                ipad.locator("#rotate").click()
                expect(ipad.locator("#rotate")).to_contain_text(f"{expected}°")
                ipad.wait_for_timeout(60)
                viewer=ipad.locator("#viewer").bounding_box();stage=ipad.locator("#stage").bounding_box()
                assert viewer and stage
                assert stage["width"]<=viewer["width"]+3 and stage["height"]<=viewer["height"]+3,(expected,stage,viewer)
                assert min(abs(stage["width"]-viewer["width"]),abs(stage["height"]-viewer["height"]))<=4,(expected,stage,viewer)
                expect(ipad.locator("#mode")).to_have_text("FIT")

            # Manual zoom doesn't turn back into FIT after resize or rotate.
            ipad.locator("#zoomIn").click()
            expect(ipad.locator("#mode")).to_have_text("MANUAL")
            before=ipad.locator("#stage").get_attribute("style")
            scale_before=ipad.evaluate("()=>getComputedStyle(document.querySelector('#stage')).transform")
            ipad.set_viewport_size({"width":1100,"height":768})
            ipad.wait_for_timeout(120)
            assert ipad.locator("#mode").text_content()=="MANUAL"
            assert ipad.locator("#stage").get_attribute("style")==before
            style_before_rotate=ipad.locator("#stage").get_attribute("style")
            ipad.locator("#rotate").click()
            ipad.wait_for_timeout(80)
            assert ipad.locator("#mode").text_content()=="MANUAL"
            style_after_rotate=ipad.locator("#stage").get_attribute("style")
            import re as _re
            def scale_of(style):
                m=_re.search(r"scale\(([^)]+)\)",style or "")
                return float(m.group(1)) if m else None
            assert abs(scale_of(style_before_rotate)-scale_of(style_after_rotate))<1e-9,(style_before_rotate,style_after_rotate)

            # Repeated real touch pinch using CDP must never push the drawing fully outside the viewer.
            cdp=ipad.context.new_cdp_session(ipad)
            vb=ipad.locator("#viewer").bounding_box()
            assert vb
            cx0=vb["x"]+vb["width"]/2
            cy0=vb["y"]+vb["height"]/2
            def touch(kind,pts):
                cdp.send("Input.dispatchTouchEvent",{
                    "type":kind,
                    "touchPoints":[{"x":x,"y":y,"radiusX":4,"radiusY":4,"force":1,"id":i+1} for i,(x,y) in enumerate(pts)]
                })
            for _ in range(10):
                touch("touchStart",[(cx0-45,cy0),(cx0+45,cy0)])
                touch("touchMove",[(cx0-95,cy0-5),(cx0+95,cy0+5)])
                touch("touchMove",[(cx0-38,cy0),(cx0+38,cy0)])
                touch("touchEnd",[])
                ipad.wait_for_timeout(30)
                viewer_box=ipad.locator("#viewer").bounding_box()
                stage_box=ipad.locator("#stage").bounding_box()
                assert viewer_box and stage_box
                overlap_x=max(0,min(viewer_box["x"]+viewer_box["width"],stage_box["x"]+stage_box["width"])-max(viewer_box["x"],stage_box["x"]))
                overlap_y=max(0,min(viewer_box["y"]+viewer_box["height"],stage_box["y"]+stage_box["height"])-max(viewer_box["y"],stage_box["y"]))
                assert overlap_x>20 and overlap_y>20,(viewer_box,stage_box)

            # Two fingers -> one remaining finger -> pan must not jump the stage away.
            touch("touchStart",[(cx0-50,cy0),(cx0+50,cy0)])
            touch("touchMove",[(cx0-100,cy0),(cx0+100,cy0)])
            touch("touchEnd",[(cx0-100,cy0)])
            touch("touchMove",[(cx0-70,cy0+25)])
            touch("touchEnd",[])
            ipad.wait_for_timeout(80)
            viewer_box=ipad.locator("#viewer").bounding_box()
            stage_box=ipad.locator("#stage").bounding_box()
            assert viewer_box and stage_box
            overlap_x=max(0,min(viewer_box["x"]+viewer_box["width"],stage_box["x"]+stage_box["width"])-max(viewer_box["x"],stage_box["x"]))
            overlap_y=max(0,min(viewer_box["y"]+viewer_box["height"],stage_box["y"]+stage_box["height"])-max(viewer_box["y"],stage_box["y"]))
            assert overlap_x>20 and overlap_y>20,(viewer_box,stage_box)

            # iOS page gesture hooks are canceling document-level magnification gestures.
            prevented=ipad.evaluate("""()=>{
              const e=new Event('gesturestart',{bubbles:true,cancelable:true});
              document.dispatchEvent(e);
              return e.defaultPrevented;
            }""")
            assert prevented is True,prevented

            # Row selection must not recenter if the row is already visible.
            ipad.locator("#fit").click()
            visible_row=ipad.locator(".row").nth(2)
            records_top_before=ipad.locator("#records").evaluate("el=>el.scrollTop")
            visible_row.click()
            ipad.wait_for_timeout(80)
            records_top_after=ipad.locator("#records").evaluate("el=>el.scrollTop")
            assert abs(records_top_after-records_top_before)<=1,(records_top_before,records_top_after)

            # Reopening the list only needs to reveal the stored selection.
            # Do not assert a click-to-offscreen position here because Playwright itself
            # scrolls offscreen click targets before dispatching the click.
            ipad.locator("#records").evaluate("el=>el.scrollTop=0")
            deep=ipad.locator(".row").nth(24)
            deep.evaluate("el=>el.click()")
            ipad.wait_for_timeout(100)
            rr=ipad.locator("#records").bounding_box();dr=deep.bounding_box()
            assert rr and dr
            assert dr["y"]>=rr["y"]-1 and dr["y"]+dr["height"]<=rr["y"]+rr["height"]+1,(rr,dr)

            # Minimap background image rotates with the drawing; viewport box logic stays unchanged.
            ipad.locator("#fit").click()
            ipad.locator("#zoomIn").click()
            expect(ipad.locator("#minimap")).to_have_class(__import__("re").compile(r".*show.*"),timeout=2000)
            expected_map={
                0:("rotate(0deg)",False),
                90:("rotate(90deg)",True),
                180:("rotate(180deg)",False),
                270:("rotate(270deg)",True),
            }
            # Current rotation is 90deg from the earlier MANUAL rotation test; return to 0 first.
            while (ipad.locator("#rotate").text_content() or "").strip() != "↻ 0°":
                ipad.locator("#rotate").click()
                ipad.wait_for_timeout(40)
            for deg in (0,90,180,270):
                if deg!=0:
                    ipad.locator("#rotate").click()
                    ipad.wait_for_timeout(50)
                style=ipad.locator("#minimapImg").get_attribute("style") or ""
                assert expected_map[deg][0] in style,(deg,style)
                mm=ipad.locator("#minimap").bounding_box()
                mi=ipad.locator("#minimapImg").bounding_box()
                assert mm and mi
                if expected_map[deg][1]:
                    assert mi["height"]<=mm["height"]+2 and mi["width"]<=mm["width"]+2,(deg,mm,mi)
                else:
                    assert mi["width"]<=mm["width"]+2 and mi["height"]<=mm["height"]+2,(deg,mm,mi)
            ipad.locator("#rotate").click()
            ipad.locator("#fit").click()

            # Minimap appears only in MANUAL and follows pan/zoom.
            ipad.locator("#fit").click()
            expect(ipad.locator("#minimap")).not_to_have_class(__import__("re").compile(r".*show.*"))
            ipad.locator("#zoomIn").click()
            expect(ipad.locator("#mode")).to_have_text("MANUAL")
            expect(ipad.locator("#minimap")).to_have_class(__import__("re").compile(r".*show.*"),timeout=2000)
            mm=ipad.locator("#minimap").bounding_box();vp=ipad.locator("#minimapViewport").bounding_box()
            assert mm and vp and vp["width"]>5 and vp["height"]>5,(mm,vp)
            before_vp=ipad.locator("#minimapViewport").get_attribute("style")
            vb2=ipad.locator("#viewer").bounding_box();assert vb2
            ipad.mouse.move(vb2["x"]+vb2["width"]/2,vb2["y"]+vb2["height"]/2)
            ipad.mouse.down()
            ipad.mouse.move(vb2["x"]+vb2["width"]/2+90,vb2["y"]+vb2["height"]/2+35,steps=4)
            ipad.mouse.up();ipad.wait_for_timeout(100)
            after_vp=ipad.locator("#minimapViewport").get_attribute("style")
            assert after_vp!=before_vp,(before_vp,after_vp)
            ipad.locator("#fit").click()
            expect(ipad.locator("#minimap")).not_to_have_class(__import__("re").compile(r".*show.*"))

            # Close sidebar, select via simulated drawing event, reopen -> row selection remains/scrolls.
            ipad.locator("#closePanel").click()
            expect(ipad.locator("#panel")).not_to_be_visible()
            ipad.evaluate("""()=>{const rows=[...document.querySelectorAll('.row')];}""")
            # Reopen then select a deep row using list, close/reopen to verify persistence.
            ipad.locator("#toggleList").click()
            deep=ipad.locator(".row").nth(24)
            deep.click();expect(deep).to_have_class(__import__("re").compile(r".*selected.*"))
            ipad.locator("#closePanel").click();ipad.locator("#toggleList").click();ipad.wait_for_timeout(150)
            expect(ipad.locator(".row.selected")).to_have_count(1)
            assert ipad.locator("#records").evaluate("el=>el.scrollTop")>0

            assert not posts,posts
            assert not errors,errors
            ipad.close()

            # Portrait tablet: vertical split; list gets ~40% of remaining workspace.
            portrait=browser.new_page(viewport={"width":768,"height":1024})
            stub(portrait)
            portrait.goto(f"{BASE}/mock/progress-fixed-layout",wait_until="domcontentloaded")
            expect(portrait.locator("#loading")).not_to_be_visible(timeout=7000)
            assert_no_body_scroll(portrait)
            ws=portrait.locator("#workspace").bounding_box();panel=portrait.locator("#panel").bounding_box()
            assert ws and panel
            ratio=panel["height"]/ws["height"]
            assert .37<=ratio<=.46,(ratio,ws,panel)
            portrait.close()

            # Phone: still fixed; only records scroll vertically.
            phone=browser.new_page(viewport={"width":390,"height":844})
            stub(phone)
            phone.goto(f"{BASE}/mock/progress-fixed-layout",wait_until="domcontentloaded")
            expect(phone.locator("#loading")).not_to_be_visible(timeout=7000)
            assert_no_body_scroll(phone)
            body_y=phone.evaluate("()=>window.scrollY")
            phone.locator("#records").evaluate("el=>el.scrollTop=500")
            phone.wait_for_timeout(50)
            assert phone.evaluate("()=>window.scrollY")==body_y
            assert phone.locator("#records").evaluate("el=>el.scrollTop")>0
            phone.close()

            browser.close()
    finally:
        s.shutdown();t.join(timeout=2)

    print("MOCK_FIXED_PROGRESS_LAYOUT_E2E: PASS")

if __name__=="__main__":
    main()
