import json
import re
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright

BASE="https://nakagawach.pythonanywhere.com/weld"

def get_json(path):
    req=Request(BASE+path,headers={"User-Agent":"weld-fixed-workspace-public"})
    with urlopen(req,timeout=30) as r:
        return json.loads(r.read().decode())

def find_project():
    for p in get_json("/projects").get("projects",[]):
        name=str(p.get("projectName") or p.get("project_name") or "")
        if "初めのサンプルPDF" in name:
            return p["id"]
    raise RuntimeError("初めのサンプルPDF not found")

def no_body_scroll(page):
    v=page.evaluate("""()=>({
      sh:document.documentElement.scrollHeight,ch:document.documentElement.clientHeight,
      bsh:document.body.scrollHeight,bch:document.body.clientHeight,y:window.scrollY
    })""")
    assert v["sh"]<=v["ch"]+1,v
    assert v["bsh"]<=v["bch"]+1,v
    assert abs(v["y"])<=1,v

def main():
    pid=find_project()
    with sync_playwright() as p:
        browser=p.chromium.launch()

        # Projects screen keeps the approved mock entry.
        home=browser.new_page(viewport={"width":1024,"height":768})
        home.goto(BASE+"/projects-screen",wait_until="domcontentloaded",timeout=60000)
        expect(home.locator("[data-progress-mock]")).to_be_visible(timeout=15000)
        expect(home.locator("[data-ui3-favorites]")).to_be_visible(timeout=15000)
        mb=home.locator("[data-progress-mock]").bounding_box()
        fb=home.locator("[data-ui3-favorites]").bounding_box()
        assert mb and fb and mb["x"]<fb["x"],(mb,fb)
        home.close()

        # Landscape tablet production workspace.
        page=browser.new_page(viewport={"width":1024,"height":768})
        posts=[];errors=[]
        page.on("request",lambda r:posts.append(r.url) if r.method=="POST" else None)
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.on("console",lambda m:errors.append(m.text) if m.type=="error" else None)
        page.goto(f"{BASE}/projects/{pid}/progress?page=1",wait_until="domcontentloaded",timeout=60000)
        expect(page.locator("#canvas")).to_be_visible(timeout=20000)
        expect(page.locator("#progressListToggle")).to_be_visible(timeout=15000)
        page.locator("#progressListToggle").click()
        expect(page.locator("#progressListPanel")).to_be_visible(timeout=10000)
        expect(page.locator(".progress-list-record").first).to_be_visible(timeout=20000)
        no_body_scroll(page)

        viewer=page.locator("#viewer").bounding_box()
        panel=page.locator("#progressListPanel").bounding_box()
        assert viewer and panel
        assert 307<=panel["width"]<=318,panel
        assert abs((viewer["x"]+viewer["width"])-panel["x"])<=3,(viewer,panel)
        assert viewer["height"]>250,viewer

        # Visible-row selection must not make the list jump.
        records=page.locator("#progressListRecords")
        visible=records.locator(".progress-list-record").first
        expect(visible).to_be_visible()
        before=records.evaluate("el=>el.scrollTop")
        visible.locator(".progress-list-focus").click()
        page.wait_for_timeout(120)
        after=records.evaluate("el=>el.scrollTop")
        assert abs(after-before)<=1,(before,after)
        expect(visible).to_have_class(re.compile(r".*selected.*"))

        # Hide/reopen list preserves the selected row.
        page.locator("#progressListClose").click()
        expect(page.locator("#progressListPanel")).not_to_be_visible()
        page.locator("#progressListToggle").click()
        expect(page.locator(".progress-list-record.selected")).to_have_count(1,timeout=5000)

        # Zoom via desktop control with panel closed, then reopen and verify minimap.
        page.locator("#progressListClose").click()
        expect(page.locator("#zoomIn")).to_be_visible()
        page.locator("#zoomIn").click()
        page.locator("#progressListToggle").click()
        expect(page.locator("#progressMinimap")).to_have_class(re.compile(r".*show.*"),timeout=5000)
        mm=page.locator("#progressMinimap").bounding_box()
        vp=page.locator("#progressMinimapViewport").bounding_box()
        assert mm and vp and vp["width"]>5 and vp["height"]>5,(mm,vp)
        viewer_box=page.locator("#viewer").bounding_box()
        assert viewer_box
        assert abs(mm["x"]-(viewer_box["x"]+10))<=2,(mm,viewer_box)
        assert abs((mm["y"]+mm["height"])-(viewer_box["y"]+viewer_box["height"]-10))<=2,(mm,viewer_box)
        before_mini=page.locator("#progressMinimapCanvas").evaluate("el=>el.toDataURL()")
        page.locator("#rotate").click()
        page.wait_for_timeout(180)
        after_mini=page.locator("#progressMinimapCanvas").evaluate("el=>el.toDataURL()")
        assert before_mini!=after_mini
        no_body_scroll(page)

        # Same page, portrait orientation with list open: drawing stays visible and list moves below.
        page.set_viewport_size({"width":768,"height":1024})
        page.wait_for_timeout(220)
        expect(page.locator("#canvas")).to_be_visible()
        viewer=page.locator("#viewer").bounding_box()
        panel=page.locator("#progressListPanel").bounding_box()
        assert viewer and panel
        assert viewer["height"]>120,viewer
        assert panel["y"]>=viewer["y"]+viewer["height"]-3,(viewer,panel)
        assert panel["width"]>=760,panel
        no_body_scroll(page)

        assert not posts,posts
        assert not errors,errors
        page.close()

        # Wide desktop follows the approved mock's three-region geometry.
        desktop=browser.new_page(viewport={"width":1440,"height":900})
        desktop.goto(f"{BASE}/projects/{pid}/progress?page=1",wait_until="domcontentloaded",timeout=60000)
        expect(desktop.locator("#canvas")).to_be_visible(timeout=20000)
        desktop.locator("#progressListToggle").click()
        expect(desktop.locator("#progressListPanel")).to_be_visible(timeout=10000)
        top_box=desktop.locator("main>.top").bounding_box()
        toolbar_box=desktop.locator(".toolbar").bounding_box()
        thumbs_box=desktop.locator("#progressThumbs").bounding_box()
        summary_box=desktop.locator("#summary").bounding_box()
        viewer_box=desktop.locator("#viewer").bounding_box()
        panel_box=desktop.locator("#progressListPanel").bounding_box()
        assert top_box and toolbar_box and thumbs_box and summary_box and viewer_box and panel_box
        assert 44<=top_box["height"]<=48,top_box
        assert toolbar_box["y"]<=1.5 and toolbar_box["y"]+toolbar_box["height"]<=top_box["height"]+2,(toolbar_box,top_box)
        assert abs(thumbs_box["y"]-(top_box["y"]+top_box["height"]))<=2,(top_box,thumbs_box)
        assert abs(panel_box["y"]-(thumbs_box["y"]+thumbs_box["height"]))<=2,(thumbs_box,panel_box)
        assert 335<=panel_box["width"]<=345,panel_box
        assert abs(summary_box["y"]-panel_box["y"])<=2,(summary_box,panel_box)
        assert abs(viewer_box["y"]-(summary_box["y"]+summary_box["height"]))<=2,(summary_box,viewer_box)
        no_body_scroll(desktop)
        desktop.close()

        # Phone: list scroll stays inside list and body remains fixed.
        phone=browser.new_page(viewport={"width":390,"height":844})
        pposts=[];perrors=[]
        phone.on("request",lambda r:pposts.append(r.url) if r.method=="POST" else None)
        phone.on("pageerror",lambda e:perrors.append(str(e)))
        phone.on("console",lambda m:perrors.append(m.text) if m.type=="error" else None)
        phone.goto(f"{BASE}/projects/{pid}/progress?page=1",wait_until="domcontentloaded",timeout=60000)
        appbar=phone.locator("[data-ui3-header='progress']")
        expect(appbar).to_be_visible(timeout=10000)
        appbar_box=appbar.bounding_box()
        assert appbar_box and appbar_box["y"]<=1.5,appbar_box
        more=appbar.locator("details.more")
        expect(more).to_be_visible()
        more.locator("summary").click()
        assert more.evaluate("el=>el.open") is True
        expect(more.locator(".more-menu")).to_be_visible()
        more.locator("summary").click()
        expect(phone.locator("#canvas")).to_be_visible(timeout=20000)
        phone.locator("#progressListToggle").click()
        expect(phone.locator("#progressListPanel")).to_be_visible(timeout=10000)
        expect(phone.locator(".progress-list-record").first).to_be_visible(timeout=20000)
        no_body_scroll(phone)
        records=phone.locator("#progressListRecords")
        phone.wait_for_function("el=>el.scrollHeight>el.clientHeight",arg=records.element_handle(),timeout=10000)
        body_y=phone.evaluate("()=>window.scrollY")
        records.evaluate("el=>{el.scrollTop=Math.min(420,el.scrollHeight-el.clientHeight)}")
        phone.wait_for_timeout(100)
        assert records.evaluate("el=>el.scrollTop")>0
        assert phone.evaluate("()=>window.scrollY")==body_y
        no_body_scroll(phone)
        assert not pposts,pposts
        assert not perrors,perrors
        phone.close()

        browser.close()

    print("PUBLIC_PROGRESS_FIXED_WORKSPACE: PASS")

if __name__=="__main__":
    main()
