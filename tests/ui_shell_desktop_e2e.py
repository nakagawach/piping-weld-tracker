import time

from playwright.sync_api import expect, sync_playwright

from tests.ui_shell_e2e import BASE_URL, PROJECT_ID, run_server, seed_database


def main():
    seed_database()
    server, thread = run_server()
    time.sleep(0.2)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})

            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
            expect(page.locator("[data-ui3-header='progress']")).to_be_visible()
            expect(page.locator("[data-weld-desktop-shell-v1]")).to_have_count(1)
            expect(page.locator("main > .top")).not_to_be_visible()
            expect(page.locator(".desktop-tools")).to_be_visible()
            expect(page.locator(".ui3-pages")).to_be_visible()
            expect(page.locator(".ui3-drawing")).to_be_visible()
            expect(page.locator("#prev")).to_be_disabled()
            assert page.locator("#prev").evaluate("el => getComputedStyle(el).cursor") == "not-allowed"

            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/entry?page=1", wait_until="domcontentloaded")
            expect(page.locator("[data-ui3-header='entry']")).to_be_visible()
            expect(page.locator("main > .top")).not_to_be_visible()
            expect(page.locator("#ocr")).to_be_visible()
            expect(page.locator("#save")).to_be_visible()

            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/thumbnails?source=progress&page=1", wait_until="domcontentloaded")
            expect(page.locator("[data-ui3-header='thumbnails']")).to_be_visible()
            expect(page.locator("main > .top")).not_to_be_visible()

            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress-list?page=1", wait_until="domcontentloaded")
            expect(page.locator("[data-ui3-header='progress-list']")).to_be_visible()
            expect(page.locator("main > .topbar")).not_to_be_visible()

            page.goto(f"{BASE_URL}/favorites", wait_until="domcontentloaded")
            expect(page.locator("[data-ui3-header='favorites']")).to_be_visible()
            expect(page.locator("main > .top")).not_to_be_visible()

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("Desktop UI shell browser regression: PASS")


if __name__ == "__main__":
    main()
