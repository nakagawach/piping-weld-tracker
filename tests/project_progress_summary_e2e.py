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


BASE_URL = "http://127.0.0.1:8768"


def seed_progress():
    seed_database()
    key = f"project:{PROJECT_ID}"
    with sqlite3.connect(DB_PATH) as connection:
        entries = [
            (key, 1, 0, "1", "manual", 10, 20, 10, 10, "2026-08-30T00:00:00+00:00"),
            (key, 1, 1, "2", "manual", 30, 20, 10, 10, "2026-08-30T00:00:00+00:00"),
            (key, 2, 0, "3", "manual", 10, 40, 10, 10, "2026-08-30T00:00:00+00:00"),
            (key, 2, 1, "4", "manual", 30, 40, 10, 10, "2026-08-30T00:00:00+00:00"),
        ]
        connection.executemany(
            """
            INSERT INTO number_map (
                drawing_key, page_number, item_order, number_text, source,
                x, y, width, height, saved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            entries,
        )
        progress = [
            (key, 1, 15, 25, "1", "完了", "2026-08-30", "", "2026-08-30T00:00:00+00:00"),
            (key, 1, 35, 25, "2", "完了", "2026-08-30", "", "2026-08-30T00:00:00+00:00"),
            (key, 2, 15, 45, "3", "施工中", "", "", "2026-08-30T00:00:00+00:00"),
        ]
        connection.executemany(
            """
            INSERT INTO weld_progress (
                drawing_key, page_number, position_x, position_y, number_text,
                status, completed_date, work_detail, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            progress,
        )


def run_server():
    server = make_server("127.0.0.1", 8768, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def verify_projects_screen(browser, viewport):
    page = browser.new_page(viewport=viewport)
    page_errors = []
    console_errors = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on(
        "console",
        lambda message: console_errors.append(message.text)
        if message.type == "error"
        else None,
    )

    page.goto(f"{BASE_URL}/projects-screen", wait_until="domcontentloaded")
    expect(page.get_by_text("UIテスト工事")).to_be_visible(timeout=5000)
    expect(page.get_by_text("工事一覧を読み込んでいます…")).to_have_count(0)

    summary = page.locator(f'[data-progress-summary="{PROJECT_ID}"]')
    expect(summary).to_be_visible()
    expect(summary.get_by_text("50.0%")).to_be_visible(timeout=5000)
    expect(summary.get_by_text("完了 2 / 4件")).to_be_visible()
    expect(summary.get_by_text("未着手 1件")).to_be_visible()
    expect(summary.get_by_text("施工中 1件")).to_be_visible()
    expect(summary.get_by_text("完了 2件", exact=True)).to_be_visible()
    expect(summary.get_by_text("進捗を読み込んでいます…")).to_have_count(0)

    expect(page.locator(f'[data-progress="projects/{PROJECT_ID}/progress"]')).to_be_visible()
    expect(page.locator(f'[data-entry="projects/{PROJECT_ID}/entry"]')).to_be_visible()

    page.wait_for_timeout(100)
    assert not page_errors, page_errors
    assert not console_errors, console_errors
    page.close()


def main():
    seed_progress()
    server, thread = run_server()
    time.sleep(0.2)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            verify_projects_screen(browser, {"width": 1440, "height": 900})
            verify_projects_screen(browser, {"width": 390, "height": 844})
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("PROJECT_PROGRESS_SUMMARY_E2E: PASS")


if __name__ == "__main__":
    main()
