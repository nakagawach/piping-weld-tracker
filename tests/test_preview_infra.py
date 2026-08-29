import sqlite3
import sys
from pathlib import Path

from werkzeug.test import Client
from werkzeug.wrappers import Response

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import DB_PATH, DATA_DIR
from test_preview_wsgi import application
from tests.seed_preview_fixture import DRAWING_KEY, PDF_NAME, PROJECT_ID, seed_preview_fixture


def assert_fixture() -> None:
    seed_preview_fixture()
    assert DB_PATH.exists(), DB_PATH
    assert str(DB_PATH).startswith(str(ROOT)), DB_PATH
    assert "/home/nakagawach/" not in str(DB_PATH)

    pdf_path = DATA_DIR / "pdfs" / PDF_NAME
    assert pdf_path.exists(), pdf_path

    with sqlite3.connect(DB_PATH) as connection:
        project = connection.execute(
            "SELECT project_name, stored_pdf_name FROM projects WHERE id = ?", (PROJECT_ID,)
        ).fetchone()
        assert project == ("UIテスト工事", PDF_NAME), project

        page_counts = dict(
            connection.execute(
                "SELECT page_number, COUNT(*) FROM number_map WHERE drawing_key = ? GROUP BY page_number",
                (DRAWING_KEY,),
            ).fetchall()
        )
        assert page_counts.get(1) == 3, page_counts
        assert 2 not in page_counts, page_counts
        assert page_counts.get(3) == 1, page_counts

        statuses = {
            row[0]
            for row in connection.execute(
                "SELECT status FROM weld_progress WHERE drawing_key = ?", (DRAWING_KEY,)
            ).fetchall()
        }
        assert statuses == {"未着手", "施工中", "完了"}, statuses


def assert_pdfium() -> None:
    import pypdfium2 as pdfium

    pdf_path = DATA_DIR / "pdfs" / PDF_NAME
    document = pdfium.PdfDocument(str(pdf_path))
    try:
        assert len(document) == 3
    finally:
        document.close()


def assert_routes() -> None:
    client = Client(application, Response)

    for path in ["/", "/healthz", "/weld/", "/weld/projects-screen"]:
        response = client.get(path)
        assert response.status_code == 200, (path, response.status_code, response.data[:200])

    for path in [
        f"/weld/projects/{PROJECT_ID}/entry?page=1",
        f"/weld/projects/{PROJECT_ID}/progress?page=1",
        f"/weld/projects/{PROJECT_ID}/thumbnails?source=progress&page=1",
    ]:
        response = client.get(path)
        assert response.status_code == 200, (path, response.status_code, response.data[:200])

    info = client.get(f"/weld/projects/{PROJECT_ID}/pdfium-info")
    assert info.status_code == 200, info.data[:200]
    assert info.get_json()["pageCount"] == 3

    for long_edge in (500, 1600):
        image = client.get(
            f"/weld/projects/{PROJECT_ID}/pdfium-page?page=1&longEdge={long_edge}&format=jpeg"
        )
        assert image.status_code == 200, (long_edge, image.status_code, image.data[:200])
        assert image.headers.get("Content-Type", "").startswith("image/jpeg")


def assert_test_db_write_read() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            "UPDATE projects SET project_name = ? WHERE id = ?", ("UIテスト工事-WRITE", PROJECT_ID)
        )
        value = connection.execute(
            "SELECT project_name FROM projects WHERE id = ?", (PROJECT_ID,)
        ).fetchone()[0]
        assert value == "UIテスト工事-WRITE"
    seed_preview_fixture()


def assert_no_production_hooks() -> None:
    checked = [
        ROOT / "test_preview_wsgi.py",
        ROOT / "tests" / "seed_preview_fixture.py",
        ROOT / "render.yaml",
    ]
    forbidden = [
        "PYTHONANYWHERE_API_TOKEN",
        "nakagawach.pythonanywhere.com",
        "/home/nakagawach/piping-weld-tracker",
        "/var/www/nakagawach_pythonanywhere_com_wsgi.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in checked)
    for token in forbidden:
        assert token not in combined, token


def main() -> None:
    assert_fixture()
    assert_pdfium()
    assert_routes()
    assert_test_db_write_read()
    assert_no_production_hooks()
    print("Render preview infrastructure tests: PASS")


if __name__ == "__main__":
    main()
