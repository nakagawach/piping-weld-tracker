import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from test_preview_wsgi import application


BASE_URL = "http://127.0.0.1:8766"
PROJECT_ID = 999


def run_server():
    server = make_server("127.0.0.1", 8766, application)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def assert_responsive_header(page, kind, mobile):
    shell = page.locator(f"[data-ui3-header='{kind}']")
    if mobile:
        expect(shell).to_be_visible()
    else:
        expect(shell).not_to_be_visible()
        expect(page.locator("main > .top")).to_be_visible()


def check_viewport(browser, viewport):
    mobile = viewport["width"] <= 640
    page = browser.new_page(viewport=viewport)
    page.goto(f"{BASE_URL}/weld/projects-screen", wait_until="networkidle")
    expect(page.locator(".header.ui3-root")).to_be_visible()
    expect(page.get_by_text("UIテスト工事")).to_be_visible()

    page.goto(f"{BASE_URL}/weld/projects/{PROJECT_ID}/entry?page=1", wait_until="networkidle")
    assert_responsive_header(page, "entry", mobile)
    expect(page.locator("#thumbnailGridButton")).to_be_visible()
    expect(page.locator("canvas")).to_be_visible()

    page.goto(f"{BASE_URL}/weld/projects/{PROJECT_ID}/progress?page=1", wait_until="networkidle")
    assert_responsive_header(page, "progress", mobile)
    expect(page.locator("#thumbnailGridButton")).to_be_visible()
    expect(page.locator("canvas")).to_be_visible()

    page.goto(
        f"{BASE_URL}/weld/projects/{PROJECT_ID}/thumbnails?source=progress&page=1",
        wait_until="networkidle",
    )
    assert_responsive_header(page, "thumbnails", mobile)
    expect(page.locator(".page-card")).to_have_count(3)
    page.close()


def main():
    server, thread = run_server()
    time.sleep(0.2)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            check_viewport(browser, {"width": 1440, "height": 900})
            check_viewport(browser, {"width": 390, "height": 844})
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("Render preview desktop/mobile browser regression: PASS")


if __name__ == "__main__":
    main()
