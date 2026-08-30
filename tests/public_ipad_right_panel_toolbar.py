import json
from urllib.request import Request, urlopen
from playwright.sync_api import expect, sync_playwright

BASE="https://nakagawach.pythonanywhere.com/weld"

def get_json(path):
    req=Request(BASE+path,headers={"User-Agent":"weld-ipad-toolbar-public"})
    with urlopen(req,timeout=30) as r:
        return json.loads(r.read().decode())

def find_project():
    for p in get_json("/projects").get("projects",[]):
        name=str(p.get("projectName") or p.get("project_name") or "")
        if "初めのサンプルPDF" in name:
            return p["id"]
    raise RuntimeError("初めのサンプルPDF not found")

def assert_clear(page):
    panel=page.locator("#progressListPanel").bounding_box()
    fs=page.locator("#fullscreen").bounding_box()
    rot=page.locator("#rotate").bounding_box()
    assert panel and fs and rot
    assert fs["x"]+fs["width"] <= panel["x"]+1,(fs,panel)
    assert rot["x"]+rot["width"] <= panel["x"]+1,(rot,panel)

def main():
    pid=find_project()
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={"width":1024,"height":768})
        errors=[];posts=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.on("console",lambda m:errors.append(m.text) if m.type=="error" else None)
        page.on("request",lambda r:posts.append(r.url) if r.method=="POST" else None)

        page.goto(f"{BASE}/projects/{pid}/progress?page=1",wait_until="domcontentloaded",timeout=60000)
        expect(page.locator("#progressListToggle")).to_be_visible(timeout=15000)
        page.locator("#progressListToggle").click()
        expect(page.locator("#progressListPanel")).to_be_visible()
        expect(page.locator("#rotate")).to_be_visible()
        expect(page.locator("#fullscreen")).to_be_visible()
        expect(page.locator("#zoomOut")).not_to_be_visible()
        expect(page.locator("#zoomIn")).not_to_be_visible()
        assert_clear(page)

        page.locator("#fullscreen").click()
        expect(page.locator("body")).to_have_class(__import__("re").compile(r".*progress-fullscreen.*"),timeout=5000)
        expect(page.locator("#progressListPanel")).to_be_visible()
        expect(page.locator("#fullscreen")).to_be_visible()
        assert_clear(page)

        page.locator("#fullscreen").click()
        expect(page.locator("body")).not_to_have_class(__import__("re").compile(r".*progress-fullscreen.*"),timeout=5000)
        expect(page.locator("#rotate")).to_be_visible()

        assert not posts,posts
        assert not errors,errors
        browser.close()

    print("PUBLIC_IPAD_RIGHT_PANEL_TOOLBAR: PASS")

if __name__=="__main__":
    main()
