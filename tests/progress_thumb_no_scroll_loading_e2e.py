import base64
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from app import app
from tests.ui_shell_e2e import PROJECT_ID, seed_database

BASE_URL = "http://127.0.0.1:8770"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC0lEQVR42mP8/x8AAusB9Y9Z7ZQAAAAASUVORK5CYII="
)


def run_server():
    server = make_server("127.0.0.1", 8770, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def install_routes(page):
    page.route(
        f"**/projects/{PROJECT_ID}/pdfium-info",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"pageCount":24}',
        ),
    )

    def image_route(route):
        route.fulfill(status=200, content_type="image/png", body=PNG_1X1)

    page.route(f"**/projects/{PROJECT_ID}/pdfium-page**", image_route)


def open_ready(page):
    requests = []
    page.on(
        "request",
        lambda request: requests.append(request.url)
        if "/pdfium-page" in request.url or "/progress-data" in request.url
        else None,
    )
    page.goto(
        f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1",
        wait_until="domcontentloaded",
    )
    page.wait_for_function(
        "document.querySelectorAll('.progress-thumb').length === 24"
    )
    # Strip must not become horizontally interactive until every eager thumbnail settles.
    page.wait_for_function(
        "document.getElementById('progressThumbs').dataset.ready === '1'"
    )
    page.wait_for_function(
        "!document.getElementById('page').disabled && "
        "document.getElementById('page').value === '1'"
    )
    page.wait_for_timeout(100)
    assert page.locator("#progressThumbs img[src]").count() == 24
    return requests


def scroll_and_assert_no_network(page, requests, mobile):
    strip = page.locator("#progressThumbs")
    box = strip.bounding_box()
    assert box
    before = len(requests)

    if mobile:
        cdp = page.context.new_cdp_session(page)
        y = box["y"] + min(25, box["height"] / 2)
        start_x = box["x"] + box["width"] * 0.80
        end_x = box["x"] + box["width"] * 0.20
        cdp.send("Input.dispatchTouchEvent", {
            "type": "touchStart",
            "touchPoints": [{"x": start_x, "y": y}],
        })
        for step in range(1, 8):
            x = start_x + (end_x - start_x) * step / 7
            cdp.send("Input.dispatchTouchEvent", {
                "type": "touchMove",
                "touchPoints": [{"x": x, "y": y}],
            })
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    else:
        strip.evaluate(
            "el => { el.scrollLeft = Math.max(0, el.scrollWidth - el.clientWidth); el.dispatchEvent(new Event('scroll')); }"
        )

    page.wait_for_timeout(250)
    assert strip.evaluate("el => el.scrollLeft") > 0
    after_requests = requests[before:]
    assert not [url for url in after_requests if "/pdfium-page" in url], after_requests
    assert not [url for url in after_requests if "/progress-data" in url], after_requests
    assert page.locator("#page").input_value() == "1"
    assert "読み込み中" not in page.locator("#status").inner_text()


def deliberate_navigation(page, requests, mobile):
    before = len(requests)
    target = page.locator('.progress-thumb[data-page="2"]')
    if mobile:
        target.tap()
    else:
        target.click()
    page.wait_for_function(
        "document.getElementById('page').value === '2' && "
        "!document.getElementById('page').disabled"
    )
    new_requests = requests[before:]
    assert any("/progress-data?page=2" in url for url in new_requests), new_requests


def main():
    seed_database()
    server, thread = run_server()
    time.sleep(0.2)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()

            desktop = browser.new_page(viewport={"width": 1440, "height": 900})
            install_routes(desktop)
            desktop_requests = open_ready(desktop)
            scroll_and_assert_no_network(desktop, desktop_requests, mobile=False)
            deliberate_navigation(desktop, desktop_requests, mobile=False)
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
            install_routes(mobile)
            mobile_requests = open_ready(mobile)
            scroll_and_assert_no_network(mobile, mobile_requests, mobile=True)
            deliberate_navigation(mobile, mobile_requests, mobile=True)
            mobile_context.close()

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("PROGRESS_THUMB_NO_SCROLL_LOADING: PASS")


if __name__ == "__main__":
    main()
