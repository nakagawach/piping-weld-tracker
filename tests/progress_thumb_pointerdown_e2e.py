import base64
import sqlite3
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from app import DB_PATH, app
from tests.ui_shell_e2e import PROJECT_ID, seed_database

BASE_URL = "http://127.0.0.1:8771"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z7ZQAAAAASUVORK5CYII="
)


def seed_progress_pages():
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("DELETE FROM number_map WHERE drawing_key = ?", (f"project:{PROJECT_ID}",))
        for page_number in (1, 2, 3):
            connection.execute(
                """
                INSERT INTO number_map (
                    drawing_key, page_number, item_order, number_text, source,
                    x, y, width, height, saved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"project:{PROJECT_ID}",
                    page_number,
                    0,
                    str(page_number),
                    "manual",
                    100.0,
                    100.0,
                    80.0,
                    80.0,
                    "2026-08-29T00:00:00+00:00",
                ),
            )


def run_server():
    server = make_server("127.0.0.1", 8771, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def install_routes(page):
    page.route(
        f"**/projects/{PROJECT_ID}/pdfium-info",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"pageCount":3}',
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


def wait_ready(page):
    page.wait_for_function(
        "document.querySelectorAll('.progress-thumb').length === 3 && "
        "document.getElementById('page').value === '1' && "
        "!document.getElementById('page').disabled && "
        "!document.getElementById('canvas').hidden"
    )
    page.wait_for_timeout(100)


def assert_viewer_stays_visible_on_press(page, target, label):
    canvas = page.locator("#canvas")
    empty = page.locator("#empty")
    assert not canvas.evaluate("el => el.hidden"), f"{label}: canvas hidden before press"
    assert empty.evaluate("el => el.hidden"), f"{label}: empty visible before press"

    target.dispatch_event("pointerdown", {
        "pointerId": 91,
        "pointerType": "touch",
        "clientX": 180,
        "clientY": 120,
        "button": 0,
        "buttons": 1,
    })
    page.wait_for_timeout(50)

    assert not canvas.evaluate("el => el.hidden"), (
        f"{label}: mere pointerdown hid the drawing before any page activation"
    )
    assert empty.evaluate("el => el.hidden"), (
        f"{label}: mere pointerdown showed the loading placeholder"
    )
    assert "読み込んでいます" not in page.locator("body").inner_text(), (
        f"{label}: mere pointerdown exposed loading text"
    )

    target.dispatch_event("pointerup", {
        "pointerId": 91,
        "pointerType": "touch",
        "clientX": 180,
        "clientY": 120,
        "button": 0,
        "buttons": 0,
    })


def desktop_case(browser):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    install_routes(page)
    page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
    wait_ready(page)
    assert_viewer_stays_visible_on_press(
        page, page.locator('.progress-thumb[data-page="2"]'), "desktop"
    )
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
    page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
    wait_ready(page)
    assert_viewer_stays_visible_on_press(
        page, page.locator('.progress-thumb[data-page="2"]'), "mobile"
    )
    context.close()


def main():
    seed_database()
    seed_progress_pages()
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

    print("PROGRESS_THUMB_POINTERDOWN_NO_LOADING: PASS")


if __name__ == "__main__":
    main()
