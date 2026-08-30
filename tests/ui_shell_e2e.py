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

            # 工事一覧: root actions are visible, legacy test card is gone.
            page.goto(f"{BASE_URL}/projects-screen", wait_until="domcontentloaded")
            expect(page.locator(".header.ui3-root")).to_be_visible()
            expect(page.locator("#new-project")).to_be_visible()
            expect(page.locator("[data-global-favorites-launch]")).to_have_count(1)
            expect(page.locator("[data-ui3-favorites]" )).to_be_visible()
            expect(page.get_by_text("サンプル工事（既存テストデータ）")).to_have_count(0)
            expect(page.locator("#open-current")).to_have_count(0)

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
            pages_box = page.locator(".ui3-pages").bounding_box()
            drawing_box = page.locator(".ui3-drawing").bounding_box()
            toolbar_box = page.locator(".toolbar").bounding_box()
            assert pages_box and drawing_box and toolbar_box
            assert pages_box["x"] < drawing_box["x"], (pages_box, drawing_box)
            assert drawing_box["x"] + drawing_box["width"] >= toolbar_box["x"] + toolbar_box["width"] - 12, (drawing_box, toolbar_box)

            # 実際にページ一覧ボタンをクリックして遷移する。
            page.locator("#thumbnailGridButton").click()
            page.wait_for_url(f"**/projects/{PROJECT_ID}/thumbnails?source=progress&page=1")
            expect(page.locator("[data-ui3-header='thumbnails']")).to_be_visible()
            assert_back(page, f"/projects/{PROJECT_ID}/progress?page=1", "進捗へ")
            page.locator(".ui3-appbar .ui3-back").click()
            page.wait_for_url(f"**/projects/{PROJECT_ID}/progress?page=1")

            # 進捗一覧ボタンを実クリック。同画面パネル表示/非表示へ置き換え。
            progress_list_toggle = page.locator("[aria-label='進捗一覧']")
            progress_list_toggle.click()
            expect(page.locator("#progressListPanel")).to_be_visible()
            progress_list_toggle.click()
            expect(page.locator("#progressListPanel")).not_to_be_visible()

            # エントリー: fixed parent navigation + overflow actions are actually visible in the menu.
            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/entry?page=1", wait_until="domcontentloaded")
            expect(page.locator("[data-ui3-header='entry']")).to_be_visible()
            assert_back(page, "/projects-screen", "工事一覧へ")
            expect(page.locator("main > .top")).not_to_be_visible()
            expect(page.locator("#thumbnailGridButton")).to_be_visible(timeout=5000)
            expect(page.locator(".page-favorite-view")).to_be_visible(timeout=5000)
            overflow = page.locator(".ui3-entry-more > summary")
            overflow.click()
            expect(page.locator(".ui3-entry-more #reset")).to_be_visible()
            expect(page.locator(".ui3-entry-more #bulkDelete")).to_be_visible()
            expect(page.locator(".ui3-entry-more [data-go-favorites]")).to_be_visible(timeout=5000)
            overflow.click()
            expect(page.locator(".ui3-entry-more #reset")).not_to_be_visible()

            # Entry由来ページ一覧はEntryの同ページへ固定で戻る。
            page.locator("#thumbnailGridButton").click()
            page.wait_for_url(f"**/projects/{PROJECT_ID}/thumbnails?source=entry&page=1")
            assert_back(page, f"/projects/{PROJECT_ID}/entry?page=1", "エントリーへ")

            # お気に入り一覧: page gridと同じ1〜4列切替を持つ。
            page.goto(f"{BASE_URL}/favorites", wait_until="domcontentloaded")
            expect(page.locator("[data-ui3-header='favorites']")).to_be_visible()
            assert_back(page, "/projects-screen", "工事一覧へ")
            expect(page.locator(".columns [data-cols]")).to_have_count(4)
            page.locator(".columns [data-cols='4']").click()
            expect(page.locator(".columns [data-cols='4']")).to_have_class("active")
            assert page.locator("#grid").evaluate("el => el.style.getPropertyValue('--cols')") == "4"

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("UI shell browser regression: PASS")


if __name__ == "__main__":
    main()
