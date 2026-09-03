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

BASE="http://127.0.0.1:8786"
WIDE='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="800"><rect width="1600" height="800" fill="white"/></svg>'


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
            (key,1,0,"1","manual",1000,900,120,120,"2026-09-03T00:00:00+00:00"),
        )


def serve():
    server=make_server("127.0.0.1",8786,app)
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
        lambda r:r.fulfill(status=200,content_type="image/svg+xml",body=WIDE),
    )


def boxes(page):
    return page.evaluate("""()=> {
      const box=id=>{const r=document.getElementById(id).getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}};
      const v=document.getElementById('viewer');
      return {
        canvas:box('canvas'),viewer:box('viewer'),panel:box('progressListPanel'),
        pending:document.body.classList.contains('progress-layout-pending'),
        scrollW:v.scrollWidth,scrollH:v.scrollHeight,clientW:v.clientWidth,clientH:v.clientHeight
      };
    }""")


def assert_stable(page):
    samples=[]
    for _ in range(4):
        samples.append(boxes(page))
        page.wait_for_timeout(80)
    assert not samples[-1]["pending"], samples
    for key in ("canvas","viewer","panel"):
        widths=[round(s[key]["w"],1) for s in samples]
        heights=[round(s[key]["h"],1) for s in samples]
        assert max(widths)-min(widths)<=1.1,(key,widths)
        assert max(heights)-min(heights)<=1.1,(key,heights)


def main():
    seed_progress()
    server,thread=serve()
    time.sleep(.2)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch()

            portrait=browser.new_page(viewport={"width":390,"height":844})
            stub(portrait)
            portrait.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            expect(portrait.locator("#canvas")).to_be_visible(timeout=7000)
            expect(portrait.locator("#progressListPanel")).to_be_visible(timeout=5000)
            portrait.wait_for_timeout(180)
            b=boxes(portrait)
            assert not b["pending"],b
            # Wide drawing: width is the initial limiting edge; list fills the rest.
            assert abs(b["canvas"]["w"]-b["viewer"]["w"])<=3,b
            assert abs(b["canvas"]["h"]-b["viewer"]["h"])<=3,b
            initial_panel_h=b["panel"]["h"]
            initial_viewer_h=b["viewer"]["h"]
            assert initial_panel_h>170,b
            assert_stable(portrait)

            # Zoom consumes list height until the list minimum, then drawing scrolls.
            for _ in range(6):
                portrait.locator("#zoomIn").evaluate("el=>el.click()")
                portrait.wait_for_timeout(35)
            z=boxes(portrait)
            assert z["viewer"]["h"]>=initial_viewer_h+40,(b,z)
            assert z["panel"]["h"]<=initial_panel_h-40,(b,z)
            assert z["panel"]["h"]>=168,z
            assert z["scrollH"]>z["clientH"]+2 or z["scrollW"]>z["clientW"]+2,z

            # Reset returns to the same fit/fill geometry without an intermediate visible state.
            portrait.locator("#zoomResetCompact").evaluate("el=>el.click()")
            portrait.wait_for_timeout(160)
            r=boxes(portrait)
            assert abs(r["canvas"]["w"]-r["viewer"]["w"])<=3,r
            assert abs(r["canvas"]["h"]-r["viewer"]["h"])<=3,r
            assert_stable(portrait)

            # Rotation uses rotated dimensions before revealing the canvas.
            portrait.locator("#rotateCompact").click()
            portrait.wait_for_timeout(160)
            rot=boxes(portrait)
            assert not rot["pending"],rot
            assert rot["canvas"]["h"]<=rot["viewer"]["h"]+3,rot
            assert rot["canvas"]["w"]<=rot["viewer"]["w"]+3,rot
            assert min(abs(rot["canvas"]["h"]-rot["viewer"]["h"]),abs(rot["canvas"]["w"]-rot["viewer"]["w"]))<=3,rot
            assert_stable(portrait)
            portrait.close()

            landscape=browser.new_page(viewport={"width":844,"height":390})
            stub(landscape)
            landscape.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            expect(landscape.locator("#canvas")).to_be_visible(timeout=7000)
            expect(landscape.locator("#progressListPanel")).to_be_visible(timeout=5000)
            landscape.wait_for_timeout(180)
            l=boxes(landscape)
            assert not l["pending"],l
            assert l["panel"]["x"]>=l["viewer"]["x"]+l["viewer"]["w"]-2,l
            assert l["panel"]["w"]>=278,l
            assert l["canvas"]["w"]<=l["viewer"]["w"]+3,l
            assert l["canvas"]["h"]<=l["viewer"]["h"]+3,l
            assert min(abs(l["canvas"]["w"]-l["viewer"]["w"]),abs(l["canvas"]["h"]-l["viewer"]["h"]))<=3,l
            initial_panel_w=l["panel"]["w"]
            initial_viewer_w=l["viewer"]["w"]
            assert_stable(landscape)

            for _ in range(6):
                landscape.locator("#zoomIn").evaluate("el=>el.click()")
                landscape.wait_for_timeout(35)
            lz=boxes(landscape)
            assert lz["viewer"]["w"]>=initial_viewer_w+40,(l,lz)
            assert lz["panel"]["w"]<=initial_panel_w-40,(l,lz)
            assert lz["panel"]["w"]>=278,lz
            assert lz["scrollW"]>lz["clientW"]+2 or lz["scrollH"]>lz["clientH"]+2,lz
            assert_stable(landscape)
            landscape.close()

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("PROGRESS_ADAPTIVE_FIT_FILL_E2E: PASS")


if __name__=="__main__":
    main()
