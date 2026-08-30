import json
import os
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright

BASE=os.environ.get("PUBLIC_BASE_URL","https://nakagawach.pythonanywhere.com/weld").rstrip("/")

def get_json(path):
    req=Request(f"{BASE}{path}",headers={"User-Agent":"weld-v3-public-check"})
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

def aligned(page):
    base=page.locator("#canvas").bounding_box()
    memo=page.locator("#drawingMemoCanvas").bounding_box()
    assert base and memo
    assert abs(base["x"]-memo["x"]) <= 1.5,(base,memo)
    assert abs(base["y"]-memo["y"]) <= 1.5,(base,memo)
    assert abs(base["width"]-memo["width"]) <= 1.5,(base,memo)

def main():
    project_id=find_project()
    items=get_json(f"/projects/{project_id}/progress-list-data").get("items",[])
    p3=next(x for x in items if str(x["number"])=="3" and x["pageNumber"]==1)
    p8=next(x for x in items if str(x["number"])=="8" and x["pageNumber"]==1)
    url=f"{BASE}/projects/{project_id}/progress?page=1"

    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={"width":390,"height":844})
        errors=[];posts=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.on("console",lambda m:errors.append(m.text) if m.type=="error" else None)
        page.on("request",lambda r:posts.append(r.url) if r.method=="POST" else None)
        page.goto(url,wait_until="domcontentloaded",timeout=60000)

        expect(page.locator("#progressListToggle")).to_be_visible(timeout=15000)
        expect(page.locator("#drawingMemoCanvas")).to_be_visible(timeout=15000)
        page.locator("#progressListToggle").click()
        expect(row(page,3)).to_be_visible(timeout=15000)

        panel=page.locator("#progressListPanel").bounding_box()
        viewer=page.locator("#viewer").bounding_box()
        assert panel and viewer
        assert viewer["y"]+viewer["height"] <= panel["y"]+2,(viewer,panel)

        row(page,3).locator(".progress-list-focus").click()
        expect(page.locator("#canvas")).to_have_attribute(
            "data-selected-target",f"1:{round(p3['x'])}:{round(p3['y'])}",timeout=15000
        )
        row(page,8).locator(".progress-list-focus").click()
        expect(page.locator("#canvas")).to_have_attribute(
            "data-selected-target",f"1:{round(p8['x'])}:{round(p8['y'])}",timeout=15000
        )
        assert "selected" in (row(page,8).get_attribute("class") or "")
        assert "selected" not in (row(page,3).get_attribute("class") or "")

        aligned(page)
        page.locator("#canvas").evaluate("el => { el.style.width='50%'; }")
        page.wait_for_timeout(150)
        aligned(page)
        page.locator("#canvas").evaluate("el => { el.style.width='75%'; }")
        page.wait_for_timeout(150)
        aligned(page)

        assert not posts,posts
        assert not errors,errors
        browser.close()

    print("PUBLIC_NORMAL_LIST_MEMO_V3: PASS")

if __name__=="__main__": main()
