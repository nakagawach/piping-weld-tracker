import sqlite3
import threading
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import DB_PATH, app


PROJECT_ID = 999
BASE_URL = "http://127.0.0.1:8765"


def seed_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                original_pdf_name TEXT NOT NULL,
                stored_pdf_name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS number_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drawing_key TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                item_order INTEGER NOT NULL,
                number_text TEXT NOT NULL,
                source TEXT NOT NULL,
                x REAL NOT NULL,
                y REAL NOT NULL,
                width REAL NOT NULL,
                height REAL NOT NULL,
                saved_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS weld_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drawing_key TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                position_x INTEGER NOT NULL,
                position_y INTEGER NOT NULL,
                number_text TEXT NOT NULL,
                status TEXT NOT NULL,
                completed_date TEXT NOT NULL DEFAULT '',
                work_detail TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                UNIQUE(drawing_key, page_number, position_x, position_y)
            )
            """
        )
        connection.execute("DELETE FROM projects WHERE id = ?", (PROJECT_ID,))
        connection.execute(
            "INSERT INTO projects (id, project_name, original_pdf_name, stored_pdf_name, created_at) VALUES (?, ?, ?, ?, ?)",
            (PROJECT_ID, "UIテスト工事", "ui-test.pdf", "ui-test.pdf", "2026-08-28T00:00:00+00:00"),
        )
        connection.execute("DELETE FROM number_map WHERE drawing_key = ?", (f"project:{PROJECT_ID}",))
        connection.execute("DELETE FROM weld_progress WHERE drawing_key = ?", (f"project:{PROJECT_ID}",))


def run_server():
    server = make_server("127.0.0.1", 8765, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def assert_back(page, expected_suffix, label):
    back = page.locator(".ui3-appbar .ui3-back")
    expect(back).to_be_visible()
    expect(back).to_have_attribute("aria-label", label)
    href = back.get_attribute("href")
    assert href == expected_suffix, (href, expected_suffix)


def main():
    seed_database()
    server, thread = run_server()
    time.sleep(0.2)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 390, "height": 844})

            # 工事一覧: common root styling must survive the favorites launcher DOM mutation.
            page.goto(f"{BASE_URL}/projects-screen", wait_until="domcontentloaded")
            expect(page.locator(".header.ui3-root")).to_be_visible()
            expect(page.locator("#new-project")).to_be_visible()
            expect(page.locator("[data-global-favorites-launch]")).to_have_count(1)

            # 進捗: fixed app navigation, no browser-history behavior, no duplicate visible back action.
            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
            expect(page.locator("[data-ui3-header='progress']")).to_be_visible()
            assert_back(page, "/projects-screen", "工事一覧へ")
            expect(page.locator("main > .top")).not_to_be_visible()
            expect(page.locator("#backCompact")).to_have_count(0)
            expect(page.locator("#thumbnailGridButton")).to_be_visible(timeout=5000)
            expect(page.locator("[aria-label='進捗一覧']")).to_be_visible()
            expect(page.locator(".page-favorite-view")).to_be_visible(timeout=5000)
            assert page.locator("[data-weld-ui-shell-v3]").count() >= 2

            # 実際にページ一覧ボタンをクリックして遷移する。
            page.locator("#thumbnailGridButton").click()
            page.wait_for_url(f"**/projects/{PROJECT_ID}/thumbnails?source=progress&page=1")
            expect(page.locator("[data-ui3-header='thumbnails']")).to_be_visible()
            assert_back(page, f"/projects/{PROJECT_ID}/progress?page=1", "進捗へ")
            page.locator(".ui3-appbar .ui3-back").click()
            page.wait_for_url(f"**/projects/{PROJECT_ID}/progress?page=1")

            # 進捗一覧ボタンを実クリック。
            page.locator("[aria-label='進捗一覧']").click()
            page.wait_for_url(f"**/projects/{PROJECT_ID}/progress-list")
            expect(page.locator("[data-ui3-header='progress-list']")).to_be_visible()
            assert_back(page, f"/projects/{PROJECT_ID}/progress?page=1", "進捗へ")

            # エントリー: fixed parent navigation + overflow actions are actually visible in the menu.
            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/entry?page=1", wait_until="domcontentloaded")
            expect(page.locator("[data-ui3-header='entry']")).to_be_visible()
            assert_back(page, "/projects-screen", "工事一覧へ")
            expect(page.locator("main > .top")).not_to_be_visible()
            expect(page.locator("#thumbnailGridButton")).to_be_visible(timeout=5000)
            expect(page.locator(".page-favorite-view")).to_be_visible(timeout=5000)
            page.locator(".ui3-entry-more > summary").click()
            expect(page.locator(".ui3-entry-more #reset")).to_be_visible()
            expect(page.locator(".ui3-entry-more #bulkDelete")).to_be_visible()
            expect(page.locator(".ui3-entry-more [data-go-favorites]")).to_be_visible(timeout=5000)

            # Entry由来ページ一覧はEntryの同ページへ固定で戻る。
            page.locator("#thumbnailGridButton").click()
            page.wait_for_url(f"**/projects/{PROJECT_ID}/thumbnails?source=entry&page=1")
            assert_back(page, f"/projects/{PROJECT_ID}/entry?page=1", "エントリーへ")

            # お気に入り一覧は常に工事一覧へ。
            page.goto(f"{BASE_URL}/favorites", wait_until="domcontentloaded")
            expect(page.locator("[data-ui3-header='favorites']")).to_be_visible()
            assert_back(page, "/projects-screen", "工事一覧へ")

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("UI shell browser regression: PASS")


if __name__ == "__main__":
    main()
