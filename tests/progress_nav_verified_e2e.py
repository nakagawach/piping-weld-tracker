import base64
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from app import app
from tests.ui_shell_e2e import PROJECT_ID, seed_database

BASE_URL = "http://127.0.0.1:8766"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z7ZQAAAAASUVORK5CYII="
)


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


def disabled_style(locator):
    return locator.evaluate(
        "el => ({pointerEvents:getComputedStyle(el).pointerEvents, opacity:Number(getComputedStyle(el).opacity), cursor:getComputedStyle(el).cursor})"
    )


def main():
    seed_database()
    server, thread = run_server()
    time.sleep(0.2)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            progress_requests = []
            page.on(
                "request",
                lambda request: progress_requests.append(request.url)
                if "/progress-data?" in request.url
                else None,
            )
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

            page.goto(
                f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector(".ui3-pages")
            page.wait_for_function(
                "document.getElementById('page').value === '1' && "
                "document.getElementById('prev').disabled && "
                "!document.getElementById('next').disabled"
            )
            page.wait_for_timeout(100)

            measured = boxes(page)
            assert_single_row(measured)

            prev = page.locator("#prev")
            next_button = page.locator("#next")
            assert prev.is_disabled()
            assert not next_button.is_disabled()
            prev_style = disabled_style(prev)
            assert prev_style["pointerEvents"] == "none", prev_style
            assert prev_style["opacity"] <= 0.5, prev_style
            before_requests = len(progress_requests)
            prev.evaluate("el => el.click()")
            page.wait_for_timeout(100)
            assert page.locator("#page").input_value() == "1"
            assert len(progress_requests) == before_requests

            inline_active = page.locator(".progress-thumb.active")
            page.wait_for_function(
                "document.querySelectorAll('.progress-thumb').length === 3"
            )
            assert inline_active.get_attribute("data-page") == "1"
            assert inline_active.is_disabled()
            assert inline_active.get_attribute("aria-disabled") == "true"
            inline_style = disabled_style(inline_active)
            assert inline_style["pointerEvents"] == "none", inline_style
            before_requests = len(progress_requests)
            inline_active.evaluate("el => el.click()")
            page.wait_for_timeout(100)
            assert page.locator("#page").input_value() == "1"
            assert len(progress_requests) == before_requests
            assert not page.locator('.progress-thumb[data-page="2"]').is_disabled()

            next_button.click()
            page.wait_for_function(
                "document.getElementById('page').value === '2' && "
                "!document.getElementById('prev').disabled && "
                "!document.getElementById('next').disabled"
            )
            next_button.click()
            page.wait_for_function(
                "document.getElementById('page').value === '3' && "
                "!document.getElementById('prev').disabled && "
                "document.getElementById('next').disabled"
            )
            page.wait_for_timeout(100)

            assert next_button.is_disabled()
            assert not prev.is_disabled()
            next_style = disabled_style(next_button)
            assert next_style["pointerEvents"] == "none", next_style
            assert next_style["opacity"] <= 0.5, next_style
            before_requests = len(progress_requests)
            next_button.evaluate("el => el.click()")
            page.wait_for_timeout(100)
            assert page.locator("#page").input_value() == "3"
            assert len(progress_requests) == before_requests

            inline_active = page.locator(".progress-thumb.active")
            assert inline_active.get_attribute("data-page") == "3"
            assert inline_active.is_disabled()
            assert inline_active.get_attribute("aria-disabled") == "true"

            page.goto(
                f"{BASE_URL}/projects/{PROJECT_ID}/thumbnails?source=progress&page=2",
                wait_until="domcontentloaded",
            )
            page.wait_for_function(
                "document.querySelectorAll('.page-card').length === 3"
            )
            grid_active = page.locator(".page-card.active")
            assert grid_active.get_attribute("data-page") == "2"
            assert not grid_active.is_disabled()
            assert grid_active.get_attribute("aria-disabled") is None
            assert not page.locator('.page-card[data-page="1"]').is_disabled()
            grid_active.click()
            page.wait_for_url(f"**/projects/{PROJECT_ID}/progress?page=2")

            # Favorites are navigation cards too: selecting an already-favorited page
            # must stay actionable and open the target progress page.
            page.goto(f"{BASE_URL}/projects-screen", wait_until="domcontentloaded")
            page.evaluate(
                "(key) => localStorage.setItem(key, JSON.stringify([2]))",
                f"weldFavoritePages:{PROJECT_ID}",
            )
            page.goto(f"{BASE_URL}/favorites", wait_until="domcontentloaded")
            page.wait_for_function("document.querySelectorAll('.card').length >= 1")
            favorite_card = page.locator(f'.card[data-project="{PROJECT_ID}"][data-page="2"]')
            assert favorite_card.count() == 1
            progress_button = favorite_card.locator("[data-progress]")
            assert not progress_button.is_disabled()
            favorite_card.locator("[data-open-progress]").click()
            page.wait_for_url(f"**/projects/{PROJECT_ID}/progress?page=2")

            print("PC_PAGER_COORDS", measured)
            print("FIRST_PAGE_PREV_DISABLED", prev_style)
            print("LAST_PAGE_NEXT_DISABLED", next_style)
            print("INLINE_CURRENT_THUMB_DISABLED", True)
            print("GRID_CURRENT_THUMB_NAVIGABLE", True)
            print("FAVORITE_PAGE_NAVIGABLE", True)
            print("BOUNDARY_DISABLED_NO_EXTRA_PROGRESS_REQUEST", True)
            print("PROGRESS_NAV_VERIFIED_E2E: PASS")
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)


if __name__ == "__main__":
    main()
