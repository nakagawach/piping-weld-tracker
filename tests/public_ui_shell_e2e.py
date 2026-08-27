import os
from urllib.parse import urljoin

from playwright.sync_api import expect, sync_playwright


BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://nakagawach.pythonanywhere.com/weld").rstrip("/")
PROJECT_ID = int(os.environ.get("PUBLIC_PROJECT_ID", "7"))


def expect_back(page, expected_url, label):
    back = page.locator(".ui3-appbar .ui3-back")
    expect(back).to_have_count(1)
    expect(back).to_be_visible()
    expect(back).to_have_attribute("aria-label", label)
    href = back.get_attribute("href")
    assert href, "back link has no href"
    actual = urljoin(page.url, href)
    assert actual == expected_url, (actual, expected_url, href)
    box = back.bounding_box()
    assert box and box["height"] >= 44, box


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})

        page.goto(f"{BASE_URL}/projects-screen", wait_until="domcontentloaded", timeout=30000)
        expect(page.locator(".header.ui3-root")).to_be_visible()
        expect(page.locator("#new-project")).to_be_visible()

        page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded", timeout=30000)
        expect(page.locator("[data-ui3-header='progress']")).to_be_visible()
        expect_back(page, f"{BASE_URL}/projects-screen", "工事一覧へ")
        expect(page.locator("main > .top")).not_to_be_visible()
        expect(page.locator("#backCompact")).to_have_count(0)
        expect(page.locator("#thumbnailGridButton")).to_be_visible(timeout=7000)
        expect(page.locator("[aria-label='進捗一覧']")).to_be_visible(timeout=7000)
        expect(page.locator(".page-favorite-view")).to_be_visible(timeout=7000)

        page.locator("#thumbnailGridButton").click()
        page.wait_for_url(f"**/weld/projects/{PROJECT_ID}/thumbnails?source=progress&page=1", timeout=30000)
        expect(page.locator("[data-ui3-header='thumbnails']")).to_be_visible()
        expect_back(page, f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", "進捗へ")
        page.locator(".ui3-appbar .ui3-back").click()
        page.wait_for_url(f"**/weld/projects/{PROJECT_ID}/progress?page=1", timeout=30000)

        page.locator("[aria-label='進捗一覧']").click()
        page.wait_for_url(f"**/weld/projects/{PROJECT_ID}/progress-list", timeout=30000)
        expect(page.locator("[data-ui3-header='progress-list']")).to_be_visible()
        expect_back(page, f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", "進捗へ")

        page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/entry?page=1", wait_until="domcontentloaded", timeout=30000)
        expect(page.locator("[data-ui3-header='entry']")).to_be_visible()
        expect_back(page, f"{BASE_URL}/projects-screen", "工事一覧へ")
        expect(page.locator("#thumbnailGridButton")).to_be_visible(timeout=7000)
        expect(page.locator(".page-favorite-view")).to_be_visible(timeout=7000)
        overflow = page.locator(".ui3-entry-more > summary")
        overflow.click()
        expect(page.locator(".ui3-entry-more #reset")).to_be_visible()
        expect(page.locator(".ui3-entry-more #bulkDelete")).to_be_visible()
        expect(page.locator(".ui3-entry-more [data-go-favorites]")).to_be_visible(timeout=7000)
        overflow.click()

        page.locator("#thumbnailGridButton").click()
        page.wait_for_url(f"**/weld/projects/{PROJECT_ID}/thumbnails?source=entry&page=1", timeout=30000)
        expect_back(page, f"{BASE_URL}/projects/{PROJECT_ID}/entry?page=1", "エントリーへ")

        page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1&viewer=1", wait_until="domcontentloaded", timeout=30000)
        expect(page.locator("html.weld-viewer-v3")).to_have_count(1)
        expect(page.locator(".ui3-appbar")).to_have_count(0)
        expect(page.locator(".weld-viewer-controls")).to_be_visible()
        expect(page.locator(".weld-viewer-controls [aria-label='90度回転']")).to_be_visible()
        close_viewer = page.locator(".weld-viewer-controls [aria-label='図面集中表示を終了']")
        expect(close_viewer).to_be_visible()
        close_viewer.click()
        page.wait_for_url(f"**/weld/projects/{PROJECT_ID}/progress?page=1", timeout=30000)

        page.goto(f"{BASE_URL}/favorites", wait_until="domcontentloaded", timeout=30000)
        expect(page.locator("[data-ui3-header='favorites']")).to_be_visible()
        expect_back(page, f"{BASE_URL}/projects-screen", "工事一覧へ")

        browser.close()
    print("Public UI shell browser regression: PASS")


if __name__ == "__main__":
    main()
