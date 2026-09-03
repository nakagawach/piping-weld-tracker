import sqlite3,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from playwright.sync_api import expect,sync_playwright
from werkzeug.serving import make_server
from app import DB_PATH,app
from tests.ui_shell_e2e import PROJECT_ID,seed_database

BASE="http://127.0.0.1:8792"
SVG='<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1600"><rect width="900" height="1600" fill="white"/></svg>'

def seed():
    seed_database(); key=f"project:{PROJECT_ID}"
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM number_map WHERE drawing_key=?",(key,))
        c.execute("""INSERT INTO number_map(drawing_key,page_number,item_order,number_text,source,x,y,width,height,saved_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)""",(key,1,0,"1","manual",200,200,120,120,"2026-09-03T00:00:00+00:00"))

def rects(page):
    return page.evaluate("""()=>{const g=id=>{const r=document.getElementById(id).getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height}};return {viewer:g('viewer'),canvas:g('canvas'),panel:g('progressListPanel'),open:document.body.classList.contains('progress-list-open'),pending:document.body.classList.contains('progress-layout-pending')}}""")

def assert_fit(r):
    assert not r["pending"],r
    assert r["canvas"]["w"]<=r["viewer"]["w"]+3,r
    assert r["canvas"]["h"]<=r["viewer"]["h"]+3,r
    assert min(abs(r["canvas"]["w"]-r["viewer"]["w"]),abs(r["canvas"]["h"]-r["viewer"]["h"]))<=4,r

def main():
    seed(); server=make_server("127.0.0.1",8792,app);th=threading.Thread(target=server.serve_forever,daemon=True);th.start();time.sleep(.15)
    try:
      with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page(viewport={"width":390,"height":844})
        page.route(f"**/projects/{PROJECT_ID}/pdfium-info",lambda r:r.fulfill(status=200,content_type="application/json",body='{"pageCount":1}'))
        page.route(f"**/projects/{PROJECT_ID}/pdfium-page**",lambda r:r.fulfill(status=200,content_type="image/svg+xml",body=SVG))
        page.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
        expect(page.locator("#canvas")).to_be_visible(timeout=7000);expect(page.locator("#progressListPanel")).to_be_visible(timeout=4000)
        page.wait_for_timeout(180)
        r=rects(page);assert r["open"],r;assert_fit(r)
        # Close list, then rotate repeatedly. Closed mode must always return to one full-width viewer.
        page.locator("#progressListToggle").click();page.wait_for_timeout(150)
        expect(page.locator("#progressListToggle")).to_have_attribute("aria-expanded","false")
        for _ in range(4):
            page.set_viewport_size({"width":844,"height":390});page.wait_for_timeout(160)
            lr=rects(page);assert not lr["open"],lr;assert_fit(lr)
            assert lr["viewer"]["w"]>800,lr
            page.set_viewport_size({"width":390,"height":844});page.wait_for_timeout(160)
            pr=rects(page);assert not pr["open"],pr;assert_fit(pr)
            assert pr["viewer"]["w"]>380,pr
        # Open list and repeat: landscape must be right-side panel, portrait bottom panel.
        page.locator("#progressListToggle").click();page.wait_for_timeout(150)
        for _ in range(3):
            page.set_viewport_size({"width":844,"height":390});page.wait_for_timeout(160)
            lr=rects(page);assert lr["open"],lr;assert_fit(lr)
            assert lr["panel"]["x"]>=lr["viewer"]["x"]+lr["viewer"]["w"]-2,lr
            page.set_viewport_size({"width":390,"height":844});page.wait_for_timeout(160)
            pr=rects(page);assert pr["open"],pr;assert_fit(pr)
            assert pr["panel"]["y"]>=pr["viewer"]["y"]+pr["viewer"]["h"]-2,pr
        browser.close()
    finally:
      server.shutdown();th.join(timeout=2)
    print("PROGRESS_ORIENTATION_HIDDEN_VISIBLE_E2E: PASS")
if __name__=="__main__": main()
