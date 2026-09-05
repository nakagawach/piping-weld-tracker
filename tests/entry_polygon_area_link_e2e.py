import io
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

from app import DB_PATH, app, get_db_connection


PROJECT_ID = 993
BASE_URL = "http://127.0.0.1:8793"
SCALE = 1600 / 6000


def white_png():
    image = Image.new("RGB", (1600, 1000), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def seed_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db_connection():
        pass
    response = app.test_client().get("/projects")
    assert response.status_code == 200

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("DELETE FROM projects WHERE id = ?", (PROJECT_ID,))
        connection.execute(
            "INSERT INTO projects (id, project_name, original_pdf_name, stored_pdf_name, created_at) VALUES (?, ?, ?, ?, ?)",
            (PROJECT_ID, "ポリゴンE2E", "area-test.pdf", "area-test.pdf", "2026-09-05T00:00:00+00:00"),
        )
        key = f"project:{PROJECT_ID}"
        area_key = f"project-area:{PROJECT_ID}"
        option_key = f"project-option:{PROJECT_ID}"
        connection.execute(
            "DELETE FROM number_map WHERE drawing_key IN (?, ?, ?)",
            (key, area_key, option_key),
        )
        connection.execute("DELETE FROM weld_progress WHERE drawing_key = ?", (key,))
        connection.execute(
            """
            INSERT INTO number_map (
                drawing_key,page_number,item_order,number_text,source,x,y,width,height,saved_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (key, 1, 0, "12", "manual", 440, 440, 120, 120, "2026-09-05T00:00:00+00:00"),
        )
        connection.execute(
            """
            INSERT INTO number_map (
                drawing_key,page_number,item_order,number_text,source,x,y,width,height,saved_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (key, 1, 1, "34", "manual", 940, 940, 120, 120, "2026-09-05T00:00:00+00:00"),
        )


def run_server():
    server = make_server("127.0.0.1", 8793, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def save_initial_area():
    client = app.test_client()
    payload = {
        "pageNumber": 1,
        "candidates": [
            {"number": "12", "source": "manual", "bbox": {"x": 440, "y": 440, "w": 120, "h": 120}},
            {"number": "34", "source": "manual", "bbox": {"x": 940, "y": 940, "w": 120, "h": 120}},
        ],
        "areas": [
            {
                "number": "12",
                "target": {"x": 500, "y": 500},
                "points": [[700, 350], [900, 350], [900, 650], [700, 650]],
            }
        ],
    }
    response = client.post(f"/projects/{PROJECT_ID}/number-map", json=payload)
    assert response.status_code == 200, response.get_data(as_text=True)
    data = response.get_json()
    assert data["count"] == 2
    assert data["areaCount"] == 1

    response = client.get(f"/projects/{PROJECT_ID}/number-map?page=1")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["areas"]) == 1
    assert data["areas"][0]["number"] == "12"
    assert data["showNumberInMarker"] is False

    bad = dict(payload)
    bad["areas"] = [{"number": "12", "target": {"x": 123, "y": 456}, "points": [[1, 1], [10, 1], [10, 10]]}]
    response = client.post(f"/projects/{PROJECT_ID}/number-map", json=bad)
    assert response.status_code == 400
    assert "丸枠" in response.get_json()["error"]

    response = client.post(
        f"/projects/{PROJECT_ID}/number-map",
        json={"pageNumber": 1, "candidates": payload["candidates"]},
    )
    assert response.status_code == 200
    response = client.get(f"/projects/{PROJECT_ID}/number-map?page=1")
    assert len(response.get_json()["areas"]) == 1


def client_point(page, ocr_x, ocr_y):
    return page.locator("#canvas").evaluate(
        """(canvas, p) => {
            const r = canvas.getBoundingClientRect();
            const scale = 1600 / 6000;
            return {
                x: r.left + (p.x * scale) * r.width / canvas.width,
                y: r.top + (p.y * scale) * r.height / canvas.height,
            };
        }""",
        {"x": ocr_x, "y": ocr_y},
    )


def click_ocr(page, x, y, count=1):
    point = client_point(page, x, y)
    if count == 2:
        page.mouse.dblclick(point["x"], point["y"], delay=40)
    else:
        page.mouse.click(point["x"], point["y"])


def main():
    seed_database()
    save_initial_area()
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
            expect(page.locator("#areaCreate")).to_be_visible(timeout=5000)
            expect(page.locator("#entryShowNumberInMarker")).to_be_visible(timeout=5000)
            expect(page.locator("#entryShowNumberInMarker")).not_to_be_checked()
            expect(page.locator("#entryZoomIn")).to_be_visible(timeout=5000)
            expect(page.locator("#entryZoomOut")).to_be_visible(timeout=5000)
            expect(page.locator("#entryZoomReset")).to_be_visible(timeout=5000)
            page.wait_for_function(
                "document.getElementById('entryAreaCanvas')?.dataset.areaCount === '1'"
            )

            canvas = page.locator("#canvas")
            initial_width = canvas.bounding_box()["width"]
            page.locator("#entryZoomIn").click()
            page.wait_for_function("parseFloat(document.getElementById('canvas').dataset.entryZoom || '1') > 1")
            assert canvas.bounding_box()["width"] > initial_width

            page.locator("#entryZoomReset").click()
            page.wait_for_function("Math.abs(parseFloat(document.getElementById('canvas').dataset.entryZoom || '0') - 1) < 0.01")
            reset_width = canvas.bounding_box()["width"]
            assert abs(reset_width - initial_width) < 2, (initial_width, reset_width)

            viewer_box = page.locator(".viewer").bounding_box()
            page.mouse.move(viewer_box["x"] + viewer_box["width"] / 2, viewer_box["y"] + viewer_box["height"] / 2)
            page.keyboard.down("Control")
            page.mouse.wheel(0, -120)
            page.keyboard.up("Control")
            page.wait_for_function("parseFloat(document.getElementById('canvas').dataset.entryZoom || '1') > 1")
            assert canvas.bounding_box()["width"] > reset_width

            page.locator("#areaCreate").click()
            expect(page.locator("#areaCreate")).to_have_class("button active")

            click_ocr(page, 1000, 1000)
            click_ocr(page, 1500, 800)
            click_ocr(page, 2050, 800)
            click_ocr(page, 2050, 1400)
            click_ocr(page, 1500, 1400, count=2)
            page.wait_for_function(
                "document.getElementById('entryAreaCanvas')?.dataset.areaCount === '2'"
            )

            with page.expect_response(
                lambda response: f"/projects/{PROJECT_ID}/number-map" in response.url and response.request.method == "POST"
            ) as response_info:
                page.locator("#save").click()
            saved = response_info.value.json()
            assert saved["count"] == 2, saved
            assert saved["areaCount"] == 2, saved
            assert saved["showNumberInMarker"] is False, saved
            page.wait_for_function("document.getElementById('pageState').textContent.includes('保存済')")

            page.reload(wait_until="domcontentloaded")
            page.wait_for_function(
                "document.getElementById('entryAreaCanvas')?.dataset.areaCount === '2'"
            )
            expect(page.locator("#entryShowNumberInMarker")).not_to_be_checked()

            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
            page.wait_for_function(
                "document.getElementById('progressEntryAreaCanvas')?.dataset.areaCount === '2'"
            )
            overlay = page.locator("#progressEntryAreaCanvas")
            expect(overlay).to_have_attribute("data-label-placement", "hidden")
            expect(overlay).to_have_attribute("data-marker-text-count", "0")
            expect(overlay).to_have_attribute("data-label-orientation", "screen-upright")
            page.locator("#rotate").click()
            page.wait_for_function("document.getElementById('rotate').textContent.includes('90')")
            expect(overlay).to_have_attribute("data-label-placement", "hidden")
            for _ in range(3):
                page.locator("#rotate").click()
            page.wait_for_function("document.getElementById('rotate').textContent.includes('0')")
            # Rotation also performs adaptive layout and position reset. Wait for that
            # asynchronous layout pass before asserting source-coordinate hit testing.
            page.wait_for_timeout(250)

            click_ocr(page, 1800, 1100)
            expect(page.locator("#progressDialog")).to_be_visible()
            expect(page.locator("#dialogTarget")).to_contain_text("34")
            page.locator("#closeDialog").click()
            expect(page.locator("#progressDialog")).not_to_be_visible()

            click_ocr(page, 1250, 1000)
            page.wait_for_timeout(150)
            expect(page.locator("#progressDialog")).not_to_be_visible()

            click_ocr(page, 1000, 1000)
            expect(page.locator("#progressDialog")).to_be_visible()
            expect(page.locator("#dialogTarget")).to_contain_text("34")

            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

    client = app.test_client()
    response = client.get(f"/projects/{PROJECT_ID}/number-map?page=1")
    data = response.get_json()
    assert response.status_code == 200
    assert len(data["areas"]) == 2, data
    assert {area["number"] for area in data["areas"]} == {"12", "34"}
    assert data["showNumberInMarker"] is False

    print("ENTRY_ZOOM_BUTTONS_AND_CTRL_WHEEL", True)
    print("ENTRY_POLYGON_CREATE_WHILE_ZOOMED", True)
    print("ENTRY_POLYGON_CREATE_SAVE_RELOAD", True)
    print("PROGRESS_MARKER_NUMBER_DEFAULT_HIDDEN", True)
    print("PROGRESS_POLYGON_OPENS_PAIRED_TARGET", True)
    print("CONNECTOR_LINE_DISPLAY_ONLY", True)
    print("ROUND_MARKER_EXISTING_HIT_RETAINED", True)
    print("ENTRY_POLYGON_AREA_LINK_E2E: PASS")


if __name__ == "__main__":
    main()
