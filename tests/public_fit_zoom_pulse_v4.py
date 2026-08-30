import json
import os
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright

BASE=os.environ.get("PUBLIC_BASE_URL","https://nakagawach.pythonanywhere.com/weld").rstrip("/")

def get_json(path):
    req=Request(f"{BASE}{path}",headers={"User-Agent":"weld-v4-public-check"})
    with urlopen(req,timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def find_project():
    for p in get_json("/projects").get("projects",[]):
        name=str(p.get("projectName") or p.get("project_name") or "")
        if "初めのサンプルPDF" in name:
            return p["id"]
    raise RuntimeError("初めのサンプルPDF not found")

def row(page,n):
    return page.locator(".progress-list-record").filter(
        has=page.locator(".progress-list-number",has_text=str(n))
    ).first

def assert_fit(page):
    canvas=page.locator("#canvas").bounding_box()
    viewer=page.locator("#viewer").bounding_box()
    assert canvas and viewer
    assert canvas["width"] <= viewer["width"] + 3,(canvas,viewer)
    assert canvas["height"] <= viewer["height"] + 3,(canvas,viewer)
    assert min(abs(canvas["width"]-viewer["width"]),abs(canvas["height"]-viewer["height"])) <= 3,(canvas,viewer)

def zoom_to_floor(page):
    for _ in range(6):
        page.locator("#zoomOut").evaluate("el => el.click()")
    page.wait_for_timeout(180)
    assert_fit(page)

def main():
    project_id=find_project()
    items=get_json(f"/projects/{project_id}/progress-list-data").get("items",[])
    p3=next(x for x in items if str(x["number"])=="3" and x["pageNumber"]==1)
    p8=next(x for x in items if str(x["number"])=="8" and x["pageNumber"]==1)
    url=f"{BASE}/projects/{project_id}/progress?page=1"

    with sync_playwright() as p:
        browser=p.chromium.launch()

        phone=browser.new_page(viewport={"width":390,"height":844})
        errors=[];posts=[]
        phone.on("pageerror",lambda e:errors.append(str(e)))
        phone.on("console",lambda m:errors.append(m.text) if m.type=="error" else None)
        phone.on("request",lambda r:posts.append(r.url) if r.method=="POST" else None)
        phone.goto(url,wait_until="domcontentloaded",timeout=60000)
        phone.locator("#progressListToggle").click()
        expect(row(phone,3)).to_be_visible(timeout=15000)
        zoom_to_floor(phone)

        row(phone,3).locator(".progress-list-focus").click()
        expect(phone.locator("#canvas")).to_have_attribute(
            "data-selected-target",f"1:{round(p3['x'])}:{round(p3['y'])}",timeout=15000
        )
        phone.wait_for_timeout(140)
        pulse3=float(phone.locator("#canvas").get_attribute("data-selection-pulse") or "0")
        assert pulse3>0,pulse3

        row(phone,8).locator(".progress-list-focus").click()
        expect(phone.locator("#canvas")).to_have_attribute(
            "data-selected-target",f"1:{round(p8['x'])}:{round(p8['y'])}",timeout=15000
        )
        phone.wait_for_timeout(140)
        pulse8=float(phone.locator("#canvas").get_attribute("data-selection-pulse") or "0")
        assert pulse8>0,pulse8
        assert "selected" in (row(phone,8).get_attribute("class") or "")
        assert "selected" not in (row(phone,3).get_attribute("class") or "")
        phone.wait_for_timeout(1450)
        assert float(phone.locator("#canvas").get_attribute("data-selection-pulse") or "0")==0
        expect(phone.locator("#canvas")).to_have_attribute(
            "data-selected-target",f"1:{round(p8['x'])}:{round(p8['y'])}"
        )
        assert not posts,posts
        assert not errors,errors
        phone.close()

        ipad=browser.new_page(viewport={"width":768,"height":1024})
        ipad.goto(url,wait_until="domcontentloaded",timeout=60000)
        ipad.locator("#progressListToggle").click()
        expect(ipad.locator(".progress-list-record").first).to_be_visible(timeout=15000)
        zoom_to_floor(ipad)
        ipad.evaluate("document.body.classList.add('progress-fullscreen')")
        ipad.wait_for_timeout(180)
        zoom_to_floor(ipad)
        panel=ipad.locator("#progressListPanel").bounding_box()
        assert panel and 500<=panel["height"]<=525 and panel["y"]>=500,panel
        ipad.close()

        browser.close()

    print("PUBLIC_FIT_ZOOM_PULSE_V4: PASS")

if __name__=="__main__": main()
