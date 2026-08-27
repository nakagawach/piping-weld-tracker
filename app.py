import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

from flask import Flask, jsonify, render_template, request as flask_request

from global_favorites import create_global_favorites_blueprint
from progress import create_progress_blueprint
from projects import create_projects_blueprint
from thumbnail_grid import create_thumbnail_grid_blueprint
from ui_baseline import create_ui_baseline_blueprint

app = Flask(__name__)

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "weld_tracker.sqlite3"
DRAWING_KEY = "sample.pdf"
PROGRESS_STATUSES = {"未着手", "施工中", "完了"}

app.register_blueprint(create_projects_blueprint(DB_PATH, DATA_DIR))
app.register_blueprint(create_progress_blueprint(DB_PATH))
app.register_blueprint(create_thumbnail_grid_blueprint(DB_PATH))
app.register_blueprint(create_global_favorites_blueprint(DB_PATH))
app.register_blueprint(create_ui_baseline_blueprint())


def get_google_vision_api_key():
    key = os.getenv("GOOGLE_VISION_API_KEY")
    if key:
        return key
    env_path = APP_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("GOOGLE_VISION_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def ensure_database():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as connection:
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
                saved_at TEXT NOT NULL,
                UNIQUE(drawing_key, page_number, item_order)
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
                completed_date TEXT,
                work_detail TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(drawing_key, page_number, position_x, position_y)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                original_pdf_name TEXT NOT NULL,
                stored_pdf_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.commit()


ensure_database()


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/projects-screen")
def projects_screen():
    return render_template("projects.html")


@app.get("/api/progress")
def get_progress():
    page_number = flask_request.args.get("page", type=int)
    if page_number is None or page_number < 1:
        return jsonify({"error": "ページ番号が不正です。"}), 400

    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT position_x, position_y, number_text, status,
                   completed_date, work_detail, updated_at
            FROM weld_progress
            WHERE drawing_key = ? AND page_number = ?
            ORDER BY id
            """,
            (DRAWING_KEY, page_number),
        ).fetchall()

    return jsonify({
        "drawingKey": DRAWING_KEY,
        "pageNumber": page_number,
        "items": [
            {
                "x": row["position_x"],
                "y": row["position_y"],
                "number": row["number_text"],
                "status": row["status"],
                "completedDate": row["completed_date"],
                "workDetail": row["work_detail"],
                "updatedAt": row["updated_at"],
            }
            for row in rows
        ],
    })


@app.post("/api/progress")
def save_progress():
    body = flask_request.get_json(silent=True) or {}
    page_number = body.get("pageNumber")
    number_text = str(body.get("number", "")).strip()
    status = str(body.get("status", "")).strip()
    completed_date = str(body.get("completedDate", "")).strip()
    work_detail = str(body.get("workDetail", "")).strip()

    if not isinstance(page_number, int) or page_number < 1:
        return jsonify({"error": "ページ番号が不正です。"}), 400
    if not number_text:
        return jsonify({"error": "対象番号が不正です。"}), 400
    if status not in PROGRESS_STATUSES:
        return jsonify({"error": "状態が不正です。"}), 400
    if len(work_detail) > 1000:
        return jsonify({"error": "メモ・作業内容は1000文字以内で入力してください。"}), 400
    if completed_date:
        try:
            datetime.strptime(completed_date, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "完了日の形式が不正です。"}), 400

    try:
        position_x = int(round(float(body.get("x"))))
        position_y = int(round(float(body.get("y"))))
    except (TypeError, ValueError):
        return jsonify({"error": "座標が不正です。"}), 400

    updated_at = utc_now_iso()
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO weld_progress (
                drawing_key, page_number, position_x, position_y, number_text,
                status, completed_date, work_detail, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(drawing_key, page_number, position_x, position_y)
            DO UPDATE SET
                number_text = excluded.number_text,
                status = excluded.status,
                completed_date = excluded.completed_date,
                work_detail = excluded.work_detail,
                updated_at = excluded.updated_at
            """,
            (
                DRAWING_KEY, page_number, position_x, position_y, number_text,
                status, completed_date, work_detail, updated_at,
            ),
        )
        connection.commit()

    return jsonify({"ok": True, "updatedAt": updated_at})


@app.post("/api/vision")
def vision_api():
    api_key = get_google_vision_api_key()
    if not api_key:
        return jsonify({"error": "Google Vision APIキーが設定されていません。"}), 500

    body = flask_request.get_json(silent=True) or {}
    image_content = body.get("imageContent")
    if not image_content:
        return jsonify({"error": "OCR画像がありません。"}), 400

    payload = json.dumps({
        "requests": [{
            "image": {"content": image_content},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
        }]
    }).encode("utf-8")
    req = request.Request(
        f"https://vision.googleapis.com/v1/images:annotate?key={api_key}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=90) as response:
            result = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return jsonify({"error": f"Google Vision APIエラー ({exc.code})", "detail": detail[:500]}), 502
    except Exception as exc:
        return jsonify({"error": f"Google Vision APIへの接続に失敗しました: {exc}"}), 502

    return jsonify(result)
