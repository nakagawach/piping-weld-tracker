import re,sqlite3,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from playwright.sync_api import expect,sync_playwright
from werkzeug.serving import make_server
from app import DB_PATH,app
from tests.ui_shell_e2e import PROJECT_ID,seed_database

BASE="http://127.0.0.1:8794"
SVG='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900"><rect width="1600" height="900" fill="white"/></svg>'

def seed():
    seed_database();key=f"project:{PROJECT_ID}"
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM number_map WHERE drawing_key=?",(key,))
        for order,num in enumerate(("11","8","6")):
            c.execute("""INSERT INTO number_map(
              drawing_key,page_number,item_order,number_text,source,x,y,width,height,saved_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (key,1,order,num,"manual",300+order*300,300,120,120,"2026-09-03T00:00:00+00:00"))

def box(page,selector):
    return page.locator(selector).bounding_box()

def main():
    seed();server=make_server("127.0.0.1",8794,app)
    th=threading.Thread(target=server.serve_forever,daemon=True);th.start();time.sleep(.15)
    try:
      with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={"width":390,"height":844})
        page.route(f"**/projects/{PROJECT_ID}/pdfium-info",lambda r:r.fulfill(status=200,content_type="application/json",body='{"pageCount":1}'))
        page.route(f"**/projects/{PROJECT_ID}/pdfium-page**",lambda r:r.fulfill(status=200,content_type="image/svg+xml",body=SVG))
        page.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
        expect(page.locator("#canvas")).to_be_visible(timeout=7000)
        expect(page.locator("#progressListPanel")).to_be_visible(timeout=4000)
        page.wait_for_timeout(180)

        # The old draggable splitter is gone as an interaction surface.
        expect(page.locator("#progressSplitter")).not_to_be_visible()
        splitter=page.locator("#progressSplitter")
        assert splitter.get_attribute("role") is None
        assert splitter.get_attribute("tabindex") is None
        assert splitter.get_attribute("aria-hidden")=="true"

        viewer=box(page,"#viewer");panel=box(page,"#progressListPanel")
        assert viewer and panel and panel["y"]>=viewer["y"]+viewer["height"]-2,(viewer,panel)

        # Portrait list-only fullscreen fills the viewport and list features remain usable.
        page.locator("#progressListFullscreen").click();page.wait_for_timeout(120)
        expect(page.locator("body")).to_have_class(re.compile(r".*progress-list-fullscreen.*"))
        expect(page.locator("#progressListFullscreen")).to_have_attribute("aria-pressed","true")
        full=box(page,"#progressListPanel")
        assert full and full["x"]<=1 and full["y"]<=1,full
        assert full["width"]>=388 and full["height"]>=840,full
        page.locator("#progressListHeaderToggle").click()
        expect(page.locator("#progressListSearch")).to_be_visible()
        page.locator("#progressListSearch").fill("11")
        expect(page.locator(".progress-list-record")).to_have_count(1)

        # Exit fullscreen: return to the automatically-sized bottom list.
        page.locator("#progressListFullscreen").click();page.wait_for_timeout(150)
        expect(page.locator("body")).not_to_have_class(re.compile(r".*progress-list-fullscreen.*"))
        expect(page.locator("#progressListFullscreen")).to_have_attribute("aria-pressed","false")
        page.locator("#progressListSearch").fill("")
        viewer=box(page,"#viewer");panel=box(page,"#progressListPanel")
        assert viewer and panel and panel["y"]>=viewer["y"]+viewer["height"]-2,(viewer,panel)

        # Landscape: normal list is right side; list-only fullscreen still fills entire viewport.
        page.set_viewport_size({"width":844,"height":390});page.wait_for_timeout(180)
        viewer=box(page,"#viewer");panel=box(page,"#progressListPanel")
        assert viewer and panel and panel["x"]>=viewer["x"]+viewer["width"]-2,(viewer,panel)
        page.locator("#progressListFullscreen").click();page.wait_for_timeout(120)
        full=box(page,"#progressListPanel")
        assert full and full["x"]<=1 and full["y"]<=1,full
        assert full["width"]>=842 and full["height"]>=388,full

        # Closing while list-fullscreen must clean up fullscreen state completely.
        page.locator("#progressListClose").click();page.wait_for_timeout(120)
        expect(page.locator("body")).not_to_have_class(re.compile(r".*progress-list-fullscreen.*"))
        expect(page.locator("body")).not_to_have_class(re.compile(r".*progress-list-open.*"))
        expect(page.locator("#progressListPanel")).not_to_be_visible()

        # Reopen: normal landscape right-side layout is restored, not stale fullscreen geometry.
        page.locator("#progressListToggle").click();page.wait_for_timeout(160)
        viewer=box(page,"#viewer");panel=box(page,"#progressListPanel")
        assert viewer and panel and panel["x"]>=viewer["x"]+viewer["width"]-2,(viewer,panel)
        assert panel["width"]<844,panel

        browser.close()
    finally:
      server.shutdown();th.join(timeout=2)
    print("PROGRESS_LIST_FIXED_FULLSCREEN_E2E: PASS")

if __name__=="__main__": main()
