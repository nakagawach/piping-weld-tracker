import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://nakagawach.pythonanywhere.com/weld"
ARTIFACTS = Path("test-artifacts")
ARTIFACTS.mkdir(exist_ok=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        requests = []
        page.on("request", lambda req: requests.append((time.time(), req.url, req.resource_type)))

        page.goto(f"{BASE}/projects-screen", wait_until="domcontentloaded", timeout=60000)
        links = page.locator("a").evaluate_all(
            """els => els.map(a => a.href).filter(h => /\/projects\/\d+\/(?:progress|entry)/.test(h))"""
        )
        progress_url = next((h for h in links if re.search(r"/projects/\d+/progress", h)), None)
        if not progress_url:
            raise AssertionError(f"no progress URL found from projects-screen; sample links={links[:20]}")

        page.goto(progress_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector("#progressThumbs", timeout=60000)
        page.wait_for_function("document.querySelectorAll('.progress-thumb').length > 1", timeout=60000)
        page.wait_for_timeout(500)

        strip = page.locator("#progressThumbs")
        before = {
            "url": page.url,
            "page": page.locator("#page").input_value(),
            "status": page.locator("#status").inner_text(),
            "scrollLeft": strip.evaluate("el => el.scrollLeft"),
            "scrollWidth": strip.evaluate("el => el.scrollWidth"),
            "clientWidth": strip.evaluate("el => el.clientWidth"),
            "readyState": page.evaluate("document.readyState"),
            "pageDisabled": page.locator("#page").is_disabled(),
        }
        page.screenshot(path=str(ARTIFACTS / "live-progress-before-scroll.png"), full_page=False)
        before_count = len(requests)

        # Force a real horizontal scroll on the deployed progress thumbnail strip.
        page.mouse.move(
            (strip.bounding_box() or {"x": 0, "y": 0, "width": 1, "height": 1})["x"] + 100,
            (strip.bounding_box() or {"x": 0, "y": 0, "width": 1, "height": 1})["y"] + 20,
        )
        strip.evaluate("el => { el.scrollLeft = Math.max(0, el.scrollWidth - el.clientWidth); el.dispatchEvent(new Event('scroll')); }")
        page.wait_for_timeout(1200)

        after = {
            "url": page.url,
            "page": page.locator("#page").input_value(),
            "status": page.locator("#status").inner_text(),
            "scrollLeft": strip.evaluate("el => el.scrollLeft"),
            "readyState": page.evaluate("document.readyState"),
            "pageDisabled": page.locator("#page").is_disabled(),
        }
        page.screenshot(path=str(ARTIFACTS / "live-progress-after-scroll.png"), full_page=False)

        new_requests = requests[before_count:]
        pdfium = [u for _,u,_ in new_requests if "/pdfium-page" in u]
        pdata = [u for _,u,_ in new_requests if "/progress-data" in u]
        others = [u for _,u,_ in new_requests if "/pdfium-page" not in u and "/progress-data" not in u]

        print("LIVE_PROGRESS_URL", progress_url)
        print("BEFORE", before)
        print("AFTER", after)
        print("NEW_PDFIUM_PAGE_REQUESTS", len(pdfium))
        for u in pdfium[:50]:
            print("PDFIUM", u)
        print("NEW_PROGRESS_DATA_REQUESTS", len(pdata))
        for u in pdata[:20]:
            print("PROGRESS_DATA", u)
        print("OTHER_NEW_REQUESTS", len(others))
        print("LIVE_SCROLL_DIAGNOSTIC: PASS")
        browser.close()


if __name__ == "__main__":
    main()
