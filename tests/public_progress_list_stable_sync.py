import json
import re
from urllib.request import Request, urlopen
from playwright.sync_api import expect, sync_playwright

BASE="https://nakagawach.pythonanywhere.com/weld"

def get_json(path):
    req=Request(BASE+path,headers={"User-Agent":"weld-stable-sync-public-check"})
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

def main():
    pid=find_project()
    items=get_json(f"/projects/{pid}/progress-list-data").get("items",[])
    target=next(x for x in items if str(x["number"])=="14" and x["pageNumber"]==3)
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

        r14=row(page,14,3)
        r14.locator(".progress-list-focus").click()
        expect(page.locator("#page")).to_have_value("3",timeout=15000)
        expect(page.locator("#canvas")).to_have_attribute("data-selected-target",re.compile(r"^3:\d+:\d+$"),timeout=15000)
        page.wait_for_timeout(400)
        assert "selected" in (r14.get_attribute("class") or ""),r14.get_attribute("class")
        assert page.locator(".progress-list-record.selected").count()==1

        for target_page in [1,3,2,1]:
            thumb=page.locator(f'.progress-thumb[data-page="{target_page}"]')
            expect(thumb).to_be_visible(timeout=15000)
            thumb.click()
            expect(page.locator("#page")).to_have_value(str(target_page),timeout=15000)
            page.wait_for_timeout(120)
            current=page.locator(".progress-list-record.current-page")
            assert current.count()>=1,(target_page,current.count())
            for i in range(current.count()):
                assert current.nth(i).locator(".progress-list-page").text_content()==f"P{target_page}"

        # Latest selection only.
        page1=[x for x in items if x["pageNumber"]==1][:2]
        assert len(page1)>=2
        r1=row(page,page1[0]["number"],1)
        r2=row(page,page1[1]["number"],1)
        r1.locator(".progress-list-focus").click()
        r2.locator(".progress-list-focus").click()
        page.wait_for_timeout(300)
        assert "selected" in (r2.get_attribute("class") or "")
        assert "selected" not in (r1.get_attribute("class") or "")
        assert page.locator(".progress-list-record.selected").count()==1

        assert not posts,posts
        assert not errors,errors
        browser.close()

    print("PUBLIC_PROGRESS_LIST_STABLE_SYNC: PASS")

if __name__=="__main__":main()
