import sqlite3,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from playwright.sync_api import expect,sync_playwright
from werkzeug.serving import make_server
from app import DB_PATH,app
from tests.ui_shell_e2e import PROJECT_ID,seed_database

BASE="http://127.0.0.1:8791"
SVG='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900"><rect width="1600" height="900" fill="white"/></svg>'

def seed():
    seed_database(); key=f"project:{PROJECT_ID}"
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM number_map WHERE drawing_key=?",(key,))
        c.execute("""INSERT INTO number_map(drawing_key,page_number,item_order,number_text,source,x,y,width,height,saved_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)""",(key,1,0,"1","manual",1000,800,120,120,"2026-09-03T00:00:00+00:00"))

def main():
    seed(); server=make_server("127.0.0.1",8791,app); th=threading.Thread(target=server.serve_forever,daemon=True); th.start();time.sleep(.15)
    try:
      with sync_playwright() as p:
        b=p.chromium.launch(); page=b.new_page(viewport={"width":390,"height":844})
        page.route(f"**/projects/{PROJECT_ID}/pdfium-info",lambda r:r.fulfill(status=200,content_type="application/json",body='{"pageCount":1}'))
        page.route(f"**/projects/{PROJECT_ID}/pdfium-page**",lambda r:r.fulfill(status=200,content_type="image/svg+xml",body=SVG))
        page.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
        expect(page.locator("#canvas")).to_be_visible(timeout=7000);expect(page.locator("#progressListPanel")).to_be_visible(timeout=4000)
        page.wait_for_timeout(180)
        def box():
          return page.evaluate("""()=>{const c=document.getElementById('canvas').getBoundingClientRect(),v=document.getElementById('viewer').getBoundingClientRect();return {cw:c.width,ch:c.height,vw:v.width,vh:v.height,zoom:document.getElementById('zoomResetCompact').textContent,pending:document.body.classList.contains('progress-layout-pending')}}""")
        opened=box(); assert not opened["pending"],opened
        assert opened["cw"]<=opened["vw"]+3 and opened["ch"]<=opened["vh"]+3,opened
        # Closing the list must recompute Fit against the enlarged viewer, never keep the smaller open-list base.
        page.locator("#progressListToggle").click();page.wait_for_timeout(180)
        expect(page.locator("#progressListToggle")).to_have_attribute("aria-expanded","false")
        closed=box();assert not closed["pending"],closed
        assert closed["cw"]>=opened["cw"]+30,(opened,closed)
        assert closed["cw"]<=closed["vw"]+3 and closed["ch"]<=closed["vh"]+3,closed
        # 100% Fit is a hard floor.
        for _ in range(8): page.locator("#zoomOut").evaluate("el=>el.click()")
        page.wait_for_timeout(100);floor=box()
        assert floor["cw"]>=closed["cw"]-2,(closed,floor)
        assert "100" in floor["zoom"] or "Fit" in floor["zoom"],floor
        # Open again: rebase to the list-open workspace, still not below Fit.
        page.locator("#progressListToggle").click();page.wait_for_timeout(180)
        reopened=box();assert not reopened["pending"],reopened
        assert reopened["cw"]<=reopened["vw"]+3 and reopened["ch"]<=reopened["vh"]+3,reopened
        for _ in range(8): page.locator("#zoomOut").evaluate("el=>el.click()")
        page.wait_for_timeout(80);refloor=box()
        assert refloor["cw"]>=reopened["cw"]-2,(reopened,refloor)
        b.close()
    finally:
      server.shutdown();th.join(timeout=2)
    print("PROGRESS_FIT_BASELINE_FLOOR_E2E: PASS")
if __name__=="__main__": main()
