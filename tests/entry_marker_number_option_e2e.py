import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

TEST_DIR = Path(__file__).resolve().parent
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

from entry_polygon_area_link_e2e import (  # noqa: E402
    BASE_URL,
    PROJECT_ID,
    run_server,
    save_initial_area,
    seed_database,
    white_png,
)
from app import app  # noqa: E402


CANDIDATES = [
    {"number": "12", "source": "manual", "bbox": {"x": 440, "y": 440, "w": 120, "h": 120}},
    {"number": "34", "source": "manual", "bbox": {"x": 940, "y": 940, "w": 120, "h": 120}},
]


def assert_backend_option_compatibility():
    client = app.test_client()

    response = client.get(f"/projects/{PROJECT_ID}/number-map?page=1")
    assert response.status_code == 200
    assert response.get_json()["showNumberInMarker"] is False

    response = client.post(
        f"/projects/{PROJECT_ID}/number-map",
        json={
            "pageNumber": 1,
            "candidates": CANDIDATES,
            "showNumberInMarker": True,
        },
    )
    assert response.status_code == 200
    assert response.get_json()["showNumberInMarker"] is True

    # Old clients that do not send the option must preserve the saved project setting.
    response = client.post(
        f"/projects/{PROJECT_ID}/number-map",
        json={"pageNumber": 1, "candidates": CANDIDATES},
    )
    assert response.status_code == 200
    response = client.get(f"/projects/{PROJECT_ID}/number-map?page=1")
    assert response.get_json()["showNumberInMarker"] is True

    response = client.post(
        f"/projects/{PROJECT_ID}/number-map",
        json={
            "pageNumber": 1,
            "candidates": CANDIDATES,
            "showNumberInMarker": False,
        },
    )
    assert response.status_code == 200
    response = client.get(f"/projects/{PROJECT_ID}/number-map?page=1")
    assert response.get_json()["showNumberInMarker"] is False


def main():
    seed_database()
    save_initial_area()
    assert_backend_option_compatibility()

    png = white_png()
    server, thread = run_server()
    time.sleep(0.2)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.route(
                f"**/projects/{PROJECT_ID}/pdfium-info",
                lambda route: route.fulfill(status=200, content_type="application/json", body='{"pageCount":1}'),
            )
            page.route(
                f"**/projects/{PROJECT_ID}/pdfium-page**",
                lambda route: route.fulfill(status=200, content_type="image/png", body=png),
            )

            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/entry?page=1", wait_until="domcontentloaded")
            checkbox = page.locator("#entryShowNumberInMarker")
            expect(checkbox).to_be_visible(timeout=5000)
            expect(checkbox).not_to_be_checked()

            checkbox.check()
            expect(page.locator("#pageState")).to_contain_text("未保存")
            with page.expect_response(
                lambda response: f"/projects/{PROJECT_ID}/number-map" in response.url
                and response.request.method == "POST"
            ) as response_info:
                page.locator("#save").click()
            assert response_info.value.json()["showNumberInMarker"] is True
            page.wait_for_function("document.getElementById('pageState').textContent.includes('保存済')")

            page.reload(wait_until="domcontentloaded")
            expect(page.locator("#entryShowNumberInMarker")).to_be_checked(timeout=5000)

            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
            page.wait_for_function(
                "document.getElementById('progressEntryAreaCanvas')?.dataset.areaCount === '1'"
            )
            overlay = page.locator("#progressEntryAreaCanvas")
            expect(overlay).to_have_attribute("data-label-placement", "marker-center")
            expect(overlay).to_have_attribute("data-marker-text-count", "2")
            expect(overlay).to_have_attribute("data-label-color", "black")
            expect(overlay).to_have_attribute("data-label-background", "marker-fill")
            expect(overlay).to_have_attribute("data-label-orientation", "screen-upright")

            page.locator("#rotate").click()
            page.wait_for_function("document.getElementById('rotate').textContent.includes('90')")
            expect(overlay).to_have_attribute("data-label-placement", "marker-center")
            expect(overlay).to_have_attribute("data-label-orientation", "screen-upright")

            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/entry?page=1", wait_until="domcontentloaded")
            checkbox = page.locator("#entryShowNumberInMarker")
            expect(checkbox).to_be_checked(timeout=5000)
            checkbox.uncheck()
            with page.expect_response(
                lambda response: f"/projects/{PROJECT_ID}/number-map" in response.url
                and response.request.method == "POST"
            ) as response_info:
                page.locator("#save").click()
            assert response_info.value.json()["showNumberInMarker"] is False

            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
            page.wait_for_function(
                "document.getElementById('progressEntryAreaCanvas')?.dataset.areaCount === '1'"
            )
            overlay = page.locator("#progressEntryAreaCanvas")
            expect(overlay).to_have_attribute("data-label-placement", "hidden")
            expect(overlay).to_have_attribute("data-marker-text-count", "0")

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("ENTRY_MARKER_NUMBER_DEFAULT_OFF", True)
    print("ENTRY_MARKER_NUMBER_SETTING_PERSISTS", True)
    print("OLD_CLIENT_PRESERVES_MARKER_NUMBER_SETTING", True)
    print("PROGRESS_MARKER_NUMBER_CENTER_BLACK", True)
    print("PROGRESS_MARKER_NUMBER_BACKGROUND_MATCHES_MARKER", True)
    print("PROGRESS_MARKER_NUMBER_UPRIGHT_ON_ROTATION", True)
    print("PROGRESS_MARKER_NUMBER_OFF_HIDES_TEXT", True)
    print("ENTRY_MARKER_NUMBER_OPTION_E2E: PASS")


if __name__ == "__main__":
    main()
