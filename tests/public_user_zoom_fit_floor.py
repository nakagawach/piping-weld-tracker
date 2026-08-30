import json
import os
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright

BASE=os.environ.get("PUBLIC_BASE_URL","https://nakagawach.pythonanywhere.com/weld").rstrip("/")

def get_json(path):
    req=Request(f"{BASE}{path}",headers={"User-Agent":"weld-fit-floor-public-check"})
    with urlopen(req,timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def find_project():
    for p in get_json("/projects").get("projects",[]):
        name=str(p.get("projectName") or p.get("project_name") or "")
        if "初めのサンプルPDF" in name:
            return p["id"]
    raise RuntimeError("初めのサンプルPDF not found")

def fit_assert(page):
    canvas=page.locator("#canvas").bounding_box()
    viewer=page.locator("#viewer").bounding_box()
    assert canvas and viewer
    assert canvas["width"] <= viewer["width"] + 3,(canvas,viewer)
    assert canvas["height"] <= viewer["height"] + 3,(canvas,viewer)
    assert min(abs(canvas["width"]-viewer["width"]),abs(canvas["height"]-viewer["height"])) <= 3,(canvas,viewer)

def zoom_to_floor(page):
    expect(page.locator("#zoomOut")).to_be_enabled(timeout=20000)
    for _ in range(8):
        page.locator("#zoomOut").evaluate("el => el.click()")
    page.wait_for_timeout(150)
    fit_assert(page)

def main():
    project_id=find_project()
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
        expect(phone.locator("#progressListPanel")).to_be_visible()
        zoom_to_floor(phone)

        before_width=phone.locator("#canvas").evaluate("el => el.style.width")
        before_zoom=phone.locator("#zoomReset").text_content()
        print("phone before", before_width, before_zoom)

        phone.set_viewport_size({"width":390,"height":730})
        phone.wait_for_timeout(250)
        assert phone.locator("#canvas").evaluate("el => el.style.width") == before_width
        assert phone.locator("#zoomReset").text_content() == before_zoom

        phone.locator("#progressListClose").click()
        phone.wait_for_timeout(250)
        assert phone.locator("#canvas").evaluate("el => el.style.width") == before_width
        assert phone.locator("#zoomReset").text_content() == before_zoom

        phone.locator("#progressListToggle").click()
        phone.wait_for_timeout(250)
        assert phone.locator("#canvas").evaluate("el => el.style.width") == before_width

        phone.evaluate("document.body.classList.add('progress-fullscreen')")
        phone.wait_for_timeout(250)
        assert phone.locator("#canvas").evaluate("el => el.style.width") == before_width
        assert phone.locator("#zoomReset").text_content() == before_zoom

        assert not posts,posts
        assert not errors,errors
        phone.close()

        ipad=browser.new_page(viewport={"width":768,"height":1024})
        ipad.goto(url,wait_until="domcontentloaded",timeout=60000)
        ipad.locator("#progressListToggle").click()
        expect(ipad.locator("#progressListPanel")).to_be_visible()
        zoom_to_floor(ipad)
        ipad_width=ipad.locator("#canvas").evaluate("el => el.style.width")
        ipad_zoom=ipad.locator("#zoomReset").text_content()
        print("ipad before", ipad_width, ipad_zoom)
        ipad.set_viewport_size({"width":768,"height":900})
        ipad.wait_for_timeout(250)
        assert ipad.locator("#canvas").evaluate("el => el.style.width") == ipad_width
        assert ipad.locator("#zoomReset").text_content() == ipad_zoom
        ipad.close()

        browser.close()

    print("PUBLIC_USER_ONLY_FIT_FLOOR: PASS")

if __name__=="__main__":
    main()
