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

BASE_URL = "http://127.0.0.1:8768"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z7ZQAAAAASUVORK5CYII="
)


def run_server():
    server = make_server("127.0.0.1", 8768, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def main():
    seed_database()
    server, thread = run_server()
    time.sleep(0.2)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
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
            page.route(
                f"**/projects/{PROJECT_ID}/pdfium-info",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body='{"pageCount":12}',
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

            progress_requests = []
            page.on(
                "request",
                lambda request: progress_requests.append(request.url)
                if "/progress-data?page=" in request.url
                else None,
            )

            page.goto(
                f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1",
                wait_until="domcontentloaded",
            )
            page.wait_for_function(
                "document.querySelectorAll('.progress-thumb').length === 12 && "
                "document.getElementById('page').value === '1' && "
                "!document.getElementById('page').disabled"
            )
            page.wait_for_timeout(150)
            progress_requests.clear()

            strip = page.locator("#progressThumbs")
            before_status = page.locator("#status").inner_text()

            # Real Chromium horizontal touch-scroll must not change the selected page.
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
            for step in range(1, 7):
                x = start_x + (end_x - start_x) * step / 6
                cdp.send("Input.dispatchTouchEvent", {
                    "type": "touchMove",
                    "touchPoints": [{"x": x, "y": y}],
                })
            cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            page.wait_for_timeout(250)
            scroll_left = strip.evaluate("el => el.scrollLeft")
            assert scroll_left > 0, scroll_left
            assert page.locator("#page").input_value() == "1"
            assert progress_requests == [], progress_requests
            assert "読み込み中" not in page.locator("#status").inner_text()

            # Reproduce a drag that is followed by an accidental click on a thumbnail.
            p2 = page.locator('.progress-thumb[data-page="2"]')
            p2.dispatch_event("pointerdown", {
                "pointerId": 41,
                "pointerType": "touch",
                "clientX": 260,
                "clientY": 180,
                "button": 0,
                "buttons": 1,
            })
            p2.dispatch_event("pointermove", {
                "pointerId": 41,
                "pointerType": "touch",
                "clientX": 190,
                "clientY": 180,
                "button": -1,
                "buttons": 1,
            })
            p2.dispatch_event("pointerup", {
                "pointerId": 41,
                "pointerType": "touch",
                "clientX": 190,
                "clientY": 180,
                "button": 0,
                "buttons": 0,
            })
            p2.dispatch_event("click")
            page.wait_for_timeout(250)

            assert page.locator("#page").input_value() == "1", (
                "thumbnail drag caused page navigation"
            )
            assert progress_requests == [], progress_requests
            assert page.locator("#status").inner_text() == before_status

            # A deliberate tap on another thumbnail must still navigate.
            p2.tap()
            page.wait_for_function(
                "document.getElementById('page').value === '2' && "
                "!document.getElementById('page').disabled"
            )
            assert any("/progress-data?page=2" in url for url in progress_requests)

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("PROGRESS_THUMB_SCROLL_NO_LOAD: PASS")


if __name__ == "__main__":
    main()
