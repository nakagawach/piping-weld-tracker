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

            page.locator("#drawingMemoEdit").click()
            tools = page.locator("#drawingMemoTools")
            expect(tools).to_be_visible()
            page.wait_for_timeout(160)
            tools_box = tools.bounding_box()
            viewer_box = page.locator("#viewer").bounding_box()
            color_box = page.locator(".memo-color").first.bounding_box()
            thin_box = page.locator('[data-memo-width="12"]').bounding_box()
            eraser_box = page.locator("#memoEraser").bounding_box()
            undo_box = page.locator("#memoUndo").bounding_box()
            assert tools_box and 47 <= tools_box["height"] <= 49, tools_box
            assert viewer_box and tools_box["y"] + tools_box["height"] <= viewer_box["y"] + 2, (tools_box, viewer_box)
            assert color_box and color_box["width"] >= 35 and color_box["height"] >= 35, color_box
            assert thin_box and thin_box["width"] >= 47 and thin_box["height"] >= 41, thin_box
            assert eraser_box and eraser_box["width"] >= 80 and eraser_box["height"] >= 41, eraser_box
            assert undo_box and undo_box["width"] >= 45 and undo_box["height"] >= 41, undo_box
            for child_box in (color_box, thin_box, eraser_box, undo_box):
                assert child_box["y"] >= tools_box["y"] - 0.5, (tools_box, child_box)
                assert child_box["y"] + child_box["height"] <= tools_box["y"] + tools_box["height"] + 0.5, (tools_box, child_box)
            metrics = tools.evaluate("el=>({scrollWidth:el.scrollWidth,clientWidth:el.clientWidth,overflowX:getComputedStyle(el).overflowX,overflowY:getComputedStyle(el).overflowY})")
            assert metrics["overflowX"] in ("auto", "scroll"), metrics
            assert metrics["overflowY"] == "hidden", metrics
            assert metrics["scrollWidth"] > metrics["clientWidth"], metrics
            expect(page.locator("#memoUndo")).to_have_attribute("aria-label", "元に戻す")
            expect(page.locator("#memoRedo")).to_have_attribute("aria-label", "やり直す")

            # Fullscreen keeps the memo row separate from the drawing instead of layering it over the viewer.
            page.locator("#fullscreenCompact").click()
            page.wait_for_timeout(180)
            tools_full = tools.bounding_box()
            viewer_full = page.locator("#viewer").bounding_box()
            assert tools_full and viewer_full
            assert 47 <= tools_full["height"] <= 49, tools_full
            assert tools_full["y"] + tools_full["height"] <= viewer_full["y"] + 2, (tools_full, viewer_full)

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("PROGRESS_UI_POLISH_E2E: PASS")


if __name__ == "__main__":
    main()
