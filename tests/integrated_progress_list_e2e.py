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

BASE_URL = "http://127.0.0.1:8771"
SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000"><rect width="1600" height="1000" fill="white"/><path d="M50 500 H1550 M800 50 V950" stroke="#aaa" stroke-width="3"/></svg>"""


def seed_progress():
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
    server = make_server("127.0.0.1", 8771, app)
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


def record(page, number):
    return page.locator(".progress-list-record").filter(
        has=page.locator(".progress-list-number", has_text=str(number))
    )


def main():
    seed_progress()
    server, thread = run_server()
    time.sleep(0.2)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()

            desktop = browser.new_page(viewport={"width": 1440, "height": 900})
            stub_pdf(desktop)
            desktop.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
            # A target selected while the initial drawing is still loading must be queued, not dropped.
            desktop.evaluate("""
              window.dispatchEvent(new CustomEvent('weld:progress-panel-target', {
                detail: {pageNumber: 1, number: '1', x: 960, y: 1060, openEditor: false}
              }))
            """)
            expect(desktop.locator("#canvas")).to_have_attribute("data-selected-target", "1:960:1060", timeout=7000)
            expect(desktop.locator("#progressListToggle")).to_be_visible()
            expect(desktop.locator('a[href*="progress-list"]')).to_have_count(0)
            expect(desktop.locator("#progressListPanel")).not_to_be_visible()
            desktop.locator("#progressListToggle").click()
            expect(desktop.locator("#progressListPanel")).to_be_visible()
            expect(desktop.locator(".progress-list-record")).to_have_count(3, timeout=7000)
            panel_box = desktop.locator("#progressListPanel").bounding_box()
            assert panel_box and panel_box["x"] > 1000 and 340 <= panel_box["width"] <= 370, panel_box

            row2 = record(desktop, 2)
            row2.locator(".progress-list-focus").click()
            assert "selected" in (row2.get_attribute("class") or "")
            expect(desktop.locator("#canvas")).to_have_attribute("data-selected-target", "1:3060:1860")

            # Panel input uses the existing real progress editor and save route.
            row2.locator(".progress-list-input").click()
            expect(desktop.locator("#progressDialog")).to_be_visible()
            desktop.locator('[data-value="完了"]').click()
            desktop.locator("#workDetail").fill("統合一覧から更新")
            desktop.locator("#save").click()
            expect(desktop.locator("#progressDialog")).not_to_be_visible()
            expect(record(desktop, 2).locator(".progress-list-badge")).to_have_text("完了")
            expect(record(desktop, 2).locator(".progress-list-memo")).to_have_text("統合一覧から更新")

            # List -> page -> drawing selection.
            row3 = record(desktop, 3)
            row3.locator(".progress-list-focus").click()
            expect(desktop.locator("#page")).to_have_value("2", timeout=7000)
            expect(desktop.locator("#canvas")).to_have_attribute("data-selected-target", "2:2060:1560")
            assert "selected" in (record(desktop, 3).get_attribute("class") or "")
            assert "current-page" in (record(desktop, 3).get_attribute("class") or "")

            # Ordinary page navigation clears the previous target and re-syncs current-page rows.
            desktop.locator("#prev").click()
            expect(desktop.locator("#page")).to_have_value("1", timeout=7000)
            expect(desktop.locator("#canvas")).not_to_have_attribute("data-selected-target", "2:2060:1560")
            expect(record(desktop, 1)).to_have_attribute("class", re.compile(r".*\bcurrent-page\b.*"), timeout=3000)
            expect(record(desktop, 3)).not_to_have_attribute("class", re.compile(r".*\\bcurrent-page\\b.*"), timeout=3000)

            # Drawing -> list selection, plus persistent blue target state.
            canvas = desktop.locator("#canvas")
            box = canvas.bounding_box()
            assert box
            x = box["x"] + (960 * (1600 / 6000) / 1600) * box["width"]
            y = box["y"] + (1060 * (1600 / 6000) / 1000) * box["height"]
            desktop.mouse.click(x, y)
            expect(desktop.locator("#progressDialog")).to_be_visible()
            assert "selected" in (record(desktop, 1).get_attribute("class") or "")
            expect(canvas).to_have_attribute("data-selected-target", "1:960:1060")
            desktop.locator("#closeDialog").click()

            # Selection survives rotation/redraw.
            desktop.locator("#rotate").click()
            expect(canvas).to_have_attribute("data-selected-target", "1:960:1060")

            # Toggle hides and restores the same panel.
            desktop.locator("#progressListToggle").click()
            expect(desktop.locator("#progressListPanel")).not_to_be_visible()
            desktop.locator("#progressListToggle").click()
            expect(desktop.locator("#progressListPanel")).to_be_visible()
            desktop.close()

            landscape = browser.new_page(viewport={"width": 1024, "height": 768})
            stub_pdf(landscape)
            landscape.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
            landscape.locator("#progressListToggle").click()
            expect(landscape.locator("#progressListPanel")).to_be_visible()
            lb = landscape.locator("#progressListPanel").bounding_box()
            assert lb and lb["x"] > 600 and lb["width"] >= 340, lb
            landscape.close()

            portrait = browser.new_page(viewport={"width": 768, "height": 1024})
            stub_pdf(portrait)
            portrait.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
            portrait.locator("#progressListToggle").click()
            expect(portrait.locator("#progressListPanel")).to_be_visible()
            pb = portrait.locator("#progressListPanel").bounding_box()
            assert pb and pb["x"] <= 1 and 500 <= pb["height"] <= 525, pb
            portrait.locator("#progressListClose").click()
            expect(portrait.locator("#progressListPanel")).not_to_be_visible()
            portrait.close()

            phone = browser.new_page(viewport={"width": 390, "height": 844})
            stub_pdf(phone)
            phone.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
            phone.locator("#progressListToggle").click()
            expect(phone.locator("#progressListPanel")).to_be_visible()
            fb = phone.locator("#progressListPanel").bounding_box()
            assert fb and fb["x"] <= 1 and 410 <= fb["height"] <= 430, fb
            expect(phone.locator(".progress-list-record")).to_have_count(3, timeout=7000)
            phone.close()

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("INTEGRATED_PROGRESS_LIST_E2E: PASS")


if __name__ == "__main__":
    main()
