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

def svg(page):
    height=1400 if page==3 else 1000
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="{height}"><rect width="1600" height="{height}" fill="white"/><text x="100" y="150" font-size="90">P{page}</text></svg>'

def seed_progress():
    seed_database()
    key=f"project:{PROJECT_ID}"
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM number_map WHERE drawing_key=?",(key,))
        for page,count in ((1,1),(2,2),(3,3)):
            for i in range(count):
                c.execute(
                    """INSERT INTO number_map(
                      drawing_key,page_number,item_order,number_text,source,
                      x,y,width,height,saved_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (key,page,i,str(i+1),"manual",800+i*180,700,120,120,"2026-09-01T00:00:00+00:00"),
                )

def run_server():
    server=make_server("127.0.0.1",8782,app)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    return server,thread

def stub(page):
    page.route(
        f"**/projects/{PROJECT_ID}/pdfium-info",
        lambda r:r.fulfill(status=200,content_type="application/json",body='{"pageCount":4}'),
    )
    def delayed(route):
        url=route.request.url
        pno=1
        for n in (1,2,3,4):
            if f"page={n}" in url:
                pno=n
                break
        if pno==2:
            time.sleep(.35)
        elif pno==3:
            time.sleep(.10)
        elif pno==4:
            time.sleep(.20)
        route.fulfill(status=200,content_type="image/svg+xml",body=svg(pno))
    page.route(f"**/projects/{PROJECT_ID}/pdfium-page**",delayed)

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
            expect(page.locator("#canvas")).to_be_visible(timeout=7000)
            expect(page.locator("#summary")).to_contain_text("全 1")
            expect(page.locator('.progress-thumb[data-page="1"]')).to_be_disabled()
            expect(page.locator(".progress-list-record.current-page")).to_have_count(1,timeout=7000)

            events=[]
            page.expose_function("captureAtomicEvent",lambda name,detail:events.append((name,detail)))
            page.evaluate("""
              for(const name of ['weld:progress-page-changing','weld:progress-page-loaded']){
                window.addEventListener(name,e=>window.captureAtomicEvent(name,e.detail||{}));
              }
              window.__canvasHiddenChanges=[];
              const canvas=document.getElementById('canvas');
              new MutationObserver(()=>window.__canvasHiddenChanges.push(canvas.hidden))
                .observe(canvas,{attributes:true,attributeFilter:['hidden']});
            """)

            # Request P2, then P3 while P2 is still loading.
            page.evaluate("""()=>{
              document.querySelector('.progress-thumb[data-page="2"]').click();
              document.querySelector('.progress-thumb[data-page="3"]').click();
            }""")
            page.wait_for_timeout(60)

            # Until the latest page is ready, the committed P1 view stays coherent.
            snap=page.evaluate("""()=>({
              page:document.getElementById('page').value,
              active:document.querySelector('.progress-thumb.active')?.dataset.page||null,
              listPage:document.querySelector('.progress-list-record.current-page .progress-list-page')?.textContent||null,
              canvasHidden:document.getElementById('canvas').hidden,
              summary:document.getElementById('summary').textContent
            })""")
            assert snap["page"] in ("1","3"),snap
            assert snap["active"]==snap["page"],snap
            assert snap["listPage"]==f"P{snap['page']}",snap
            assert snap["page"]!="2",snap
            if snap["page"]=="1":
                assert snap["canvasHidden"] is False and "全 1" in snap["summary"],snap
            else:
                assert snap["canvasHidden"] is False and "全 3" in snap["summary"],snap
            assert page.evaluate("()=>window.__canvasHiddenChanges")==[]

            # P2 must never commit; only the latest P3 may replace P1.
            page.wait_for_function("document.getElementById('page').value === '3'",timeout=7000)
            page.wait_for_timeout(100)
            assert page.locator('.progress-thumb.active').get_attribute("data-page")=="3"
            assert "全 3" in page.locator("#summary").text_content()
            loaded=[d.get("page") for n,d in events if n=="weld:progress-page-loaded"]
            assert 2 not in loaded,events
            assert loaded and loaded[-1]==3,events

            # Saved -> unsaved: keep P3 until P4 is ready, then atomically show empty P4.
            page.locator('.progress-thumb[data-page="4"]').click(no_wait_after=True)
            page.wait_for_timeout(80)
            snap=page.evaluate("""()=>({
              page:document.getElementById('page').value,
              active:document.querySelector('.progress-thumb.active')?.dataset.page||null,
              canvasHidden:document.getElementById('canvas').hidden,
              emptyHidden:document.getElementById('empty').hidden,
              summaryHidden:document.getElementById('summary').hidden,
              summary:document.getElementById('summary').textContent,
              summaryHtml:document.getElementById('summary').innerHTML
            })""")
            assert snap["page"] in ("3","4") and snap["active"]==snap["page"],snap
            if snap["page"]=="3":
                assert snap["canvasHidden"] is False and snap["emptyHidden"] is True and "全 3" in snap["summary"],snap
            else:
                assert snap["canvasHidden"] is True and snap["emptyHidden"] is False and snap["summaryHidden"] is True and snap["summaryHtml"]=="",snap
            page.wait_for_function("document.getElementById('page').value === '4'",timeout=7000)
            page.wait_for_timeout(80)
            assert page.locator("#canvas").is_hidden()
            assert page.locator("#empty").is_visible()
            assert page.locator("#summary").evaluate("el=>el.hidden") is True
            assert page.locator("#summary").inner_html()==""
            assert page.locator('.progress-thumb.active').get_attribute("data-page")=="4"

            # Unsaved -> saved: keep the P4 empty state until P2 is fully ready.
            page.locator('.progress-thumb[data-page="2"]').click(no_wait_after=True)
            page.wait_for_timeout(100)
            snap=page.evaluate("""()=>({
              page:document.getElementById('page').value,
              active:document.querySelector('.progress-thumb.active')?.dataset.page||null,
              canvasHidden:document.getElementById('canvas').hidden,
              emptyHidden:document.getElementById('empty').hidden,
              summaryHidden:document.getElementById('summary').hidden,
              summary:document.getElementById('summary').textContent
            })""")
            assert snap["page"] in ("4","2") and snap["active"]==snap["page"],snap
            if snap["page"]=="4":
                assert snap["canvasHidden"] is True and snap["emptyHidden"] is False and snap["summaryHidden"] is True,snap
            else:
                assert snap["canvasHidden"] is False and snap["emptyHidden"] is True and "全 2" in snap["summary"],snap
            page.wait_for_function("document.getElementById('page').value === '2'",timeout=7000)
            page.wait_for_timeout(100)
            final_state=page.evaluate("""()=>{const c=document.getElementById('canvas'),v=document.getElementById('viewer'),cb=c.getBoundingClientRect(),vb=v.getBoundingClientRect();return{
              page:document.getElementById('page').value,
              active:document.querySelector('.progress-thumb.active')?.dataset.page||null,
              canvasHidden:c.hidden,
              emptyHidden:document.getElementById('empty').hidden,
              summary:document.getElementById('summary').textContent,
              canvas:{w:cb.width,h:cb.height,intrinsicW:c.width,intrinsicH:c.height,offsetW:c.offsetWidth,offsetH:c.offsetHeight,display:getComputedStyle(c).display,visibility:getComputedStyle(c).visibility,styleWidth:c.style.width},
              viewer:{w:vb.width,h:vb.height}
            }}""")
            assert final_state["page"]=="2" and final_state["active"]=="2",final_state
            assert final_state["canvasHidden"] is False and final_state["emptyHidden"] is True,final_state
            assert page.locator("#empty").evaluate("el=>getComputedStyle(el).display")=="none"
            assert "全 2" in final_state["summary"],final_state
            assert final_state["canvas"]["w"]>10 and final_state["canvas"]["h"]>10,final_state
            assert final_state["viewer"]["w"]>10 and final_state["viewer"]["h"]>10,final_state

            # Fullscreen + zoomed page change must preserve zoom and viewer/splitter geometry.
            page.locator("#fullscreenCompact").click()
            page.wait_for_timeout(120)
            page.evaluate("document.getElementById('zoomIn').click()")
            page.wait_for_timeout(120)
            before=page.evaluate("""()=>({
              page:document.getElementById('page').value,
              zoom:document.getElementById('zoomReset').textContent,
              width:document.getElementById('canvas').style.width,
              viewerH:document.getElementById('viewer').getBoundingClientRect().height,
              splitY:document.getElementById('progressSplitter').getBoundingClientRect().y
            })""")
            page.locator("#next").click()
            page.wait_for_function("document.getElementById('page').value === '3'",timeout=7000)
            page.wait_for_timeout(120)
            after=page.evaluate("""()=>({
              page:document.getElementById('page').value,
              zoom:document.getElementById('zoomReset').textContent,
              width:document.getElementById('canvas').style.width,
              viewerH:document.getElementById('viewer').getBoundingClientRect().height,
              splitY:document.getElementById('progressSplitter').getBoundingClientRect().y,
              canvasH:document.getElementById('canvas').getBoundingClientRect().height
            })""")
            assert after["page"]=="3",after
            assert after["zoom"]==before["zoom"],(before,after)
            assert after["width"]==before["width"],(before,after)
            assert page.locator("#progressSplitter").get_attribute("data-mode")=="auto"
            # User zoom-in already collapsed the list to minimum / viewer to maximum.
            # Page changes preserve that geometry while preserving the zoom.
            assert abs(after["viewerH"]-before["viewerH"])<=3,(before,after)
            assert abs(after["splitY"]-before["splitY"])<=3,(before,after)
            canvas_bottom=page.locator("#canvas").bounding_box()
            split_box=page.locator("#progressSplitter").bounding_box()
            assert canvas_bottom and split_box
            assert after["canvasH"]>0,after

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("PROGRESS_PAGE_ATOMIC_TRANSITION_E2E: PASS")

if __name__=="__main__":
    main()
