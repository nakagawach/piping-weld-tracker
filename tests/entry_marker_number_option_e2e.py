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
    click_ocr,
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
    assert response.get_json()["numberMarkerTargets"] == []

    response = client.post(
        f"/projects/{PROJECT_ID}/number-map",
        json={
            "pageNumber": 1,
            "candidates": CANDIDATES,
            "numberMarkerTargets": [
                {"number": "12", "target": {"x": 500, "y": 500}},
            ],
        },
    )
    assert response.status_code == 200
    assert response.get_json()["numberMarkerCount"] == 1

    response = client.get(f"/projects/{PROJECT_ID}/number-map?page=1")
    data = response.get_json()
    assert len(data["numberMarkerTargets"]) == 1
    assert data["numberMarkerTargets"][0]["number"] == "12"

    # Old clients that do not send the individual option must preserve it.
    response = client.post(
        f"/projects/{PROJECT_ID}/number-map",
        json={"pageNumber": 1, "candidates": CANDIDATES},
    )
    assert response.status_code == 200
    response = client.get(f"/projects/{PROJECT_ID}/number-map?page=1")
    data = response.get_json()
    assert len(data["numberMarkerTargets"]) == 1
    assert data["numberMarkerTargets"][0]["number"] == "12"

    response = client.post(
        f"/projects/{PROJECT_ID}/number-map",
        json={
            "pageNumber": 1,
            "candidates": CANDIDATES,
            "numberMarkerTargets": [],
        },
    )
    assert response.status_code == 200
    response = client.get(f"/projects/{PROJECT_ID}/number-map?page=1")
    assert response.get_json()["numberMarkerTargets"] == []

    response = client.post(
        f"/projects/{PROJECT_ID}/number-map",
        json={
            "pageNumber": 1,
            "candidates": CANDIDATES,
            "numberMarkerTargets": [
                {"number": "12", "target": {"x": 123, "y": 456}},
            ],
        },
    )
    assert response.status_code == 400
    assert "丸枠" in response.get_json()["error"]


def checkbox_ocr_point(page, candidate_index):
    return page.evaluate(
        """index => {
            const host = window.__weldEntryAreaHost;
            const item = host.getCandidates()[index];
            const width = Math.max(host.cssPxToOcrX(14), 20);
            const height = Math.max(host.cssPxToOcrY(14), 20);
            const gap = Math.max(host.cssPxToOcrX(3), 4);
            return {
                x: item.bbox.x + item.bbox.w + gap + width / 2,
                y: item.bbox.y + height / 2,
            };
        }""",
        candidate_index,
    )


def click_marker_checkbox(page, candidate_index):
    point = checkbox_ocr_point(page, candidate_index)
    click_ocr(page, point["x"], point["y"])


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
            expect(page.locator("#entryMarkerNumberHelp")).to_be_visible(timeout=5000)
            page.wait_for_function(
                "document.getElementById('entryAreaCanvas')?.dataset.numberMarkerCount === '0'"
            )

            # Enable only marker 12. Marker 34 remains OFF.
            click_marker_checkbox(page, 0)
            page.wait_for_function(
                "document.getElementById('entryAreaCanvas')?.dataset.numberMarkerCount === '1'"
            )
            expect(page.locator("#pageState")).to_contain_text("未保存")
            with page.expect_response(
                lambda response: f"/projects/{PROJECT_ID}/number-map" in response.url
                and response.request.method == "POST"
            ) as response_info:
                page.locator("#save").click()
            saved = response_info.value.json()
            assert saved["numberMarkerCount"] == 1, saved
            page.wait_for_function("document.getElementById('pageState').textContent.includes('保存済')")

            response = page.request.get(f"{BASE_URL}/projects/{PROJECT_ID}/number-map?page=1")
            data = response.json()
            assert [item["number"] for item in data["numberMarkerTargets"]] == ["12"], data

            page.reload(wait_until="domcontentloaded")
            page.wait_for_function(
                "document.getElementById('entryAreaCanvas')?.dataset.numberMarkerCount === '1'"
            )

            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
            page.wait_for_function(
                "document.getElementById('progressEntryAreaCanvas')?.dataset.areaCount === '1'"
            )
            overlay = page.locator("#progressEntryAreaCanvas")
            expect(overlay).to_have_attribute("data-label-placement", "marker-center-individual")
            expect(overlay).to_have_attribute("data-marker-text-count", "1")
            expect(overlay).to_have_attribute("data-label-color", "black")
            expect(overlay).to_have_attribute("data-label-background", "marker-fill")
            expect(overlay).to_have_attribute("data-label-orientation", "screen-upright")

            page.locator("#rotate").click()
            page.wait_for_function("document.getElementById('rotate').textContent.includes('90')")
            expect(overlay).to_have_attribute("data-marker-text-count", "1")
            expect(overlay).to_have_attribute("data-label-orientation", "screen-upright")

            # Turn marker 12 OFF and marker 34 ON, proving the setting is per marker.
            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/entry?page=1", wait_until="domcontentloaded")
            page.wait_for_function(
                "document.getElementById('entryAreaCanvas')?.dataset.numberMarkerCount === '1'"
            )
            click_marker_checkbox(page, 0)
            click_marker_checkbox(page, 1)
            page.wait_for_function(
                "document.getElementById('entryAreaCanvas')?.dataset.numberMarkerCount === '1'"
            )
            with page.expect_response(
                lambda response: f"/projects/{PROJECT_ID}/number-map" in response.url
                and response.request.method == "POST"
            ) as response_info:
                page.locator("#save").click()
            assert response_info.value.json()["numberMarkerCount"] == 1

            response = page.request.get(f"{BASE_URL}/projects/{PROJECT_ID}/number-map?page=1")
            data = response.json()
            assert [item["number"] for item in data["numberMarkerTargets"]] == ["34"], data

            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
            page.wait_for_function(
                "document.getElementById('progressEntryAreaCanvas')?.dataset.areaCount === '1'"
            )
            overlay = page.locator("#progressEntryAreaCanvas")
            expect(overlay).to_have_attribute("data-marker-text-count", "1")
            expect(overlay).to_have_attribute("data-label-placement", "marker-center-individual")

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    print("ENTRY_MARKER_NUMBER_DEFAULT_OFF_PER_MARKER", True)
    print("ENTRY_MARKER_NUMBER_ONE_OF_TWO_ENABLED", True)
    print("ENTRY_MARKER_NUMBER_SETTING_PERSISTS", True)
    print("OLD_CLIENT_PRESERVES_PER_MARKER_SETTING", True)
    print("PROGRESS_ONLY_ENABLED_MARKER_HAS_NUMBER", True)
    print("PROGRESS_MARKER_NUMBER_CENTER_BLACK", True)
    print("PROGRESS_MARKER_NUMBER_BACKGROUND_MATCHES_MARKER", True)
    print("PROGRESS_MARKER_NUMBER_UPRIGHT_ON_ROTATION", True)
    print("ENTRY_MARKER_NUMBER_OPTION_E2E: PASS")


if __name__ == "__main__":
    main()
