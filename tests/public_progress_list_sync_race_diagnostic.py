import json, os, random, time
from urllib.request import Request, urlopen
from playwright.sync_api import sync_playwright, expect

BASE="https://nakagawach.pythonanywhere.com/weld"

def get_json(path):
    req=Request(BASE+path,headers={"User-Agent":"weld-sync-race-check"})
    with urlopen(req,timeout=30) as r:return json.loads(r.read().decode())

def find_project():
    for p in get_json("/projects").get("projects",[]):
        name=str(p.get("projectName") or p.get("project_name") or "")
        if "初めのサンプルPDF" in name:return p["id"]
    raise RuntimeError("not found")

pid=find_project()
items=get_json(f"/projects/{pid}/progress-list-data")["items"]
by_page={}
for x in items: by_page.setdefault(x["pageNumber"],[]).append(x)
pages=[p for p,v in by_page.items() if len(v)>=2][:5]
print("pages",pages)

with sync_playwright() as p:
    b=p.chromium.launch()
    page=b.new_page(viewport={"width":390,"height":844})
    events=[]
    page.goto(f"{BASE}/projects/{pid}/progress?page=1",wait_until="domcontentloaded",timeout=60000)
    page.evaluate("""
      window.__syncEvents=[];
      for (const n of ['weld:progress-page-changing','weld:progress-page-loaded','weld:progress-selection','weld:progress-panel-target']) {
        window.addEventListener(n,e=>window.__syncEvents.push({n,t:performance.now(),d:e.detail||null,page:document.querySelector('#page')?.value}));
      }
    """)
    page.locator("#progressListToggle").click()
    expect(page.locator(".progress-list-record").first).to_be_visible(timeout=15000)

    failures=[]
    for cycle in range(20):
        target_page=pages[cycle%len(pages)]
        # click thumbnail/page nav if not current
        current=int(page.locator("#page").input_value())
        if current!=target_page:
            thumb=page.locator(f'.progress-thumb[data-page="{target_page}"]')
            if thumb.count():
                thumb.click()
            else:
                page.locator("#page").fill(str(target_page));page.locator("#page").press("Enter")
            try: expect(page.locator("#page")).to_have_value(str(target_page),timeout=10000)
            except Exception as e:
                failures.append(("page-not-change",cycle,current,target_page));continue
        arr=by_page[target_page]
        for item in arr[:2]:
            row=page.locator(".progress-list-record").filter(
                has=page.locator(".progress-list-number",has_text=str(item["number"]))
            ).filter(has=page.locator(".progress-list-page",has_text=f'P{target_page}')).first
            row.locator(".progress-list-focus").click()
            page.wait_for_timeout(80)
            cls=row.get_attribute("class") or ""
            sel=page.locator(".progress-list-record.selected")
            sk=page.evaluate("()=>window.__syncEvents.slice(-6)")
            if "selected" not in cls:
                failures.append(("not-selected",cycle,target_page,item["number"],cls,sk))
            if sel.count()!=1:
                failures.append(("selected-count",cycle,target_page,item["number"],sel.count(),sk))
        # rapid page next/back sequence
        if target_page < max(by_page):
            page.locator("#next").click()
            page.wait_for_timeout(20)
            page.locator("#prev").click()
            page.wait_for_timeout(300)
    print("FAILURES",json.dumps(failures,ensure_ascii=False,indent=2))
    print("LAST_EVENTS",json.dumps(page.evaluate("()=>window.__syncEvents.slice(-50)"),ensure_ascii=False,indent=2))
    b.close()
