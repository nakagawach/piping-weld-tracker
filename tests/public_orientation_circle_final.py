import json
from urllib.request import Request, urlopen
from playwright.sync_api import expect, sync_playwright

BASE="https://nakagawach.pythonanywhere.com/weld"
SCALE=1600/6000

def get_json(path):
    req=Request(BASE+path,headers={"User-Agent":"weld-orientation-circle-public"})
    with urlopen(req,timeout=30) as r:
        return json.loads(r.read().decode())

def find_project():
    for p in get_json("/projects").get("projects",[]):
        name=str(p.get("projectName") or p.get("project_name") or "")
        if "初めのサンプルPDF" in name:
            return p["id"]
    raise RuntimeError("初めのサンプルPDF not found")

def row(page,item):
    return page.locator(".progress-list-record").filter(
        has=page.locator(".progress-list-number",has_text=str(item["number"]))
    ).filter(
        has=page.locator(".progress-list-page",has_text=f'P{item["pageNumber"]}')
    ).first

def assert_visible(page):
    viewer=page.locator("#viewer").bounding_box()
    canvas=page.locator("#canvas").bounding_box()
    assert viewer and canvas
    assert viewer["height"]>80,viewer
    assert canvas["height"]>80,canvas
    assert page.locator("#canvas").is_visible()

def canvas_pixel(page,item):
    x=round(float(item["x"])*SCALE)
    y=round(float(item["y"])*SCALE)
    return page.locator("#canvas").evaluate(
        "(el,p)=>Array.from(el.getContext('2d').getImageData(p.x,p.y,1,1).data)",
        {"x":x,"y":y},
    )

def diff(a,b):
    return sum(abs(int(a[i])-int(b[i])) for i in range(3))

def main():
    pid=find_project()
    items=[x for x in get_json(f"/projects/{pid}/progress-list-data").get("items",[]) if x["pageNumber"]==1]
    assert len(items)>=2
    first,second=items[0],items[1]

    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={"width":768,"height":1024})
        errors=[];posts=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.on("console",lambda m:errors.append(m.text) if m.type=="error" else None)
        page.on("request",lambda r:posts.append(r.url) if r.method=="POST" else None)

        page.goto(f"{BASE}/projects/{pid}/progress?page=1",wait_until="domcontentloaded",timeout=60000)
        expect(page.locator("#progressListToggle")).to_be_visible(timeout=15000)
        page.locator("#progressListToggle").click()
        expect(page.locator("#progressListPanel")).to_be_visible(timeout=15000)
        expect(row(page,first)).to_be_visible(timeout=15000)
        assert_visible(page)

        # Portrait <-> landscape repeatedly with list open.
        for _ in range(5):
            page.set_viewport_size({"width":1024,"height":768})
            page.wait_for_timeout(140)
            expect(page.locator("#progressListPanel")).to_be_visible()
            assert_visible(page)
            panel=page.locator("#progressListPanel").bounding_box()
            assert panel and panel["x"]>600,panel

            page.set_viewport_size({"width":768,"height":1024})
            page.wait_for_timeout(140)
            expect(page.locator("#progressListPanel")).to_be_visible()
            assert_visible(page)
            panel=page.locator("#progressListPanel").bounding_box()
            assert panel and panel["y"]>450,panel

        # Immediate rotate right after reopening list.
        page.locator("#progressListClose").click()
        page.locator("#progressListToggle").click()
        page.set_viewport_size({"width":1024,"height":768})
        page.wait_for_timeout(160)
        assert_visible(page)

        # Circle-only marker: selected target center changes because rectangle is removed.
        before_first=canvas_pixel(page,first)
        row(page,first).locator(".progress-list-focus").click()
        expect(page.locator("#canvas")).to_have_attribute(
            "data-selected-target",
            f'1:{round(float(first["x"]))}:{round(float(first["y"]))}',
            timeout=15000,
        )
        page.wait_for_timeout(120)
        selected_first=canvas_pixel(page,first)
        assert diff(before_first,selected_first)>=8,(before_first,selected_first)

        # Move selection; first target rectangle should return close to original.
        row(page,second).locator(".progress-list-focus").click()
        expect(page.locator("#canvas")).to_have_attribute(
            "data-selected-target",
            f'1:{round(float(second["x"]))}:{round(float(second["y"]))}',
            timeout=15000,
        )
        page.wait_for_timeout(120)
        restored_first=canvas_pixel(page,first)
        assert diff(before_first,restored_first)<=6,(before_first,restored_first)

        assert not posts,posts
        assert not errors,errors
        browser.close()

    print("PUBLIC_ORIENTATION_CIRCLE_FINAL: PASS")

if __name__=="__main__":
    main()
