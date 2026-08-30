import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import DB_PATH, DATA_DIR


PROJECT_ID = 999
PROJECT_NAME = "UIテスト工事"
PDF_NAME = "preview-ui-test.pdf"
DRAWING_KEY = f"project:{PROJECT_ID}"


def create_test_pdf(pdf_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pages = []
    for page_number in range(1, 4):
        image = Image.new("RGB", (1200, 900), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((40, 40, 1160, 860), outline="black", width=4)
        draw.text((80, 80), f"Render Preview Test P{page_number}", fill="black")
        draw.line((120, 220, 1080, 220), fill="black", width=3)
        draw.line((120, 420, 1080, 420), fill="black", width=3)
        draw.line((120, 620, 1080, 620), fill="black", width=3)
        pages.append(image)
    pages[0].save(pdf_path, "PDF", save_all=True, append_images=pages[1:], resolution=150.0)
    for image in pages:
        image.close()


def ensure_schema(connection: sqlite3.Connection) -> None:
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


def seed_preview_fixture() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = DATA_DIR / "pdfs" / PDF_NAME
    create_test_pdf(pdf_path)

    cache_dir = DATA_DIR / "render_cache" / pdf_path.stem
    cache_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as connection:
        ensure_schema(connection)
        connection.execute("DELETE FROM projects WHERE id = ?", (PROJECT_ID,))
        connection.execute("DELETE FROM number_map WHERE drawing_key = ?", (DRAWING_KEY,))
        connection.execute("DELETE FROM weld_progress WHERE drawing_key = ?", (DRAWING_KEY,))
        connection.execute(
            """
            INSERT INTO projects (id, project_name, original_pdf_name, stored_pdf_name, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (PROJECT_ID, PROJECT_NAME, PDF_NAME, PDF_NAME, now),
        )

        candidates = [
            (1, 1, "1", "ocr", 900.0, 1200.0, 120.0, 120.0),
            (1, 2, "2", "ocr", 2400.0, 2400.0, 120.0, 120.0),
            (1, 3, "3", "manual", 3900.0, 3600.0, 120.0, 120.0),
            (3, 1, "F1", "ocr", 1200.0, 1500.0, 180.0, 120.0),
        ]
        connection.executemany(
            """
            INSERT INTO number_map (
                drawing_key, page_number, item_order, number_text, source,
                x, y, width, height, saved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (DRAWING_KEY, page, order, number, source, x, y, width, height, now)
                for page, order, number, source, x, y, width, height in candidates
            ],
        )

        progress_rows = [
            (1, 960, 1260, "1", "未着手", "", "Render preview fixture", now),
            (1, 2460, 2460, "2", "施工中", "", "施工中サンプル", now),
            (1, 3960, 3660, "3", "完了", "2026-08-29", "完了サンプル", now),
        ]
        connection.executemany(
            """
            INSERT INTO weld_progress (
                drawing_key, page_number, position_x, position_y, number_text,
                status, completed_date, work_detail, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (DRAWING_KEY, page, x, y, number, status, completed, detail, updated)
                for page, x, y, number, status, completed, detail, updated in progress_rows
            ],
        )

    print(f"Preview fixture ready: project={PROJECT_ID}, db={DB_PATH}, pdf={pdf_path}")


if __name__ == "__main__":
    seed_preview_fixture()
