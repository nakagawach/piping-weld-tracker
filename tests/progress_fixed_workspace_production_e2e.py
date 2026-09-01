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
            expect(land.locator("#progressListPanel")).to_be_visible(timeout=5000)
            expect(land.locator("#progressListToggle")).to_have_attribute("aria-expanded","true")
            expect(land.locator(".progress-list-record")).to_have_count(34,timeout=7000)

            # Progress-list header is one compact row by default; filters expand with ∨ / ∧.
            header_toggle=land.locator("#progressListHeaderToggle")
            expect(header_toggle).to_be_visible()
            expect(header_toggle).to_have_text("∨")
            expect(header_toggle).to_have_attribute("aria-expanded","false")
            expect(land.locator("#progressListPanel .panel-filters")).not_to_be_visible()
            header_toggle.click()
            expect(header_toggle).to_have_text("∧")
            expect(header_toggle).to_have_attribute("aria-expanded","true")
            expect(land.locator("#progressListPanel .panel-filters")).to_be_visible()
            expect(land.locator("#progressListTabs")).to_be_visible()
            expect(land.locator("#progressListSearch")).to_be_visible()
            header_toggle.click()
            expect(header_toggle).to_have_text("∨")
            expect(header_toggle).to_have_attribute("aria-expanded","false")
            expect(land.locator("#progressListPanel .panel-filters")).not_to_be_visible()
            expect(land.locator("#progressListPanel")).to_be_visible()
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

            # The list and drawing API read the same number_map: a listed P2 must render as saved.
            expect(row(land,29,2)).to_be_visible(timeout=3000)
            land.locator('.progress-thumb[data-page="2"]').click()
            expect(land.locator("#page")).to_have_value("2",timeout=5000)
            expect(land.locator("#canvas")).to_be_visible(timeout=5000)
            expect(land.locator("#empty")).to_be_hidden()
            land.locator('.progress-thumb[data-page="1"]').click()
            expect(land.locator("#page")).to_have_value("1",timeout=5000)

            # Zoom produces minimap. The + button is intentionally hidden while the
            # narrow right panel is open, so zoom once with the panel closed, then reopen.
            land.locator("#progressListClose").click()
            expect(land.locator("#zoomIn")).to_be_visible()
            land.locator("#zoomIn").click()
            land.locator("#progressListToggle").click()
            expect(land.locator("#progressMinimap")).to_have_class(re.compile(r".*show.*"),timeout=3000)
            mm=land.locator("#progressMinimap").bounding_box();vp=land.locator("#progressMinimapViewport").bounding_box()
            assert mm and vp and vp["width"]>5 and vp["height"]>5,(mm,vp)
            viewer_box=land.locator("#viewer").bounding_box()
            assert viewer_box
            assert abs(mm["x"]-(viewer_box["x"]+10))<=2,(mm,viewer_box)
            assert abs((mm["y"]+mm["height"])-(viewer_box["y"]+viewer_box["height"]-10))<=2,(mm,viewer_box)
            land.locator("#viewer").evaluate("el=>{el.scrollLeft=Math.min(120,el.scrollWidth-el.clientWidth);el.scrollTop=Math.min(120,el.scrollHeight-el.clientHeight)}")
            land.wait_for_timeout(80)
            mm_after_scroll=land.locator("#progressMinimap").bounding_box()
            viewer_after_scroll=land.locator("#viewer").bounding_box()
            assert mm_after_scroll and viewer_after_scroll
            assert abs(mm_after_scroll["x"]-(viewer_after_scroll["x"]+10))<=2,(mm_after_scroll,viewer_after_scroll)
            assert abs((mm_after_scroll["y"]+mm_after_scroll["height"])-(viewer_after_scroll["y"]+viewer_after_scroll["height"]-10))<=2,(mm_after_scroll,viewer_after_scroll)
            before_mini=land.locator("#progressMinimapCanvas").evaluate("el=>el.toDataURL()")
            land.locator("#rotate").click()
            land.wait_for_timeout(100)
            after_mini=land.locator("#progressMinimapCanvas").evaluate("el=>el.toDataURL()")
            assert before_mini!=after_mini
            no_body_scroll(land)
            land.close()

            # Wide PC matches approved mock structure: one header row, thumbnails,
            # then drawing summary/viewer on the left and progress list on the right.
            desktop=browser.new_page(viewport={"width":1440,"height":900})
            stub(desktop)
            desktop.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            expect(desktop.locator("#canvas")).to_be_visible(timeout=7000)
            expect(desktop.locator("#progressListPanel")).to_be_visible(timeout=5000)
            expect(desktop.locator("#progressListToggle")).to_have_attribute("aria-expanded","true")
            no_body_scroll(desktop)
            top_box=desktop.locator("main>.top").bounding_box()
            toolbar_box=desktop.locator(".toolbar").bounding_box()
            thumbs_box=desktop.locator("#progressThumbs").bounding_box()
            summary_box=desktop.locator("#summary").bounding_box()
            viewer_box=desktop.locator("#viewer").bounding_box()
            panel_box=desktop.locator("#progressListPanel").bounding_box()
            assert top_box and toolbar_box and thumbs_box and summary_box and viewer_box and panel_box
            assert 44<=top_box["height"]<=48,top_box
            assert toolbar_box["y"]<=1.5 and toolbar_box["y"]+toolbar_box["height"]<=top_box["height"]+2,(toolbar_box,top_box)
            expect(desktop.locator("#prev")).to_be_visible()
            expect(desktop.locator("#next")).to_be_visible()
            expect(desktop.locator("#zoomOut")).to_be_visible()
            expect(desktop.locator("#zoomIn")).to_be_visible()
            expect(desktop.locator("#rotate")).to_be_visible()
            expect(desktop.locator("#progressListToggle")).to_be_visible()
            assert abs(thumbs_box["y"]-(top_box["y"]+top_box["height"]))<=2,(top_box,thumbs_box)
            assert 54<=thumbs_box["height"]<=62,thumbs_box
            assert abs(panel_box["y"]-(thumbs_box["y"]+thumbs_box["height"]))<=2,(thumbs_box,panel_box)
            assert 335<=panel_box["width"]<=345,panel_box
            assert abs(summary_box["y"]-panel_box["y"])<=2,(summary_box,panel_box)
            assert abs(viewer_box["y"]-(summary_box["y"]+summary_box["height"]))<=2,(summary_box,viewer_box)
            assert abs((viewer_box["x"]+viewer_box["width"])-panel_box["x"])<=2,(viewer_box,panel_box)
            expect(desktop.locator("#zoomReset")).to_contain_text("Fit")
            fit_metrics=desktop.locator("#viewer").evaluate("""el=>({
              sw:el.scrollWidth,cw:el.clientWidth,sh:el.scrollHeight,ch:el.clientHeight,
              sl:el.scrollLeft,st:el.scrollTop
            })""")
            assert fit_metrics["sw"]<=fit_metrics["cw"]+2,fit_metrics
            assert fit_metrics["sh"]<=fit_metrics["ch"]+2,fit_metrics
            fit_canvas=desktop.locator("#canvas").bounding_box()
            assert fit_canvas
            assert fit_canvas["width"]<=viewer_box["width"]+2,(fit_canvas,viewer_box)
            assert fit_canvas["height"]<=viewer_box["height"]+2,(fit_canvas,viewer_box)

            # Manual zoom may overflow the viewer. PC mouse drag pans only the drawing
            # and must not be mistaken for a weld-point click.
            desktop.locator("#zoomIn").click()
            desktop.locator("#zoomIn").click()
            desktop.wait_for_timeout(120)
            expect(desktop.locator("#zoomReset")).not_to_contain_text("Fit")
            desktop.locator("#viewer").evaluate("el=>{el.scrollLeft=Math.min(120,Math.max(0,el.scrollWidth-el.clientWidth));el.scrollTop=Math.min(120,Math.max(0,el.scrollHeight-el.clientHeight))}")
            pan_before=desktop.locator("#viewer").evaluate("el=>({sl:el.scrollLeft,st:el.scrollTop,sw:el.scrollWidth,cw:el.clientWidth,sh:el.scrollHeight,ch:el.clientHeight})")
            assert pan_before["sw"]>pan_before["cw"]+5 or pan_before["sh"]>pan_before["ch"]+5,pan_before
            vb=desktop.locator("#viewer").bounding_box();assert vb
            start_x=vb["x"]+vb["width"]*.62;start_y=vb["y"]+vb["height"]*.62
            desktop.mouse.move(start_x,start_y)
            desktop.mouse.down()
            desktop.mouse.move(start_x-90,start_y-70,steps=6)
            desktop.mouse.up()
            desktop.wait_for_timeout(80)
            pan_after=desktop.locator("#viewer").evaluate("el=>({sl:el.scrollLeft,st:el.scrollTop})")
            assert pan_after["sl"]>pan_before["sl"]+20 or pan_after["st"]>pan_before["st"]+20,(pan_before,pan_after)
            expect(desktop.locator("#progressDialog")).not_to_be_visible()

            # Ctrl+wheel inside the drawing zooms the drawing and cancels the browser's
            # default wheel action. Plain wheel behavior outside this condition is untouched.
            ctrl_result=desktop.locator("#viewer").evaluate("""el=>{
              window.__ctrlWheelPrevented=false;
              el.addEventListener('wheel',e=>{window.__ctrlWheelPrevented=e.defaultPrevented},{once:true});
              const r=el.getBoundingClientRect(),before=document.getElementById('zoomReset').textContent;
              const dispatched=el.dispatchEvent(new WheelEvent('wheel',{
                bubbles:true,cancelable:true,ctrlKey:true,deltaY:-120,
                clientX:r.left+r.width/2,clientY:r.top+r.height/2
              }));
              return {before,after:document.getElementById('zoomReset').textContent,prevented:window.__ctrlWheelPrevented,dispatched};
            }""")
            assert ctrl_result["prevented"] is True,ctrl_result
            assert ctrl_result["dispatched"] is False,ctrl_result
            assert ctrl_result["after"]!=ctrl_result["before"],ctrl_result

            desktop.locator("#zoomReset").click()
            desktop.wait_for_timeout(140)
            expect(desktop.locator("#zoomReset")).to_contain_text("Fit")
            refit=desktop.locator("#viewer").evaluate("el=>({sw:el.scrollWidth,cw:el.clientWidth,sh:el.scrollHeight,ch:el.clientHeight})")
            assert refit["sw"]<=refit["cw"]+2,refit
            assert refit["sh"]<=refit["ch"]+2,refit

            # Closing the right list changes viewer width; FIT mode must recalculate and stay fully contained.
            desktop.locator("#progressListClose").click()
            desktop.wait_for_timeout(180)
            closed_fit=desktop.locator("#viewer").evaluate("el=>({sw:el.scrollWidth,cw:el.clientWidth,sh:el.scrollHeight,ch:el.clientHeight})")
            assert closed_fit["sw"]<=closed_fit["cw"]+2,closed_fit
            assert closed_fit["sh"]<=closed_fit["ch"]+2,closed_fit
            desktop.close()

            # Portrait tablet: list opens by default below drawing and AUTO split follows the drawing.
            portrait=browser.new_page(viewport={"width":768,"height":1024})
            stub(portrait)
            portrait.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            expect(portrait.locator("#progressListPanel")).to_be_visible(timeout=5000)
            expect(portrait.locator("#progressListToggle")).to_have_attribute("aria-expanded","true")
            expect(portrait.locator("#progressSplitter")).to_be_visible()
            portrait.wait_for_timeout(180)
            no_body_scroll(portrait)
            viewer=portrait.locator("#viewer").bounding_box();panel=portrait.locator("#progressListPanel").bounding_box();split=portrait.locator("#progressSplitter").bounding_box()
            assert viewer and panel and split
            assert abs(split["y"]-(viewer["y"]+viewer["height"]))<=2,(viewer,split)
            assert abs(panel["y"]-(split["y"]+split["height"]))<=2,(split,panel)
            assert panel["width"]>=760,panel
            assert viewer["height"]>=180,viewer
            assert panel["height"]>=185,panel
            portrait.close()

            # Saved rotation must settle before the initial AUTO splitter height is finalized.
            rotated=browser.new_page(viewport={"width":390,"height":844})
            stub(rotated)
            rotated.goto(f"{BASE}/projects-screen",wait_until="domcontentloaded")
            rotated.evaluate("""()=>localStorage.setItem('weldDrawingRotation:999','90')""")
            rotated.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            expect(rotated.locator("#canvas")).to_be_visible(timeout=7000)
            expect(rotated.locator("#rotate")).to_contain_text("90",timeout=7000)
            rotated.wait_for_timeout(160)
            rviewer=rotated.locator("#viewer").bounding_box()
            rcanvas=rotated.locator("#canvas").bounding_box()
            rsplit=rotated.locator("#progressSplitter").bounding_box()
            rpanel=rotated.locator("#progressListPanel").bounding_box()
            assert rviewer and rcanvas and rsplit and rpanel
            assert abs(rsplit["y"]-(rviewer["y"]+rviewer["height"]))<=2,(rviewer,rsplit)
            rgap=rsplit["y"]-(rcanvas["y"]+rcanvas["height"])
            assert rgap<=12,(rgap,rcanvas,rsplit)
            assert rpanel["height"]>=165,rpanel
            assert rotated.locator("#progressSplitter").get_attribute("data-mode")=="auto"
            rotated.close()

            # Tablet follows iPhone-style CSS fullscreen and must not call the native Fullscreen API.
            tablet_fs=browser.new_page(viewport={"width":1024,"height":768})
            stub(tablet_fs)
            tablet_fs.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            expect(tablet_fs.locator("#fullscreen")).to_be_visible(timeout=5000)
            tablet_fs.evaluate("""()=>{window.__nativeFsCalls=0;document.documentElement.requestFullscreen=()=>{window.__nativeFsCalls++;return Promise.resolve()}}""")
            expect(tablet_fs.locator("#progressThumbs")).to_be_visible()
            tablet_fs.locator("#fullscreen").click()
            tablet_fs.wait_for_timeout(100)
            assert tablet_fs.evaluate("()=>window.__nativeFsCalls") == 0
            expect(tablet_fs.locator("body")).to_have_class(re.compile(r".*progress-fullscreen.*"))
            expect(tablet_fs.locator("#progressThumbs")).not_to_be_visible()
            tablet_fs.locator("#fullscreen").click()
            tablet_fs.wait_for_timeout(100)
            expect(tablet_fs.locator("#progressThumbs")).to_be_visible()
            tablet_fs.close()

            # Phone: fixed viewport; list scroll does not move body.
            phone=browser.new_page(viewport={"width":390,"height":844})
            stub(phone)
            phone.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            assert "cache:'no-store'" in phone.content()
            appbar=phone.locator("[data-ui3-header='progress']")
            expect(appbar).to_be_visible()
            appbar_box=appbar.bounding_box()
            assert appbar_box and appbar_box["y"]<=1.5,appbar_box
            more=phone.locator("[data-ui3-header='progress'] details.more")
            expect(more).to_be_visible()
            more.locator("summary").click()
            assert more.evaluate("el=>el.open") is True
            expect(more.locator(".more-menu")).to_be_visible()
            menu_box=more.locator(".more-menu").bounding_box()
            assert menu_box and menu_box["y"]>=appbar_box["y"]+appbar_box["height"]-2,(appbar_box,menu_box)
            more.locator("summary").click()
            expect(phone.locator("#progressListPanel")).to_be_visible(timeout=5000)
            expect(phone.locator("#progressListToggle")).to_have_attribute("aria-expanded","true")
            expect(phone.locator("#progressSplitter")).to_be_visible()
            expect(phone.locator("#progressListState")).to_have_text(re.compile(r"34件"),timeout=5000)
            expect(phone.locator(".progress-list-record")).to_have_count(34,timeout=5000)
            phone.wait_for_timeout(260)
            no_body_scroll(phone)

            # Initial OPEN must wait for the real canvas before consuming the one-time FIT.
            initial_viewer=phone.locator("#viewer").bounding_box()
            initial_canvas=phone.locator("#canvas").bounding_box()
            assert initial_viewer and initial_canvas
            assert initial_canvas["width"]<=initial_viewer["width"]+2,(initial_canvas,initial_viewer)
            assert initial_canvas["height"]<=initial_viewer["height"]+2,(initial_canvas,initial_viewer)
            expect(phone.locator("#progressMinimap")).not_to_have_class(re.compile(r".*show.*"))
            assert "cache:'no-store'" in phone.content()
            assert "_fresh=" in phone.content()

            # Dynamic progress responses must also forbid HTTP/proxy caching.
            data_response=phone.request.get(f"{BASE}/projects/{PROJECT_ID}/progress-data?page=1")
            list_response=phone.request.get(f"{BASE}/projects/{PROJECT_ID}/progress-list-data")
            html_response=phone.request.get(f"{BASE}/projects/{PROJECT_ID}/progress?page=1")
            assert "no-store" in data_response.headers.get("cache-control","").lower(),data_response.headers
            assert "no-store" in list_response.headers.get("cache-control","").lower(),list_response.headers
            assert "no-store" in html_response.headers.get("cache-control","").lower(),html_response.headers

            # AUTO split removes avoidable blank space below the fitted drawing.
            viewer_auto=phone.locator("#viewer").bounding_box()
            canvas_auto=phone.locator("#canvas").bounding_box()
            split_auto=phone.locator("#progressSplitter").bounding_box()
            panel_auto=phone.locator("#progressListPanel").bounding_box()
            assert viewer_auto and canvas_auto and split_auto and panel_auto
            assert abs(split_auto["y"]-(viewer_auto["y"]+viewer_auto["height"]))<=2,(viewer_auto,split_auto)
            auto_gap=split_auto["y"]-(canvas_auto["y"]+canvas_auto["height"])
            # Never leave avoidable positive blank space. A negative gap is valid when
            # the flexible minimum list height clamps the splitter above the canvas bottom.
            assert auto_gap<=12,(auto_gap,canvas_auto,split_auto)
            assert panel_auto["height"]>=165,panel_auto
            assert phone.locator("#progressSplitter").get_attribute("data-mode")=="auto"

            # AUTO split must ignore viewer pan/scroll and react only to zoom changes.
            phone.evaluate("""()=>{window.__splitEvents=0;window.addEventListener('weld:progress-split-changed',()=>window.__splitEvents++)}""")
            before_events=phone.evaluate("()=>window.__splitEvents")
            phone.locator("#viewer").evaluate("el=>{el.scrollTop=Math.min(80,Math.max(0,el.scrollHeight-el.clientHeight));el.scrollLeft=Math.min(80,Math.max(0,el.scrollWidth-el.clientWidth))}")
            phone.wait_for_timeout(120)
            assert phone.evaluate("()=>window.__splitEvents")==before_events
            phone.locator("#zoomIn").evaluate("el=>el.click()")
            phone.wait_for_timeout(140)
            assert phone.evaluate("()=>window.__splitEvents")>before_events

            # Saved-to-saved page changes keep the committed canvas visible until the new page is ready.
            phone.evaluate("""()=>{
              window.__canvasHiddenSeen=false;
              const canvas=document.getElementById('canvas');
              new MutationObserver(()=>{if(canvas.hidden)window.__canvasHiddenSeen=true}).observe(canvas,{attributes:true,attributeFilter:['hidden']});
            }""")
            phone.locator("#next").click()
            phone.wait_for_function("document.getElementById('page').value === '2'")
            expect(phone.locator("#canvas")).to_be_visible(timeout=5000)
            assert phone.evaluate("()=>window.__canvasHiddenSeen") is False
            phone.locator("#prev").click()
            phone.wait_for_function("document.getElementById('page').value === '1'")
            phone.wait_for_timeout(100)

            # Dragging the independent splitter enters MANUAL mode and preserves the chosen height.
            current_viewer=phone.locator("#viewer").bounding_box()
            assert current_viewer
            start_h=current_viewer["height"]
            sb=phone.locator("#progressSplitter").bounding_box()
            assert sb
            phone.mouse.move(sb["x"]+sb["width"]/2,sb["y"]+sb["height"]/2)
            phone.mouse.down()
            phone.mouse.move(sb["x"]+sb["width"]/2,sb["y"]+70,steps=5)
            phone.mouse.up()
            phone.wait_for_timeout(100)
            manual_viewer=phone.locator("#viewer").bounding_box()
            assert manual_viewer and manual_viewer["height"]>start_h+40,(start_h,manual_viewer)
            assert phone.locator("#progressSplitter").get_attribute("data-mode")=="manual"
            expect(phone.locator("#progressDialog")).not_to_be_visible()
            manual_h=manual_viewer["height"]

            # MANUAL split survives progress page changes.
            phone.locator("#next").click()
            phone.wait_for_function("document.getElementById('page').value === '2'")
            phone.wait_for_timeout(140)
            after_page=phone.locator("#viewer").bounding_box()
            assert after_page and abs(after_page["height"]-manual_h)<=3,(manual_h,after_page)
            phone.locator("#prev").click()
            phone.wait_for_function("document.getElementById('page').value === '1'")
            phone.wait_for_timeout(120)

            # Flexible limits prevent either pane from being dragged out of the viewport.
            sb=phone.locator("#progressSplitter").bounding_box();assert sb
            phone.mouse.move(sb["x"]+sb["width"]/2,sb["y"]+sb["height"]/2);phone.mouse.down();phone.mouse.move(sb["x"]+sb["width"]/2,sb["y"]+1000);phone.mouse.up()
            phone.wait_for_timeout(80)
            panel_min=phone.locator("#progressListPanel").bounding_box();viewer_max=phone.locator("#viewer").bounding_box()
            assert panel_min and viewer_max and panel_min["height"]>=165,(panel_min,viewer_max)
            sb=phone.locator("#progressSplitter").bounding_box();assert sb
            phone.mouse.move(sb["x"]+sb["width"]/2,sb["y"]+sb["height"]/2);phone.mouse.down();phone.mouse.move(sb["x"]+sb["width"]/2,sb["y"]-1000);phone.mouse.up()
            phone.wait_for_timeout(80)
            viewer_min=phone.locator("#viewer").bounding_box();panel_max=phone.locator("#progressListPanel").bounding_box()
            assert viewer_min and panel_max and viewer_min["height"]>=145,(viewer_min,panel_max)

            body_before=phone.evaluate("()=>window.scrollY")
            records=phone.locator("#progressListRecords")
            phone.wait_for_function(
                "el=>el.scrollHeight>el.clientHeight",
                arg=records.element_handle(),
                timeout=5000,
            )
            # Let the one-shot current-page reveal finish before testing independent list scrolling.
            phone.wait_for_timeout(250)
            records.evaluate("el=>{el.scrollTop=Math.min(500,el.scrollHeight-el.clientHeight)}")
            phone.wait_for_timeout(80)
            assert records.evaluate("el=>el.scrollTop")>0
            assert phone.evaluate("()=>window.scrollY")==body_before
            # Thumbnail strip scroll is independent.
            thumbs=phone.locator("#progressThumbs")
            if thumbs.evaluate("el=>el.scrollWidth>el.clientWidth"):
                thumbs.evaluate("el=>el.scrollLeft=180")
                assert thumbs.evaluate("el=>el.scrollLeft")>0
                assert phone.evaluate("()=>window.scrollY")==body_before
            phone.close()

            # iPhone SE-sized viewport: compact list chrome and fullscreen reclaims app-header height.
            se=browser.new_page(viewport={"width":375,"height":667})
            stub(se)
            se.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            expect(se.locator("#progressListPanel")).to_be_visible(timeout=5000)
            expect(se.locator("#progressListToggle")).to_have_attribute("aria-expanded","true")
            se_header_toggle=se.locator("#progressListHeaderToggle")
            expect(se_header_toggle).to_have_text("∨")
            expect(se.locator("#progressListPanel .panel-filters")).not_to_be_visible()
            head_before=se.locator("#progressListPanel .panel-head").bounding_box()
            assert head_before and 30<=head_before["height"]<=33,head_before
            se_header_toggle.click()
            expect(se_header_toggle).to_have_text("∧")
            expect(se.locator("#progressListPanel .panel-filters")).to_be_visible()
            tab_before=se.locator("#progressListPanel .panel-tab").first.bounding_box()
            search_before=se.locator("#progressListPanel .panel-search input").bounding_box()
            assert tab_before and tab_before["height"]<=31,tab_before
            assert search_before and search_before["height"]<=35,search_before
            se_header_toggle.click()
            expect(se_header_toggle).to_have_text("∨")
            expect(se.locator("#progressListPanel .panel-filters")).not_to_be_visible()
            appbar_before=se.locator("[data-ui3-header='progress']").bounding_box()
            viewer_before=se.locator("#viewer").bounding_box()
            expect(se.locator("#progressThumbs")).to_be_visible()
            assert appbar_before and viewer_before
            se.evaluate("""()=>{window.__nativeFsCalls=0;document.documentElement.requestFullscreen=()=>{window.__nativeFsCalls++;return Promise.resolve()}}""")
            se.locator("#fullscreenCompact").click()
            assert se.evaluate("()=>window.__nativeFsCalls") == 0
            se.wait_for_timeout(160)
            expect(se.locator("body")).to_have_class(re.compile(r".*progress-fullscreen.*"))
            expect(se.locator("[data-ui3-header='progress'] .ui3-back")).not_to_be_visible()
            expect(se.locator("[data-ui3-header='progress'] .ui3-title")).not_to_be_visible()
            expect(se.locator("#progressThumbs")).not_to_be_visible()
            expect(se.locator("#fullscreenCompact")).to_be_visible()
            expect(se.locator("#drawingMemoEdit")).to_be_visible()
            se.locator("#drawingMemoEdit").click()
            expect(se.locator("#drawingMemoTools")).to_be_visible(timeout=3000)
            memo_tools_full=se.locator("#drawingMemoTools").bounding_box()
            viewer_with_memo=se.locator("#viewer").bounding_box()
            assert memo_tools_full and viewer_with_memo
            assert memo_tools_full["y"]+memo_tools_full["height"]<=viewer_with_memo["y"]+2,(memo_tools_full,viewer_with_memo)
            se.locator("#drawingMemoEdit").click()
            expect(se.locator("#drawingMemoTools")).not_to_be_visible()
            appbar_full=se.locator("[data-ui3-header='progress']").bounding_box()
            viewer_full=se.locator("#viewer").bounding_box()
            assert appbar_full and viewer_full
            assert appbar_full["width"]<=40 and appbar_full["height"]<=40,appbar_full
            assert viewer_full["y"] < viewer_before["y"]-30,(viewer_before,viewer_full)
            se.locator("#fullscreenCompact").click()
            se.wait_for_timeout(160)
            expect(se.locator("body")).not_to_have_class(re.compile(r".*progress-fullscreen.*"))
            expect(se.locator("[data-ui3-header='progress'] .ui3-back")).to_be_visible()
            expect(se.locator("#progressThumbs")).to_be_visible()
            se.close()

            browser.close()
    finally:
        server.shutdown();thread.join(timeout=2)

    print("PROGRESS_FIXED_WORKSPACE_PRODUCTION_E2E: PASS")

if __name__=="__main__":
    main()
