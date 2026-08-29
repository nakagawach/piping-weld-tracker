import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://nakagawach.pythonanywhere.com/weld"
ARTIFACTS = Path("test-artifacts")
ARTIFACTS.mkdir(exist_ok=True)


def discover_progress_url(browser):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    try:
        page.goto(f"{BASE}/projects-screen", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector("[data-progress]", timeout=60000)
        progress_path = page.locator("[data-progress]").first.get_attribute("data-progress")
        if not progress_path:
            raise AssertionError("no progress target found from projects-screen")
        return f"{BASE}/{progress_path.lstrip('/')}"
    finally:
        page.close()


def wait_progress_ready(page):
    page.wait_for_selector("#progressThumbs", timeout=60000)
    page.wait_for_function(
        "document.querySelectorAll('.progress-thumb').length > 1",
        timeout=60000,
    )
    page.wait_for_function(
        "document.getElementById('status').textContent.includes('ピンチ・移動・回転・全画面')",
        timeout=60000,
    )
    page.wait_for_timeout(300)


def run_case(page, label, progress_url, mobile=False):
    requests = []
    page.on("request", lambda req: requests.append((time.time(), req.url, req.resource_type)))
    page.goto(progress_url, wait_until="domcontentloaded", timeout=60000)
    wait_progress_ready(page)

    strip = page.locator("#progressThumbs")
    box = strip.bounding_box()
    assert box
    before = {
        "page": page.locator("#page").input_value(),
        "status": page.locator("#status").inner_text(),
        "scrollLeft": strip.evaluate("el => el.scrollLeft"),
        "scrollWidth": strip.evaluate("el => el.scrollWidth"),
        "clientWidth": strip.evaluate("el => el.clientWidth"),
        "pageDisabled": page.locator("#page").is_disabled(),
        "loadedImages": strip.locator("img[src]").count(),
        "canvasHidden": page.locator("#canvas").evaluate("el => el.hidden"),
        "canvasSize": page.locator("#canvas").evaluate("el => [el.width,el.height]"),
        "emptyHidden": page.locator("#empty").evaluate("el => el.hidden"),
        "emptyText": page.locator("#empty").inner_text(),
        "viewerScrollTop": page.locator("#viewer").evaluate("el => el.scrollTop"),
    }
    page.screenshot(path=str(ARTIFACTS / f"live-{label}-before.png"), full_page=False)
    before_count = len(requests)

    if mobile:
        context = page.context
        cdp = context.new_cdp_session(page)
        y = box["y"] + min(box["height"] / 2, 25)
        start_x = box["x"] + box["width"] * 0.80
        end_x = box["x"] + box["width"] * 0.20
        cdp.send("Input.dispatchTouchEvent", {
            "type": "touchStart",
            "touchPoints": [{"x": start_x, "y": y}],
        })
        for step in range(1, 9):
            x = start_x + (end_x - start_x) * step / 8
            cdp.send("Input.dispatchTouchEvent", {
                "type": "touchMove",
                "touchPoints": [{"x": x, "y": y}],
            })
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    else:
        # Move the strip far enough to expose thumbnails that were previously off-screen.
        strip.evaluate("el => {el.scrollLeft=Math.max(0,el.scrollWidth-el.clientWidth);el.dispatchEvent(new Event('scroll'))}")

    page.wait_for_timeout(1500)
    after = {
        "page": page.locator("#page").input_value(),
        "status": page.locator("#status").inner_text(),
        "scrollLeft": strip.evaluate("el => el.scrollLeft"),
        "pageDisabled": page.locator("#page").is_disabled(),
        "loadedImages": strip.locator("img[src]").count(),
        "canvasHidden": page.locator("#canvas").evaluate("el => el.hidden"),
        "canvasSize": page.locator("#canvas").evaluate("el => [el.width,el.height]"),
        "emptyHidden": page.locator("#empty").evaluate("el => el.hidden"),
        "emptyText": page.locator("#empty").inner_text(),
        "viewerScrollTop": page.locator("#viewer").evaluate("el => el.scrollTop"),
        "bodyLoadingTexts": page.locator("body").evaluate("el => (el.innerText.match(/[^\\n]*読み込[^\\n]*/g)||[])"),
    }
    page.screenshot(path=str(ARTIFACTS / f"live-{label}-after.png"), full_page=False)

    new_requests = requests[before_count:]
    pdfium = [u for _,u,_ in new_requests if "/pdfium-page" in u]
    pdata = [u for _,u,_ in new_requests if "/progress-data" in u]

    print(label.upper(), "BEFORE", before)
    print(label.upper(), "AFTER", after)
    print(label.upper(), "NEW_PDFIUM_PAGE_REQUESTS", len(pdfium))
    for u in pdfium[:50]:
        print(label.upper(), "PDFIUM", u)
    print(label.upper(), "NEW_PROGRESS_DATA_REQUESTS", len(pdata))
    for u in pdata[:20]:
        print(label.upper(), "PROGRESS_DATA", u)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        progress_url = discover_progress_url(browser)
        print("LIVE_PROGRESS_URL", progress_url)

        for width in (1440, 1024, 820):
            desktop = browser.new_page(viewport={"width": width, "height": 900})
            run_case(desktop, f"desktop-{width}", progress_url, mobile=False)
            desktop.close()

        mobile_context = browser.new_context(
            viewport={"width": 390, "height": 844},
            screen={"width": 390, "height": 844},
            device_scale_factor=2.75,
            is_mobile=True,
            has_touch=True,
            user_agent=(
                "Mozilla/5.0 (Linux; Android 16; Pixel 7 Pro) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36"
            ),
        )
        mobile = mobile_context.new_page()
        run_case(mobile, "mobile", progress_url, mobile=True)
        mobile_context.close()

        browser.close()

    print("LIVE_SCROLL_DIAGNOSTIC: PASS")


if __name__ == "__main__":
    main()
