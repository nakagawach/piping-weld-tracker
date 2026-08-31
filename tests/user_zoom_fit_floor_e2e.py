import sqlite3
import sys
import threading
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import DB_PATH, app
from tests.ui_shell_e2e import PROJECT_ID, seed_database

BASE="http://127.0.0.1:8774"
SVG='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000"><rect width="1600" height="1000" fill="white"/></svg>'


def seed_progress():
    seed_database()
    key=f"project:{PROJECT_ID}"
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM number_map WHERE drawing_key=?",(key,))
        c.execute(
            """INSERT INTO number_map(
              drawing_key,page_number,item_order,number_text,source,
              x,y,width,height,saved_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (key,1,0,"1","manual",1000,900,120,120,"2026-08-30T00:00:00+00:00"),
        )


def serve():
    server=make_server("127.0.0.1",8774,app)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    return server,thread


def stub(page):
    page.route(
        f"**/projects/{PROJECT_ID}/pdfium-info",
        lambda r:r.fulfill(status=200,content_type="application/json",body='{"pageCount":1}'),
    )
    page.route(
        f"**/projects/{PROJECT_ID}/pdfium-page**",
        lambda r:r.fulfill(status=200,content_type="image/svg+xml",body=SVG),
    )


def fit_assert(page):
    canvas=page.locator("#canvas").bounding_box()
    viewer=page.locator("#viewer").bounding_box()
    assert canvas and viewer
    assert canvas["width"] <= viewer["width"] + 3, (canvas,viewer)
    assert canvas["height"] <= viewer["height"] + 3, (canvas,viewer)
    assert min(
        abs(canvas["width"]-viewer["width"]),
        abs(canvas["height"]-viewer["height"]),
    ) <= 3, (canvas,viewer)


def zoom_to_floor(page):
    expect(page.locator("#zoomOut")).to_be_enabled(timeout=7000)
    for _ in range(8):
        page.locator("#zoomOut").evaluate("el => el.click()")
    page.wait_for_timeout(120)
    fit_assert(page)


def main():
    seed_progress()
    server,thread=serve()
    time.sleep(.2)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch()

            phone=browser.new_page(viewport={"width":390,"height":844})
            stub(phone)
            phone.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            expect(phone.locator("#progressListPanel")).to_be_visible(timeout=5000)
            expect(phone.locator("#progressListToggle")).to_have_attribute("aria-expanded","true")
            zoom_to_floor(phone)

            # Browser/UI viewport changes must not alter zoom by themselves.
            before_style=phone.locator("#canvas").get_attribute("style") or ""
            before_zoom=phone.locator("#zoomReset").text_content()
            phone.set_viewport_size({"width":390,"height":730})
            phone.wait_for_timeout(180)
            assert (phone.locator("#canvas").get_attribute("style") or "") == before_style
            assert phone.locator("#zoomReset").text_content() == before_zoom

            # Closing/opening the list changes viewer geometry, but not user zoom.
            phone.locator("#progressListClose").click()
            phone.wait_for_timeout(180)
            assert (phone.locator("#canvas").get_attribute("style") or "") == before_style
            assert phone.locator("#zoomReset").text_content() == before_zoom
            phone.locator("#progressListToggle").click()
            phone.wait_for_timeout(180)
            assert (phone.locator("#canvas").get_attribute("style") or "") == before_style

            # Fullscreen class/layout changes also must not auto-change zoom.
            phone.evaluate("document.body.classList.add('progress-fullscreen')")
            phone.wait_for_timeout(180)
            assert (phone.locator("#canvas").get_attribute("style") or "") == before_style
            assert phone.locator("#zoomReset").text_content() == before_zoom

            # If layout changed so current zoom is already below the new floor,
            # another shrink attempt must stay put, never jump upward.
            current_style=phone.locator("#canvas").get_attribute("style") or ""
            phone.locator("#zoomOut").evaluate("el => el.click()")
            phone.wait_for_timeout(80)
            assert (phone.locator("#canvas").get_attribute("style") or "") == current_style
            phone.close()

            ipad=browser.new_page(viewport={"width":768,"height":1024})
            stub(ipad)
            ipad.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1",wait_until="domcontentloaded")
            expect(ipad.locator("#progressListPanel")).to_be_visible(timeout=5000)
            expect(ipad.locator("#progressListToggle")).to_have_attribute("aria-expanded","true")
            zoom_to_floor(ipad)
            ipad_before=ipad.locator("#canvas").get_attribute("style") or ""
            ipad.set_viewport_size({"width":768,"height":900})
            ipad.wait_for_timeout(180)
            assert (ipad.locator("#canvas").get_attribute("style") or "") == ipad_before
            ipad.close()

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("USER_ZOOM_FIT_FLOOR_E2E: PASS")


if __name__=="__main__":
    main()
