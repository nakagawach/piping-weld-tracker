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

BASE_URL = "http://127.0.0.1:8769"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z7ZQAAAAASUVORK5CYII="
)


def run_server():
    server = make_server("127.0.0.1", 8769, app)
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
    page.route(
        f"**/projects/{PROJECT_ID}/pdfium-page**",
        lambda route: route.fulfill(
            status=200,
            content_type="image/png",
            body=PNG_1X1,
        ),
    )


def open_progress(page):
    requests = []
    page.on(
        "request",
        lambda request: requests.append(request.url)
        if "/progress-data?page=" in request.url
        else None,
    )
    page.goto(
        f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1",
        wait_until="domcontentloaded",
    )
    page.wait_for_function(
        "document.querySelectorAll('.progress-thumb').length === 24 && "
        "document.getElementById('page').value === '1' && "
        "!document.getElementById('page').disabled"
    )
    page.wait_for_timeout(150)
    requests.clear()
    return requests


def assert_no_page_load(page, requests, label):
    page.wait_for_timeout(250)
    assert page.locator("#page").input_value() == "1", label
    assert requests == [], (label, requests)
    assert "読み込み中" not in page.locator("#status").inner_text(), (
        label,
        page.locator("#status").inner_text(),
    )


def desktop_case(browser):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    install_routes(page)
    requests = open_progress(page)
    strip = page.locator("#progressThumbs")
    box = strip.bounding_box()
    assert box

    # PC trackpad/mouse horizontal scroll itself must not navigate.
    page.mouse.move(box["x"] + box["width"] * 0.6, box["y"] + box["height"] * 0.5)
    page.mouse.wheel(500, 0)
    page.wait_for_timeout(120)
    assert strip.evaluate("el => el.scrollLeft") > 0
    assert_no_page_load(page, requests, "desktop scroll itself loaded a page")

    # Browsers can deliver a click after a scroll/drag interaction.
    # That click must be ignored during the scroll-suppression window.
    p2 = page.locator('.progress-thumb[data-page="2"]')
    p2.dispatch_event("click")
    assert_no_page_load(page, requests, "desktop post-scroll click loaded a page")

    # After the suppression window, a deliberate click still navigates.
    page.wait_for_timeout(600)
    p2.click()
    page.wait_for_function(
        "document.getElementById('page').value === '2' && "
        "!document.getElementById('page').disabled"
    )
    assert any("/progress-data?page=2" in url for url in requests)
    page.close()


def mobile_case(browser):
    context = browser.new_context(
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
    page = context.new_page()
    install_routes(page)
    requests = open_progress(page)
    strip = page.locator("#progressThumbs")
    box = strip.bounding_box()
    assert box

    cdp = context.new_cdp_session(page)
    y = box["y"] + box["height"] / 2
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
    page.wait_for_timeout(120)
    assert strip.evaluate("el => el.scrollLeft") > 0
    assert_no_page_load(page, requests, "mobile touch-scroll itself loaded a page")

    p2 = page.locator('.progress-thumb[data-page="2"]')
    p2.dispatch_event("click")
    assert_no_page_load(page, requests, "mobile post-scroll click loaded a page")

    page.wait_for_timeout(600)
    p2.tap()
    page.wait_for_function(
        "document.getElementById('page').value === '2' && "
        "!document.getElementById('page').disabled"
    )
    assert any("/progress-data?page=2" in url for url in requests)
    context.close()


def main():
    seed_database()
    server, thread = run_server()
    time.sleep(0.2)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            desktop_case(browser)
            mobile_case(browser)
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("PROGRESS_THUMB_SCROLL_ACTIVATION_GUARD: PASS")


if __name__ == "__main__":
    main()
