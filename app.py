import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

from flask import Flask, jsonify, render_template, request as flask_request

from progress import create_progress_blueprint
from projects import create_projects_blueprint

app = Flask(__name__)

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "weld_tracker.sqlite3"
DRAWING_KEY = "sample.pdf"
PROGRESS_STATUSES = {"未着手", "施工中", "完了"}

app.register_blueprint(create_projects_blueprint(DB_PATH, DATA_DIR))
app.register_blueprint(create_progress_blueprint(DB_PATH))


def get_google_vision_api_key():
    key = os.getenv("GOOGLE_VISION_API_KEY")
    if key:
        return key

    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return None

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == "GOOGLE_VISION_API_KEY":
            return value.strip().strip('"').strip("'")
    return None


def get_db_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
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
        "CREATE INDEX IF NOT EXISTS idx_number_map_page ON number_map (drawing_key, page_number, item_order)"
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
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_weld_progress_page ON weld_progress (drawing_key, page_number)"
    )
    return connection


def normalize_candidate(raw_candidate):
    if not isinstance(raw_candidate, dict):
        raise ValueError("番号候補の形式が不正です。")

    number_text = str(raw_candidate.get("number", "")).strip()
    if not number_text.isdigit() or not 1 <= int(number_text) <= 99:
        raise ValueError("番号は1〜99で指定してください。")

    source = raw_candidate.get("source", "manual")
    if source not in {"ocr", "manual"}:
        source = "manual"

    bbox = raw_candidate.get("bbox")
    if not isinstance(bbox, dict):
        raise ValueError("番号候補の座標がありません。")

    try:
        x = float(bbox.get("x"))
        y = float(bbox.get("y"))
        width = float(bbox.get("w"))
        height = float(bbox.get("h"))
    except (TypeError, ValueError) as exc:
        raise ValueError("番号候補の座標が不正です。") from exc

    if width <= 0 or height <= 0:
        raise ValueError("番号候補の幅・高さが不正です。")

    return {
        "number": number_text,
        "source": source,
        "bbox": {"x": x, "y": y, "w": width, "h": height},
    }


def normalize_progress(body):
    page_number = body.get("pageNumber")
    number_text = str(body.get("number", "")).strip()
    status = str(body.get("status", "")).strip()
    completed_date = str(body.get("completedDate", "")).strip()
    work_detail = str(body.get("workDetail", "")).strip()

    if not isinstance(page_number, int) or page_number < 1:
        raise ValueError("ページ番号が不正です。")
    if not number_text.isdigit() or not 1 <= int(number_text) <= 99:
        raise ValueError("番号は1〜99で指定してください。")
    if status not in PROGRESS_STATUSES:
        raise ValueError("状態が不正です。")
    if len(work_detail) > 1000:
        raise ValueError("作業内容は1000文字以内で入力してください。")
    if completed_date:
        try:
            datetime.strptime(completed_date, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("完了日の形式が不正です。") from exc

    try:
        position_x = int(round(float(body.get("x"))))
        position_y = int(round(float(body.get("y"))))
    except (TypeError, ValueError) as exc:
        raise ValueError("座標が不正です。") from exc

    return {
        "pageNumber": page_number,
        "number": number_text,
        "status": status,
        "completedDate": completed_date,
        "workDetail": work_detail,
        "x": position_x,
        "y": position_y,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/projects-screen")
def projects_screen():
    return render_template("projects.html")


@app.get("/number-map")
def get_number_map():
    page_number = flask_request.args.get("page", type=int)
    if page_number is None or page_number < 1:
        return jsonify({"error": "ページ番号が不正です。"}), 400

    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT number_text, source, x, y, width, height, saved_at
            FROM number_map
            WHERE drawing_key = ? AND page_number = ?
            ORDER BY item_order
            """,
            (DRAWING_KEY, page_number),
        ).fetchall()

    candidates = [
        {
            "number": row["number_text"],
            "source": row["source"],
            "bbox": {
                "x": row["x"],
                "y": row["y"],
                "w": row["width"],
                "h": row["height"],
            },
        }
        for row in rows
    ]

    return jsonify({
        "drawingKey": DRAWING_KEY,
        "pageNumber": page_number,
        "saved": bool(rows),
        "savedAt": rows[0]["saved_at"] if rows else None,
        "candidates": candidates,
    })


@app.post("/number-map")
def save_number_map():
    body = flask_request.get_json(silent=True) or {}
    page_number = body.get("pageNumber")
    raw_candidates = body.get("candidates")

    if not isinstance(page_number, int) or page_number < 1:
        return jsonify({"error": "ページ番号が不正です。"}), 400
    if not isinstance(raw_candidates, list):
        return jsonify({"error": "番号候補が不正です。"}), 400
    if len(raw_candidates) > 1000:
        return jsonify({"error": "番号候補が多すぎます。"}), 400

    try:
        candidates = [normalize_candidate(candidate) for candidate in raw_candidates]
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    saved_at = datetime.now(timezone.utc).isoformat()

    with get_db_connection() as connection:
        connection.execute(
            "DELETE FROM number_map WHERE drawing_key = ? AND page_number = ?",
            (DRAWING_KEY, page_number),
        )
        connection.executemany(
            """
            INSERT INTO number_map (
                drawing_key, page_number, item_order, number_text, source,
                x, y, width, height, saved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    DRAWING_KEY,
                    page_number,
                    index,
                    candidate["number"],
                    candidate["source"],
                    candidate["bbox"]["x"],
                    candidate["bbox"]["y"],
                    candidate["bbox"]["w"],
                    candidate["bbox"]["h"],
                    saved_at,
                )
                for index, candidate in enumerate(candidates)
            ],
        )

    return jsonify({
        "drawingKey": DRAWING_KEY,
        "pageNumber": page_number,
        "savedAt": saved_at,
        "count": len(candidates),
    })


@app.get("/weld-progress")
def get_weld_progress():
    page_number = flask_request.args.get("page", type=int)
    if page_number is None or page_number < 1:
        return jsonify({"error": "ページ番号が不正です。"}), 400

    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT position_x, position_y, number_text, status, completed_date, work_detail, updated_at
            FROM weld_progress
            WHERE drawing_key = ? AND page_number = ?
            ORDER BY id
            """,
            (DRAWING_KEY, page_number),
        ).fetchall()

    items = [
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
    ]
    return jsonify({"drawingKey": DRAWING_KEY, "pageNumber": page_number, "items": items})


@app.post("/weld-progress")
def save_weld_progress():
    body = flask_request.get_json(silent=True) or {}
    try:
        item = normalize_progress(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    updated_at = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as connection:
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
                DRAWING_KEY,
                item["pageNumber"],
                item["x"],
                item["y"],
                item["number"],
                item["status"],
                item["completedDate"],
                item["workDetail"],
                updated_at,
            ),
        )

    return jsonify({**item, "updatedAt": updated_at})


@app.post("/ocr")
def ocr():
    api_key = get_google_vision_api_key()
    if not api_key:
        return jsonify({"error": "GOOGLE_VISION_API_KEY が設定されていません。"}), 503

    body = flask_request.get_json(silent=True) or {}
    image_base64 = body.get("imageBase64", "")
    page_number = body.get("pageNumber")

    if not isinstance(image_base64, str) or not image_base64:
        return jsonify({"error": "解析画像がありません。"}), 400
    if len(image_base64) > 12_000_000:
        return jsonify({"error": "解析画像が大きすぎます。"}), 413

    payload = {
        "requests": [
            {
                "image": {"content": image_base64},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
            }
        ]
    }

    req = request.Request(
        f"https://vision.googleapis.com/v1/images:annotate?key={api_key}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=90) as response:
            vision_response = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return jsonify({"error": "Google Vision APIエラー", "detail": detail[:1200]}), 502
    except Exception as exc:
        return jsonify({"error": "Google Vision APIへの接続に失敗しました。", "detail": str(exc)}), 502

    responses = vision_response.get("responses", [])
    if not responses:
        return jsonify({"error": "Google Vision APIから結果を取得できませんでした。"}), 502

    first = responses[0]
    if first.get("error"):
        return jsonify({"error": "Google Vision APIエラー", "detail": first["error"]}), 502

    annotations = first.get("textAnnotations", [])
    words = []
    for annotation in annotations[1:]:
        text = annotation.get("description", "")
        vertices = annotation.get("boundingPoly", {}).get("vertices", [])
        points = [
            {"x": int(vertex.get("x", 0)), "y": int(vertex.get("y", 0))}
            for vertex in vertices
        ]
        if not text or not points:
            continue
        words.append({"text": text, "vertices": points})

    return jsonify({
        "pageNumber": page_number,
        "wordCount": len(words),
        "words": words,
    })


if __name__ == "__main__":
    app.run(debug=True)
