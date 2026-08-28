# Unified header navigation regression for the V1.1 rebuild.
import sqlite3
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import DATA_DIR, DB_PATH, app


PROJECT_ID = 999
BASE_URL = "http://127.0.0.1:8765"


def seed_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    pdf_dir = DATA_DIR / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / "ui-test.pdf"
    pages = [Image.new("RGB", (320, 240), "white") for _ in range(3)]
    pages[0].save(pdf_path, "PDF", save_all=True, append_images=pages[1:])
    for image in pages:
        image.close()

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
    # Viewer pages request PDF info/thumbnails in parallel. Use a threaded test server so
    # the regression reflects PythonAnywhere/browser behavior instead of deadlocking on
    # a single-request local server.
    server = make_server("127.0.0.1", 8765, app, threaded=True)
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

            page.goto(f"{BASE_URL}/projects-screen", wait_until="domcontentloaded")
            expect(page.locator(".header.ui3-root")).to_be_visible()
            expect(page.locator("#new-project")).to_be_visible()
            expect(page.locator("[data-global-favorites-launch]")).to_have_count(1)
            expect(page.locator("[data-ui3-favorites]")).to_be_visible()
            expect(page.get_by_text("サンプル工事（既存テストデータ）")).to_have_count(0)
            expect(page.locator("#open-current")).to_have_count(0)

            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
            expect(page.locator("[data-ui3-header='progress']")).to_be_visible()
            assert_back(page, "/projects-screen", "工事一覧へ")
            expect(page.locator("main > .top")).not_to_be_visible()
            expect(page.locator("#backCompact")).to_have_count(0)
            expect(page.locator("#thumbnailGridButton")).to_be_visible(timeout=5000)
            expect(page.locator("[aria-label='進捗一覧']")).to_be_visible()
            expect(page.locator(".page-favorite-view")).to_be_visible(timeout=5000)
            expect(page.locator(".ui3-page-group")).to_be_visible()
            expect(page.locator(".ui3-view-group")).to_be_visible()
            expect(page.locator(".ui3-page-tools")).to_be_visible()
            expect(page.locator("[data-ui3-screen-actions='progress']")).to_be_visible()
            expect(page.locator("#drawingMemoLaunch")).to_be_visible()
            expect(page.locator("#drawingMemoEdit")).to_be_visible()
            expect(page.get_by_text("図面エントリーへ", exact=True)).to_be_visible()
            assert page.locator("[data-weld-ui-shell-v3]").count() >= 2

            page.locator("#thumbnailGridButton").click()
            page.wait_for_url(f"**/projects/{PROJECT_ID}/thumbnails?source=progress&page=1")
            expect(page.locator("[data-ui3-header='thumbnails']")).to_be_visible()
            assert_back(page, f"/projects/{PROJECT_ID}/progress?page=1", "進捗へ")
            page.locator(".ui3-appbar .ui3-back").click()
            page.wait_for_url(f"**/projects/{PROJECT_ID}/progress?page=1")

            page.locator("[aria-label='進捗一覧']").click()
            page.wait_for_url(f"**/projects/{PROJECT_ID}/progress-list")
            expect(page.locator("[data-ui3-header='progress-list']")).to_be_visible()
            assert_back(page, f"/projects/{PROJECT_ID}/progress?page=1", "進捗へ")

            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/entry?page=1", wait_until="domcontentloaded")
            expect(page.locator("[data-ui3-header='entry']")).to_be_visible()
            assert_back(page, "/projects-screen", "工事一覧へ")
            expect(page.locator("main > .top")).not_to_be_visible()
            expect(page.locator("#thumbnailGridButton")).to_be_visible(timeout=5000)
            expect(page.locator(".page-favorite-view")).to_be_visible(timeout=5000)
            expect(page.locator(".ui3-page-group")).to_be_visible()
            expect(page.locator(".ui3-view-group")).to_be_visible()
            expect(page.locator(".ui3-page-tools")).to_be_visible()
            expect(page.locator("[data-ui3-screen-actions='entry']")).to_be_visible()
            overflow = page.locator(".ui3-more > summary")
            overflow.click()
            expect(page.locator(".ui3-more #reset")).to_be_visible()
            expect(page.locator(".ui3-more #bulkDelete")).to_be_visible()
            overflow.click()
            expect(page.locator(".ui3-more #reset")).not_to_be_visible()

            page.locator("#thumbnailGridButton").click()
            page.wait_for_url(f"**/projects/{PROJECT_ID}/thumbnails?source=entry&page=1")
            assert_back(page, f"/projects/{PROJECT_ID}/entry?page=1", "エントリーへ")

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
