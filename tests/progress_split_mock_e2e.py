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

BASE_URL = "http://127.0.0.1:8769"
SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000"><rect width="1600" height="1000" fill="white"/><path d="M80 500 H1500 M800 80 V920" stroke="#999" stroke-width="3"/></svg>"""


def seed_mock_data():
    seed_database()
    key = f"project:{PROJECT_ID}"
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("DELETE FROM number_map WHERE drawing_key = ?", (key,))
        connection.execute("DELETE FROM weld_progress WHERE drawing_key = ?", (key,))
        connection.executemany(
            """
            INSERT INTO number_map (
                drawing_key, page_number, item_order, number_text, source,
                x, y, width, height, saved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (key, 1, 0, "1", "manual", 900, 1000, 120, 120, "2026-08-30T00:00:00+00:00"),
                (key, 1, 1, "2", "manual", 3000, 1800, 120, 120, "2026-08-30T00:00:00+00:00"),
                (key, 2, 0, "3", "manual", 2000, 1500, 120, 120, "2026-08-30T00:00:00+00:00"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO weld_progress (
                drawing_key, page_number, position_x, position_y, number_text,
                status, completed_date, work_detail, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (key, 1, 960, 1060, "1", "完了", "2026-08-30", "検査OK", "2026-08-30T00:00:00+00:00"),
                (key, 1, 3060, 1860, "2", "施工中", "", "ルートパス中", "2026-08-30T00:00:00+00:00"),
            ],
        )


def run_server():
    server = make_server("127.0.0.1", 8769, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stub_pdf(page):
    page.route(
        f"**/projects/{PROJECT_ID}/pdfium-info",
        lambda route: route.fulfill(status=200, content_type="application/json", body='{"pageCount":2}'),
    )
    page.route(
        f"**/projects/{PROJECT_ID}/pdfium-page**",
        lambda route: route.fulfill(status=200, content_type="image/svg+xml", body=SVG),
    )


def main():
    seed_mock_data()
    server, thread = run_server()
    time.sleep(0.2)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()

            page = browser.new_page(viewport={"width": 1440, "height": 900})
            stub_pdf(page)
            posts = []
            page.on("request", lambda req: posts.append(req.url) if req.method == "POST" else None)
            page.goto(f"{BASE_URL}/projects-screen", wait_until="domcontentloaded")
            mock_button = page.locator("[data-ui3-mock]")
            expect(mock_button).to_be_visible()
            expect(mock_button).to_have_text("モック確認")
            mock_button.click()
            page.wait_for_url("**/mock/progress-split")
            expect(page.locator("#side")).to_be_visible()
            expect(page.locator(".record")).to_have_count(3, timeout=5000)
            expect(page.locator("#status")).to_contain_text("P1")

            page.locator("#zoomIn").click()
            page.locator("#zoomIn").click()
            expect(page.locator("#zoomValue")).to_have_text("150%")
            record2 = page.locator(".record").filter(has=page.locator(".number", has_text="2"))
            record2.locator(".record-focus").click()
            expect(page.locator("#zoomValue")).to_have_text("150%")
            expect(page.locator(".record.selected .number")).to_have_text("2")
            assert "focused" in (page.locator('.marker[data-number="2"]').get_attribute("class") or "")
            assert not page.locator("#mockDialog").evaluate("el => el.open")

            # A second click must cancel the first highlight immediately and select the latest target.
            record1 = page.locator(".record").filter(has=page.locator(".number", has_text="1"))
            record1.locator(".record-focus").click()
            expect(page.locator(".record.selected .number")).to_have_text("1")
            assert "focused" in (page.locator('.marker[data-number="1"]').get_attribute("class") or "")
            assert "focused" not in (page.locator('.marker[data-number="2"]').get_attribute("class") or "")

            # Rotation works without changing zoom.
            page.locator("#rotate").click()
            expect(page.locator("#rotate")).to_have_text("↻ 90°")
            expect(page.locator("#zoomValue")).to_have_text("150%")
            assert "rotate(90deg)" in (page.locator("#surface").get_attribute("style") or "")

            # Right-side progress input opens instantly and applies locally only.
            record2.locator(".record-input").click()
            expect(page.locator("#mockDialog")).to_be_visible()
            expect(page.locator("#dialogTarget")).to_contain_text("2 / P1")
            page.locator("#dialogStatus").select_option("完了")
            page.locator("#dialogMemo").fill("モック更新")
            page.locator("#mockSave").click()
            expect(record2.locator(".badge")).to_have_text("完了")
            expect(record2.locator(".memo")).to_have_text("モック更新")

            # Drawing marker still opens the same input mock.
            page.locator('.marker[data-number="2"]').click()
            expect(page.locator("#mockDialog")).to_be_visible()
            expect(page.locator("#dialogTarget")).to_contain_text("2 / P1")
            page.locator("#closeDialog").click()
            assert not posts, posts
            page.close()

            tablet = browser.new_page(viewport={"width": 1024, "height": 768})
            stub_pdf(tablet)
            tablet.goto(f"{BASE_URL}/mock/progress-split?project={PROJECT_ID}", wait_until="domcontentloaded")
            expect(tablet.locator("#side")).to_be_visible()
            expect(tablet.locator(".record")).to_have_count(3, timeout=5000)
            tablet.close()

            narrow = browser.new_page(viewport={"width": 820, "height": 900})
            stub_pdf(narrow)
            narrow.goto(f"{BASE_URL}/mock/progress-split?project={PROJECT_ID}", wait_until="domcontentloaded")
            expect(narrow.locator("#openSide")).to_be_visible()
            narrow.locator("#openSide").click()
            assert "open" in (narrow.locator("#side").get_attribute("class") or "")
            expect(narrow.locator(".record")).to_have_count(3, timeout=5000)
            narrow.close()

            phone = browser.new_page(viewport={"width": 390, "height": 844})
            stub_pdf(phone)
            phone.goto(f"{BASE_URL}/mock/progress-split?project={PROJECT_ID}", wait_until="domcontentloaded")
            expect(phone.locator("#openSide")).to_be_visible()
            expect(phone.locator("#rotate")).to_be_visible()
            phone.locator("#rotate").click()
            expect(phone.locator("#rotate")).to_have_attribute("aria-label", "図面を90度回転")
            phone.locator("#openSide").click()
            expect(phone.locator("#side")).to_be_visible()
            box = phone.locator("#side").bounding_box()
            assert box is not None and box["width"] >= 380, box
            expect(phone.locator(".record-input")).to_have_count(3, timeout=5000)
            phone.close()

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("PROGRESS_SPLIT_MOCK_E2E: PASS")


if __name__ == "__main__":
    main()
