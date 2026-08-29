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

PROJECT_ID = 998
BASE_URL = "http://127.0.0.1:8766"


def seed_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY AUTOINCREMENT, project_name TEXT NOT NULL, original_pdf_name TEXT NOT NULL, stored_pdf_name TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL)""")
        connection.execute("DELETE FROM projects WHERE id = ?", (PROJECT_ID,))
        connection.execute("INSERT INTO projects (id, project_name, original_pdf_name, stored_pdf_name, created_at) VALUES (?, ?, ?, ?, ?)", (PROJECT_ID, "PCナビ検証", "verify.pdf", "verify.pdf", "2026-08-29T00:00:00+00:00"))


def run_server():
    server = make_server("127.0.0.1", 8766, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def center_y(box):
    return box["y"] + box["height"] / 2


def boxes(page):
    return {
        "prev": page.locator("#prev").bounding_box(),
        "field": page.locator(".page-field").bounding_box(),
        "next": page.locator("#next").bounding_box(),
    }


def assert_single_row(measured):
    assert all(measured.values()), measured
    ys = [center_y(measured[k]) for k in ("prev", "field", "next")]
    assert max(ys) - min(ys) <= 2, (measured, ys)
    assert measured["prev"]["x"] + measured["prev"]["width"] <= measured["field"]["x"] + 2, measured
    assert measured["field"]["x"] + measured["field"]["width"] <= measured["next"]["x"] + 2, measured


def main():
    seed_database()
    server, thread = run_server()
    time.sleep(0.2)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
            page.wait_for_selector(".ui3-pages")
            page.wait_for_timeout(600)

            after = boxes(page)
            assert_single_row(after)

            page.locator("#prev").evaluate("el => el.disabled = true")
            cursor = page.locator("#prev").evaluate("el => getComputedStyle(el).cursor")
            assert cursor == "not-allowed", cursor

            # Same-page thumbnail must be a real disabled button, not a clickable reload/navigation target.
            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/thumbnails?source=progress&page=3", wait_until="domcontentloaded")
            page.locator("#grid").evaluate("grid => { grid.innerHTML='<button type=\"button\" class=\"page-card active\" data-page=\"3\">P3</button>'; }")
            page.wait_for_timeout(50)
            active = page.locator(".page-card.active")
            assert active.is_disabled()
            assert active.get_attribute("aria-disabled") == "true"
            assert active.evaluate("el => getComputedStyle(el).cursor") == "not-allowed"
            before_url = page.url
            active.click(force=True)
            page.wait_for_timeout(50)
            assert page.url == before_url, (before_url, page.url)

            print("PC_PAGER_COORDS", after)
            print("DISABLED_CURSOR", cursor)
            print("CURRENT_THUMB_DISABLED", active.is_disabled(), active.get_attribute("aria-disabled"))
            print("PROGRESS_NAV_VERIFIED_E2E: PASS")
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)


if __name__ == "__main__":
    main()
