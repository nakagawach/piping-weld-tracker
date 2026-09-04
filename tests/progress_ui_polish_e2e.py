import re
import sqlite3
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import DB_PATH, app
from tests.ui_shell_e2e import PROJECT_ID, seed_database

BASE = "http://127.0.0.1:8795"
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900"><rect width="1600" height="900" fill="white"/></svg>'


def seed_progress():
    seed_database()
    key = f"project:{PROJECT_ID}"
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("DELETE FROM number_map WHERE drawing_key=?", (key,))
        connection.execute(
            """INSERT INTO number_map(
              drawing_key,page_number,item_order,number_text,source,x,y,width,height,saved_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (key, 1, 0, "1", "manual", 300, 300, 120, 120, "2026-09-04T00:00:00+00:00"),
        )


def main():
    seed_progress()
    server = make_server("127.0.0.1", 8795, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.15)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.route(
                f"**/projects/{PROJECT_ID}/pdfium-info",
                lambda route: route.fulfill(status=200, content_type="application/json", body='{"pageCount":1}'),
            )
            page.route(
                f"**/projects/{PROJECT_ID}/pdfium-page**",
                lambda route: route.fulfill(status=200, content_type="image/svg+xml", body=SVG),
            )
            page.goto(f"{BASE}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
            expect(page.locator("#canvas")).to_be_visible(timeout=7000)
            expect(page.locator("#progressListPanel")).to_be_visible(timeout=5000)
            page.wait_for_timeout(180)

            # Fullscreen and close remain distinct controls in both states.
            fullscreen = page.locator("#progressListFullscreen")
            close = page.locator("#progressListClose")
            expect(fullscreen.locator("svg")).to_have_count(1)
            expect(fullscreen).to_have_attribute("aria-label", "進捗一覧を全画面表示")
            assert fullscreen.text_content().strip() != "×"
            assert close.text_content().strip() == "×"

            fullscreen.click()
            expect(page.locator("body")).to_have_class(re.compile(r".*progress-list-fullscreen.*"))
            expect(fullscreen).to_have_attribute("aria-label", "進捗一覧を元のサイズに戻す")
            expect(fullscreen.locator("svg")).to_have_count(1)
            assert fullscreen.text_content().strip() != "×"
            assert close.text_content().strip() == "×"

            fullscreen.click()
            expect(page.locator("body")).not_to_have_class(re.compile(r".*progress-list-fullscreen.*"))

            # Memo toolbar keeps comfortable touch targets and scrolls instead of squeezing controls.
            page.locator("#drawingMemoEdit").click()
            tools = page.locator("#drawingMemoTools")
            expect(tools).to_be_visible()
            color_box = page.locator(".memo-color").first.bounding_box()
            thin_box = page.locator('[data-memo-width="12"]').bounding_box()
            eraser_box = page.locator("#memoEraser").bounding_box()
            undo_box = page.locator("#memoUndo").bounding_box()
            assert color_box and color_box["width"] >= 35 and color_box["height"] >= 35, color_box
            assert thin_box and thin_box["width"] >= 47 and thin_box["height"] >= 41, thin_box
            assert eraser_box and eraser_box["width"] >= 80 and eraser_box["height"] >= 41, eraser_box
            assert undo_box and undo_box["width"] >= 45 and undo_box["height"] >= 41, undo_box
            metrics = tools.evaluate("el=>({scrollWidth:el.scrollWidth,clientWidth:el.clientWidth,overflowX:getComputedStyle(el).overflowX})")
            assert metrics["overflowX"] in ("auto", "scroll"), metrics
            assert metrics["scrollWidth"] > metrics["clientWidth"], metrics
            expect(page.locator("#memoUndo")).to_have_attribute("aria-label", "元に戻す")
            expect(page.locator("#memoRedo")).to_have_attribute("aria-label", "やり直す")

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("PROGRESS_UI_POLISH_E2E: PASS")


if __name__ == "__main__":
    main()
