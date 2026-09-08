import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path

from flask import Flask
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as app_module  # noqa: E402
from projects import create_projects_blueprint  # noqa: E402


PROJECTS_PAYLOAD = {
    "projects": [
        {
            "id": 1,
            "projectName": "A工事",
            "pdfName": "A.pdf",
            "createdAt": "2026-09-01T00:00:00+00:00",
            "pdfUrl": "pdfs/a.pdf",
            "entryUrl": "projects/1/entry",
        },
        {
            "id": 2,
            "projectName": "B工事",
            "pdfName": "B.pdf",
            "createdAt": "2026-09-02T00:00:00+00:00",
            "pdfUrl": "pdfs/b.pdf",
            "entryUrl": "projects/2/entry",
        },
        {
            "id": 3,
            "projectName": "C工事",
            "pdfName": "C.pdf",
            "createdAt": "2026-09-03T00:00:00+00:00",
            "pdfUrl": "pdfs/c.pdf",
            "entryUrl": "projects/3/entry",
        },
    ]
}


def initialize_existing_schema(db_path, data_dir):
    previous_path = getattr(app_module, "DB_PATH")
    setattr(app_module, "DB_PATH", db_path)
    try:
        connection = app_module.get_db_connection()
        with connection:
            pass
        connection.close()
    finally:
        setattr(app_module, "DB_PATH", previous_path)

    project_app = Flask("dashboard-project-schema")
    project_app.register_blueprint(create_projects_blueprint(db_path, data_dir))
    response = project_app.test_client().get("/projects")
    assert response.status_code == 200


def seed_database(db_path, data_dir):
    initialize_existing_schema(db_path, data_dir)
    connection = sqlite3.connect(db_path)
    connection.executemany(
        "INSERT INTO projects(id, project_name, original_pdf_name, stored_pdf_name, created_at) VALUES (?, ?, ?, ?, ?)",
        [
            (1, "A工事", "A.pdf", "a.pdf", "2026-09-01T00:00:00+00:00"),
            (2, "B工事", "B.pdf", "b.pdf", "2026-09-02T00:00:00+00:00"),
            (3, "C工事", "C.pdf", "c.pdf", "2026-09-03T00:00:00+00:00"),
        ],
    )

    number_rows = []
    for order, center_x in enumerate((100, 200, 300, 400)):
        number_rows.append(
            ("project:1", 1, order, str(order + 1), "manual", center_x - 10, 90, 20, 20, "2026-09-01T00:00:00+00:00")
        )
    number_rows.append(
        ("project:2", 1, 0, "1", "manual", 90, 90, 20, 20, "2026-09-02T00:00:00+00:00")
    )
    connection.executemany(
        """
        INSERT INTO number_map(
            drawing_key, page_number, item_order, number_text, source,
            x, y, width, height, saved_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        number_rows,
    )

    connection.executemany(
        """
        INSERT INTO weld_progress(
            drawing_key, page_number, position_x, position_y, number_text,
            status, completed_date, work_detail, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("project:1", 1, 100, 100, "1", "完了", "2026-09-05", "", "2026-09-05T01:00:00+00:00"),
            ("project:1", 1, 200, 100, "2", "完了", "2026-09-05", "", "2026-09-05T02:00:00+00:00"),
            ("project:1", 1, 300, 100, "3", "施工中", "", "", "2026-09-05T03:00:00+00:00"),
            ("project:2", 1, 100, 100, "1", "完了", "2026-09-06", "", "2026-09-06T01:00:00+00:00"),
        ],
    )
    connection.commit()
    connection.close()


def use_test_database(db_path):
    previous_path = getattr(app_module, "DB_PATH")
    setattr(app_module, "DB_PATH", db_path)
    return previous_path


def restore_database(previous_path):
    setattr(app_module, "DB_PATH", previous_path)


def run_server():
    server = make_server("127.0.0.1", 0, app_module.app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def assert_backend(db_path):
    previous_path = use_test_database(db_path)
    try:
        client = app_module.app.test_client()
        response = client.get("/progress-dashboard-data")
        assert response.status_code == 200
        assert response.headers["Cache-Control"].startswith("no-store")
        data = response.get_json()

        assert data["totals"] == {
            "projects": 3,
            "total": 5,
            "untouched": 1,
            "working": 1,
            "done": 3,
            "completionRate": 60.0,
            "unenteredProjects": 1,
            "completeProjects": 1,
        }

        by_id = {item["id"]: item for item in data["projects"]}
        assert by_id[1]["completionRate"] == 50.0
        assert by_id[1]["status"] == "施工中"
        assert by_id[1]["done"] == 2
        assert by_id[1]["working"] == 1
        assert by_id[1]["untouched"] == 1
        assert by_id[2]["completionRate"] == 100.0
        assert by_id[2]["status"] == "完了"
        assert by_id[3]["completionRate"] == 0
        assert by_id[3]["status"] == "未エントリー"
    finally:
        restore_database(previous_path)


def assert_browser(db_path):
    previous_path = use_test_database(db_path)
    server, thread, base_url = run_server()
    time.sleep(0.1)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                page.route(
                    "**/projects",
                    lambda route: route.fulfill(status=200, content_type="application/json", json=PROJECTS_PAYLOAD),
                )
                page.route(
                    "**/projects/2/progress",
                    lambda route: route.fulfill(status=200, content_type="text/plain", body="progress-2"),
                )
                page.goto(f"{base_url}/projects-screen", wait_until="domcontentloaded")
                expect(page.locator("#progress-dashboard")).to_be_visible()
                expect(page.locator('[data-progress-summary="1"]')).to_contain_text("50.0%")
                expect(page.locator('[data-progress-summary="1"]')).to_contain_text("完了 2 / 4")
                expect(page.locator('[data-progress-summary="3"]')).to_contain_text("未エントリー")
                expect(page.get_by_role("button", name="進捗入力").first).to_be_visible()
                expect(page.get_by_role("button", name="図面エントリー").first).to_be_visible()
                expect(page.get_by_role("button", name="PDFを開く").first).to_be_visible()
                expect(page.get_by_role("button", name="削除").first).to_be_visible()

                page.locator("#progress-dashboard").click()
                page.wait_for_url(f"{base_url}/progress-dashboard")
                expect(page.locator("#overallRate")).to_have_text("60.0%")
                expect(page.locator("#doneCount")).to_have_text("3 / 5")
                expect(page.locator("#projectSummary")).to_contain_text("未エントリー 1件")
                expect(page.locator(".project-card")).to_have_count(3)

                page.locator("#statusFilter").select_option("施工中")
                expect(page.locator(".project-card")).to_have_count(1)
                expect(page.locator(".project-card")).to_contain_text("A工事")
                expect(page.locator("#resultCount")).to_have_text("1件")

                page.locator("#statusFilter").select_option("all")
                page.locator("#search").fill("B.pdf")
                expect(page.locator(".project-card")).to_have_count(1)
                expect(page.locator(".project-card")).to_contain_text("B工事")
                page.locator("#search").fill("")

                page.locator("#sort").select_option("high")
                expect(page.locator(".project-card").first).to_contain_text("B工事")
                page.locator(".project-card").first.click()
                page.wait_for_url(f"{base_url}/projects/2/progress")

                mobile = browser.new_page(viewport={"width": 390, "height": 844})
                mobile.goto(f"{base_url}/progress-dashboard", wait_until="domcontentloaded")
                expect(mobile.locator("#overallRate")).to_have_text("60.0%")
                expect(mobile.locator(".project-card")).to_have_count(3)
                no_horizontal_overflow = mobile.evaluate(
                    "document.documentElement.scrollWidth <= window.innerWidth + 1"
                )
                assert no_horizontal_overflow
            finally:
                browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)
        restore_database(previous_path)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        db_path = root / "dashboard.sqlite3"
        data_dir = root / "project-data"
        seed_database(db_path, data_dir)
        assert_backend(db_path)
        assert_browser(db_path)

    print("progress_dashboard_e2e: OK")


if __name__ == "__main__":
    main()
