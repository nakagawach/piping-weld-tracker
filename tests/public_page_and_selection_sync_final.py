import json
import re
from urllib.request import Request, urlopen
from playwright.sync_api import expect, sync_playwright

BASE="https://nakagawach.pythonanywhere.com/weld"

def get_json(path):
    req=Request(BASE+path,headers={"User-Agent":"weld-page-sync-public-final"})
    with urlopen(req,timeout=30) as r:return json.loads(r.read().decode())

def find_project():
    for p in get_json("/projects").get("projects",[]):
        name=str(p.get("projectName") or p.get("project_name") or "")
        if "初めのサンプルPDF" in name:return p["id"]
    raise RuntimeError("初めのサンプルPDF not found")

def row(page,number,page_number):
    return page.locator(".progress-list-record").filter(
        has=page.locator(".progress-list-number",has_text=str(number))
    ).filter(has=page.locator(".progress-list-page",has_text=f"P{page_number}")).first

def assert_current_page_rows(page,n):
    current=page.locator(".progress-list-record.current-page")
    assert current.count()>=1,(n,current.count())
    for i in range(current.count()):
        assert current.nth(i).locator(".progress-list-page").text_content()==f"P{n}"

def main():
    pid=find_project()
    items=get_json(f"/projects/{pid}/progress-list-data").get("items",[])
    assert any(str(x["number"])=="14" and x["pageNumber"]==3 for x in items)
    url=f"{BASE}/projects/{pid}/progress?page=1"

    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={"width":390,"height":844})
        errors=[];posts=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.on("console",lambda m:errors.append(m.text) if m.type=="error" else None)
        page.on("request",lambda r:posts.append(r.url) if r.method=="POST" else None)

        page.goto(url,wait_until="domcontentloaded",timeout=60000)
        page.locator("#progressListToggle").click()
        expect(page.locator(".progress-list-record").first).to_be_visible(timeout=15000)

        # Real 1px drift case: list center 2050, drawing event center 2051.
        r14=row(page,14,3)
        r14.locator(".progress-list-focus").click()
        expect(page.locator("#page")).to_have_value("3",timeout=15000)
        expect(page.locator("#canvas")).to_have_attribute(
            "data-selected-target",re.compile(r"^3:\d+:\d+$"),timeout=15000
        )
        page.wait_for_timeout(500)
        assert "selected" in (r14.get_attribute("class") or "")
        assert page.locator(".progress-list-record.selected").count()==1

        # Return to P1 and verify current-page state.
        page.locator('.progress-thumb[data-page="1"]').click()
        expect(page.locator("#page")).to_have_value("1",timeout=15000)
        page.wait_for_timeout(150)
        assert_current_page_rows(page,1)

        # Start P2, then while busy request P3 and finally P1.
        page.locator('.progress-thumb[data-page="2"]').click(no_wait_after=True)
        expect(page.locator("#page")).to_have_value("2",timeout=3000)
        page.locator('.progress-thumb[data-page="3"]').click(no_wait_after=True,force=True)
        page.locator('.progress-thumb[data-page="1"]').click(no_wait_after=True,force=True)
        expect(page.locator("#page")).to_have_value("1",timeout=15000)
        page.wait_for_timeout(350)
        assert page.locator("#page").input_value()=="1"
        assert_current_page_rows(page,1)

        # Repeat with P3 as the latest request.
        page.locator('.progress-thumb[data-page="2"]').click(no_wait_after=True)
        expect(page.locator("#page")).to_have_value("2",timeout=3000)
        page.locator('.progress-thumb[data-page="1"]').click(no_wait_after=True,force=True)
        page.locator('.progress-thumb[data-page="3"]').click(no_wait_after=True,force=True)
        expect(page.locator("#page")).to_have_value("3",timeout=15000)
        page.wait_for_timeout(350)
        assert_current_page_rows(page,3)

        # Latest row selection only.
        page1=[x for x in items if x["pageNumber"]==1][:2]
        page.locator('.progress-thumb[data-page="1"]').click()
        expect(page.locator("#page")).to_have_value("1",timeout=15000)
        r1=row(page,page1[0]["number"],1)
        r2=row(page,page1[1]["number"],1)
        r1.locator(".progress-list-focus").click()
        r2.locator(".progress-list-focus").click()
        page.wait_for_timeout(350)
        assert "selected" in (r2.get_attribute("class") or "")
        assert "selected" not in (r1.get_attribute("class") or "")
        assert page.locator(".progress-list-record.selected").count()==1

        assert not posts,posts
        assert not errors,errors
        browser.close()

    print("PUBLIC_PAGE_AND_SELECTION_SYNC_FINAL: PASS")

if __name__=="__main__":main()
