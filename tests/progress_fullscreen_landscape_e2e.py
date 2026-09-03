import re,sqlite3,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from playwright.sync_api import expect,sync_playwright
from werkzeug.serving import make_server
from app import DB_PATH,app
from tests.ui_shell_e2e import PROJECT_ID,seed_database

BASE="http://127.0.0.1:8793"
SVG='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900"><rect width="1600" height="900" fill="white"/></svg>'

def seed():
    seed_database(); key=f"project:{PROJECT_ID}"
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM number_map WHERE drawing_key=?",(key,))
        c.execute("""INSERT INTO number_map(drawing_key,page_number,item_order,number_text,source,x,y,width,height,saved_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)""",(key,1,0,"1","manual",300,300,120,120,"2026-09-03T00:00:00+00:00"))

def rect(page,id):
    return page.locator(id).bounding_box()

def assert_fit(page):
    c=rect(page,"#canvas");v=rect(page,"#viewer")
    assert c and v,(c,v)
    assert c["width"]<=v["width"]+3,(c,v)
    assert c["height"]<=v["height"]+3,(c,v)
    assert min(abs(c["width"]-v["width"]),abs(c["height"]-v["height"]))<=4,(c,v)

def main():
    seed();server=make_server("127.0.0.1",8793,app);th=threading.Thread(target=server.serve_forever,daemon=True);th.start();time.sleep(.15)
    try:
      with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page(viewport={"width":844,"height":390})
        page.route(f"**/projects/{PROJECT_ID}/pdfium-info",lambda r:r.fulfill(status=200,content_type="application/json",body='{"pageCount":1}'))
        page.route(f"**/projects/{PROJECT_ID}/pdfium-page**",lambda r:r.fulfill(status=200,content_type="image/svg+xml",body=SVG))
        page.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
        expect(page.locator("#canvas")).to_be_visible(timeout=7000)
        expect(page.locator("#progressListPanel")).to_be_visible(timeout=4000)
        page.wait_for_timeout(180)
        assert_fit(page)

        # Landscape fullscreen with list open: app header and thumbs are gone;
        # list starts at the top and drawing uses the remaining viewport height.
        page.locator("#fullscreen").click()
        expect(page.locator("body")).to_have_class(re.compile(r".*progress-fullscreen.*"),timeout=3000)
        page.wait_for_timeout(180)
        expect(page.locator(".ui3-appbar")).not_to_be_visible()
        expect(page.locator("#progressThumbs")).not_to_be_visible()
        panel=rect(page,"#progressListPanel");viewer=rect(page,"#viewer");toolbar=rect(page,".toolbar")
        assert panel and viewer and toolbar,(panel,viewer,toolbar)
        assert panel["y"]<=3,panel
        assert panel["height"]>=380,panel
        assert viewer["x"]<panel["x"],(viewer,panel)
        assert viewer["height"]>220,viewer
        assert_fit(page)

        # Still fullscreen: close list. Viewer must reclaim full width and remain Fit.
        page.locator("#progressListClose").click();page.wait_for_timeout(160)
        expect(page.locator("#progressListToggle")).to_have_attribute("aria-expanded","false")
        expect(page.locator(".ui3-appbar")).not_to_be_visible()
        expect(page.locator("#progressThumbs")).not_to_be_visible()
        viewer=rect(page,"#viewer")
        assert viewer and viewer["width"]>=835,viewer
        assert_fit(page)

        # Rotate screen while list hidden, then back; stale two-column layout must not survive.
        page.set_viewport_size({"width":390,"height":844});page.wait_for_timeout(180)
        assert_fit(page)
        page.set_viewport_size({"width":844,"height":390});page.wait_for_timeout(180)
        viewer=rect(page,"#viewer")
        assert viewer and viewer["width"]>=835,viewer
        assert_fit(page)

        # Re-open list in fullscreen landscape: right panel is restored, header stays hidden.
        page.locator("#progressListToggle").click();page.wait_for_timeout(180)
        expect(page.locator("#progressListPanel")).to_be_visible()
        expect(page.locator(".ui3-appbar")).not_to_be_visible()
        panel=rect(page,"#progressListPanel");viewer=rect(page,"#viewer")
        assert panel and viewer and panel["x"]>=viewer["x"]+viewer["width"]-2,(panel,viewer)
        assert panel["y"]<=3,panel
        assert_fit(page)

        # Exit fullscreen: normal landscape chrome returns.
        page.locator("#fullscreen").click();page.wait_for_timeout(180)
        expect(page.locator("body")).not_to_have_class(re.compile(r".*progress-fullscreen.*"))
        expect(page.locator("main > .top")).to_be_visible()
        expect(page.locator("#back")).to_be_visible()
        browser.close()
    finally:
      server.shutdown();th.join(timeout=2)
    print("PROGRESS_FULLSCREEN_LANDSCAPE_E2E: PASS")

if __name__=="__main__": main()
