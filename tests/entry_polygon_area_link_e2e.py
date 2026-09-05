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

from app import DB_PATH, app


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
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                original_pdf_name TEXT NOT NULL,
                stored_pdf_name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS number_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drawing_key TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                item_order INTEGER NOT NULL,
                number_text TEXT NOT NULL,
                source TEXT NOT NULL,
                x REAL NOT NULL,
                y REAL NOT NULL,
                width REAL NOT NULL,
                height REAL NOT NULL,
                saved_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS weld_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drawing_key TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                position_x INTEGER NOT NULL,
                position_y INTEGER NOT NULL,
                number_text TEXT NOT NULL,
                status TEXT NOT NULL,
                completed_date TEXT NOT NULL DEFAULT '',
                work_detail TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                UNIQUE(drawing_key, page_number, position_x, position_y)
            )
            """
        )
        connection.execute("DELETE FROM projects WHERE id = ?", (PROJECT_ID,))
        connection.execute(
            "INSERT INTO projects (id, project_name, original_pdf_name, stored_pdf_name, created_at) VALUES (?, ?, ?, ?, ?)",
            (PROJECT_ID, "ポリゴンE2E", "area-test.pdf", "area-test.pdf", "2026-09-05T00:00:00+00:00"),
        )
        key = f"project:{PROJECT_ID}"
        connection.execute("DELETE FROM number_map WHERE drawing_key = ?", (key,))
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

    bad = dict(payload)
    bad["areas"] = [{"number": "12", "target": {"x": 123, "y": 456}, "points": [[1, 1], [10, 1], [10, 10]]}]
    response = client.post(f"/projects/{PROJECT_ID}/number-map", json=bad)
    assert response.status_code == 400
    assert "丸枠" in response.get_json()["error"]

    # Old clients that save candidates only must not erase polygon data.
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

            # Entry: existing polygon loads, then create a second polygon paired with marker 34.
            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/entry?page=1", wait_until="domcontentloaded")
            expect(page.locator("#areaCreate")).to_be_visible(timeout=5000)
            page.wait_for_function(
                "document.getElementById('entryAreaCanvas')?.dataset.areaCount === '1'"
            )
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
            page.wait_for_function("document.getElementById('pageState').textContent.includes('保存済')")

            # Reloading the Entry page must restore both saved polygons.
            page.reload(wait_until="domcontentloaded")
            page.wait_for_function(
                "document.getElementById('entryAreaCanvas')?.dataset.areaCount === '2'"
            )

            # Progress: polygon interior opens exactly the paired target's existing progress dialog.
            page.goto(f"{BASE_URL}/projects/{PROJECT_ID}/progress?page=1", wait_until="domcontentloaded")
            page.wait_for_function(
                "document.getElementById('progressEntryAreaCanvas')?.dataset.areaCount === '2'"
            )
            click_ocr(page, 1800, 1100)
            expect(page.locator("#progressDialog")).to_be_visible()
            expect(page.locator("#dialogTarget")).to_contain_text("34")
            page.locator("#closeDialog").click()
            expect(page.locator("#progressDialog")).not_to_be_visible()

            # Connector midpoint is display-only: it must NOT open the progress dialog.
            click_ocr(page, 1250, 1000)
            page.wait_for_timeout(150)
            expect(page.locator("#progressDialog")).not_to_be_visible()

            # Existing round marker remains interactive and opens the same target.
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

    print("ENTRY_POLYGON_CREATE_SAVE_RELOAD", True)
    print("PROGRESS_POLYGON_OPENS_PAIRED_TARGET", True)
    print("CONNECTOR_LINE_DISPLAY_ONLY", True)
    print("ROUND_MARKER_EXISTING_HIT_RETAINED", True)
    print("ENTRY_POLYGON_AREA_LINK_E2E: PASS")


if __name__ == "__main__":
    main()
