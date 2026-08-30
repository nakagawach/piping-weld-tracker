from playwright.sync_api import expect, sync_playwright

URL="https://nakagawach.pythonanywhere.com/weld/mock/progress-fixed-layout"

def assert_no_body_scroll(page):
    v=page.evaluate("()=>({a:document.documentElement.scrollHeight,b:document.documentElement.clientHeight,c:document.body.scrollHeight,d:document.body.clientHeight})")
    assert v["a"]<=v["b"]+1,v
    assert v["c"]<=v["d"]+1,v

def main():
    with sync_playwright() as p:
        browser=p.chromium.launch()

        # Public projects screen: mock launch appears immediately left of favorites.
        home=browser.new_page(viewport={"width":1024,"height":768})
        home.goto("https://nakagawach.pythonanywhere.com/weld/projects-screen",wait_until="domcontentloaded",timeout=60000)
        expect(home.locator('[data-progress-mock]')).to_be_visible(timeout=15000)
        expect(home.locator('[data-ui3-favorites]')).to_be_visible(timeout=15000)
        mb=home.locator('[data-progress-mock]').bounding_box();fb=home.locator('[data-ui3-favorites]').bounding_box()
        assert mb and fb and mb["x"]<fb["x"],(mb,fb)
        home.locator('[data-progress-mock]').click()
        expect(home).to_have_url(__import__("re").compile(r"/weld/mock/progress-fixed-layout$"),timeout=15000)
        home.close()

        for name,size in [
            ("ipad-landscape",{"width":1024,"height":768}),
            ("ipad-portrait",{"width":768,"height":1024}),
            ("phone",{"width":390,"height":844}),
        ]:
            page=browser.new_page(viewport=size)
            posts=[];errors=[]
            page.on("request",lambda r:posts.append(r.url) if r.method=="POST" else None)
            page.on("pageerror",lambda e:errors.append(str(e)))
            page.goto(URL,wait_until="domcontentloaded",timeout=60000)
            expect(page.locator("#loading")).not_to_be_visible(timeout=30000)
            expect(page.locator("#projectTitle")).to_contain_text("初めのサンプルPDF")
            expect(page.locator(".row").first).to_be_visible(timeout=20000)
            assert_no_body_scroll(page)
            expect(page.locator("#mode")).to_have_text("FIT")
            if name=="ipad-landscape":
                # Public rotation: 4 quarter-turns keep FIT and return to 0deg.
                for expected in (90,180,270,0):
                    page.locator("#rotate").click()
                    expect(page.locator("#rotate")).to_contain_text(f"{expected}°")
                    expect(page.locator("#mode")).to_have_text("FIT")
                    page.wait_for_timeout(80)
                    rv=page.locator("#viewer").bounding_box();rs=page.locator("#stage").bounding_box()
                    assert rv and rs
                    assert rs["width"]<=rv["width"]+4 and rs["height"]<=rv["height"]+4,(expected,rs,rv)
                page.locator("#zoomIn").click()
                expect(page.locator("#mode")).to_have_text("MANUAL")
                style_before=page.locator("#stage").get_attribute("style")
                page.locator("#rotate").click()
                page.wait_for_timeout(80)
                assert page.locator("#mode").text_content()=="MANUAL"
                import re as _re
                def scale_of(style):
                    m=_re.search(r"scale\(([^)]+)\)",style or "")
                    return float(m.group(1)) if m else None
                style_after=page.locator("#stage").get_attribute("style")
                assert abs(scale_of(style_before)-scale_of(style_after))<1e-9,(style_before,style_after)
                page.locator("#fit").click()
                expect(page.locator("#mode")).to_have_text("FIT")
            viewer=page.locator("#viewer").bounding_box()
            stage=page.locator("#stage").bounding_box()
            assert viewer and stage
            assert stage["width"]<=viewer["width"]+4,(name,stage,viewer)
            assert stage["height"]<=viewer["height"]+4,(name,stage,viewer)
            if name=="ipad-landscape":
                panel=page.locator("#panel").bounding_box()
                assert panel and 308<=panel["width"]<=324,panel
            else:
                ws=page.locator("#workspace").bounding_box()
                panel=page.locator("#panel").bounding_box()
                assert ws and panel
                assert .35<=panel["height"]/ws["height"]<=.48,(name,ws,panel)
            page.locator("#records").evaluate("el=>el.scrollTop=300")
            page.wait_for_timeout(80)
            if page.locator("#records").evaluate("el=>el.scrollHeight>el.clientHeight"):
                assert page.locator("#records").evaluate("el=>el.scrollTop")>0
            assert not posts,(name,posts)
            assert not errors,(name,errors)
            page.close()
        browser.close()
    print("PUBLIC_FIXED_PROGRESS_MOCK: PASS")

if __name__=="__main__":
    main()
