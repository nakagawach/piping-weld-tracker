import json
import os
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("PUBLIC_BASE_URL", "https://nakagawach.pythonanywhere.com/weld").rstrip("/")


def get_json(path):
    request = Request(f"{BASE}{path}", headers={"User-Agent": "weld-public-readonly-e2e"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def find_project():
    projects = get_json("/projects").get("projects", [])
    for project in projects:
        project_id = project.get("id")
        if not project_id:
            continue
        try:
            items = get_json(f"/projects/{project_id}/progress-list-data").get("items", [])
            info = get_json(f"/projects/{project_id}/pdfium-info")
        except Exception:
            continue
        if items and info.get("pageCount"):
            return project_id, items
    raise RuntimeError("No readable project with progress-list items was found.")


def panel_row(page, number, page_number):
    return page.locator(".progress-list-record").filter(
        has=page.locator(".progress-list-focus", has_text=str(number))
    ).filter(has=page.locator(".progress-list-page", has_text=f"P{page_number}"))


def main():
    project_id, items = find_project()
    first = items[0]
    other_page = next((item for item in items if item.get("pageNumber") != first.get("pageNumber")), None)
    url = f"{BASE}/projects/{project_id}/progress?page={first['pageNumber']}"

    with sync_playwright() as p:
        browser = p.chromium.launch()

        desktop = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        posts = []
        desktop.on("pageerror", lambda exc: errors.append(str(exc)))
        desktop.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        desktop.on("request", lambda req: posts.append(req.url) if req.method == "POST" else None)
        desktop.goto(url, wait_until="domcontentloaded", timeout=60000)
        expect(desktop.locator("#progressListToggle")).to_be_visible(timeout=15000)
        desktop.locator("#progressListToggle").click()
        expect(desktop.locator("#progressListPanel")).to_be_visible()
        expect(desktop.locator(".progress-list-record").first).to_be_visible(timeout=15000)
        box = desktop.locator("#progressListPanel").bounding_box()
        assert box and box["x"] > 900 and box["width"] >= 340, box

        row = panel_row(desktop, first["number"], first["pageNumber"]).first
        row.locator(".progress-list-focus").click()
        expect(desktop.locator("#canvas")).to_have_attribute("data-selected-target", f"{first['pageNumber']}:{round(first['x'])}:{round(first['y'])}", timeout=15000)
        assert "selected" in (row.get_attribute("class") or "")

        row.locator(".progress-list-input").click()
        expect(desktop.locator("#progressDialog")).to_be_visible()
        desktop.locator("#closeDialog").click()

        if other_page:
            other = panel_row(desktop, other_page["number"], other_page["pageNumber"]).first
            other.locator(".progress-list-focus").click()
            expect(desktop.locator("#page")).to_have_value(str(other_page["pageNumber"]), timeout=20000)
            expect(desktop.locator("#canvas")).to_have_attribute("data-selected-target", f"{other_page['pageNumber']}:{round(other_page['x'])}:{round(other_page['y'])}", timeout=20000)

        desktop.locator("#progressListToggle").click()
        expect(desktop.locator("#progressListPanel")).not_to_be_visible()
        assert not posts, posts
        assert not errors, errors
        desktop.close()

        phone = browser.new_page(viewport={"width": 390, "height": 844})
        phone.goto(url, wait_until="domcontentloaded", timeout=60000)
        phone.locator("#progressListToggle").click()
        expect(phone.locator("#progressListPanel")).to_be_visible()
        phone_box = phone.locator("#progressListPanel").bounding_box()
        assert phone_box and 410 <= phone_box["height"] <= 430 and phone_box["x"] <= 1, phone_box
        phone.close()

        portrait = browser.new_page(viewport={"width": 768, "height": 1024})
        portrait.goto(url, wait_until="domcontentloaded", timeout=60000)
        portrait.locator("#progressListToggle").click()
        expect(portrait.locator("#progressListPanel")).to_be_visible()
        portrait_box = portrait.locator("#progressListPanel").bounding_box()
        assert portrait_box and 500 <= portrait_box["height"] <= 525 and portrait_box["x"] <= 1, portrait_box
        portrait.close()

        landscape = browser.new_page(viewport={"width": 1024, "height": 768})
        landscape.goto(url, wait_until="domcontentloaded", timeout=60000)
        landscape.locator("#progressListToggle").click()
        expect(landscape.locator("#progressListPanel")).to_be_visible()
        landscape_box = landscape.locator("#progressListPanel").bounding_box()
        assert landscape_box and landscape_box["x"] > 600 and landscape_box["width"] >= 340, landscape_box
        landscape.close()

        browser.close()

    print("PUBLIC_INTEGRATED_PROGRESS_LIST_E2E: PASS")


if __name__ == "__main__":
    main()
