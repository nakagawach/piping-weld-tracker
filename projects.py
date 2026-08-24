import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request, send_file, send_from_directory

from project_render import normalize_label, render_cached, vision_ocr


def create_projects_blueprint(db_path: Path, data_dir: Path):
    blueprint = Blueprint("projects", __name__)
    upload_dir = data_dir / "pdfs"
    cache_dir = data_dir / "render_cache"

    def ensure_table(connection):
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

    def connect():
        data_dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        ensure_table(connection)
        return connection

    def project_drawing_key(project_id):
        return f"project:{project_id}"

    def get_project_pdf_path(project_id):
        with connect() as connection:
            row = connection.execute(
                "SELECT stored_pdf_name FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        pdf_path = upload_dir / row["stored_pdf_name"]
        return pdf_path if pdf_path.exists() else None

    def get_project_cache_dir(project_id):
        pdf_path = get_project_pdf_path(project_id)
        if pdf_path is None:
            return None
        return cache_dir / pdf_path.stem

    def normalize_candidate(raw_candidate):
        if not isinstance(raw_candidate, dict):
            raise ValueError("番号候補の形式が不正です。")

        number_text = normalize_label(raw_candidate.get("number", ""))
        if not number_text:
            raise ValueError("番号は数字、丸数字、またはF1/S2/A-12等の英数字で指定してください。")

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

    @blueprint.get("/projects")
    def list_projects():
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT id, project_name, original_pdf_name, stored_pdf_name, created_at
                FROM projects
                ORDER BY id DESC
                """
            ).fetchall()

        return jsonify({
            "projects": [
                {
                    "id": row["id"],
                    "projectName": row["project_name"],
                    "pdfName": row["original_pdf_name"],
                    "createdAt": row["created_at"],
                    "pdfUrl": f"pdfs/{row['stored_pdf_name']}",
                    "entryUrl": f"projects/{row['id']}/entry",
                }
                for row in rows
            ]
        })

    @blueprint.post("/projects")
    def register_project():
        project_name = request.form.get("projectName", "").strip()
        pdf = request.files.get("pdf")

        if not project_name:
            return jsonify({"error": "工事名を入力してください。"}), 400
        if len(project_name) > 200:
            return jsonify({"error": "工事名は200文字以内で入力してください。"}), 400
        if pdf is None or not pdf.filename:
            return jsonify({"error": "PDFを選択してください。"}), 400

        original_name = Path(pdf.filename).name
        if Path(original_name).suffix.lower() != ".pdf":
            return jsonify({"error": "PDFファイルを選択してください。"}), 400

        header = pdf.stream.read(5)
        pdf.stream.seek(0)
        if header != b"%PDF-":
            return jsonify({"error": "PDFファイルとして確認できませんでした。"}), 400

        upload_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}.pdf"
        destination = upload_dir / stored_name
        pdf.save(destination)

        created_at = datetime.now(timezone.utc).isoformat()
        try:
            with connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO projects (project_name, original_pdf_name, stored_pdf_name, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (project_name, original_name, stored_name, created_at),
                )
                project_id = cursor.lastrowid
        except Exception:
            destination.unlink(missing_ok=True)
            raise

        return jsonify({
            "id": project_id,
            "projectName": project_name,
            "pdfName": original_name,
            "createdAt": created_at,
            "pdfUrl": f"pdfs/{stored_name}",
            "entryUrl": f"projects/{project_id}/entry",
        }), 201

    @blueprint.delete("/projects/<int:project_id>")
    def delete_project(project_id):
        with connect() as connection:
            row = connection.execute(
                "SELECT stored_pdf_name FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if row is None:
                return jsonify({"error": "工事が見つかりません。"}), 404

            connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            stored_name = row["stored_pdf_name"]

        pdf_path = upload_dir / stored_name
        try:
            pdf_path.unlink(missing_ok=True)
            shutil.rmtree(cache_dir / Path(stored_name).stem, ignore_errors=True)
        except OSError:
            return jsonify({
                "error": "工事情報は削除しましたが、PDFファイルの削除に失敗しました。"
            }), 500

        return jsonify({"deleted": True, "id": project_id})

    @blueprint.get("/projects/<int:project_id>/entry")
    def project_entry(project_id):
        with connect() as connection:
            row = connection.execute(
                """
                SELECT project_name, original_pdf_name, stored_pdf_name
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()

        if row is None:
            return "工事が見つかりません。", 404

        return render_template(
            "project_entry.html",
            project_id=project_id,
            project_name=row["project_name"],
            pdf_name=row["original_pdf_name"],
            pdf_url=f"../../pdfs/{row['stored_pdf_name']}",
        )

    @blueprint.get("/projects/<int:project_id>/pdfium-info")
    def pdfium_info(project_id):
        pdf_path = get_project_pdf_path(project_id)
        if pdf_path is None:
            return jsonify({"error": "PDFが見つかりません。"}), 404
        try:
            import pypdfium2 as pdfium
        except ImportError:
            return jsonify({"error": "pypdfium2がPythonAnywhere環境に未インストールです。"}), 503

        document = None
        try:
            document = pdfium.PdfDocument(str(pdf_path))
            return jsonify({"pageCount": len(document)})
        except Exception as exc:
            return jsonify({"error": f"PDFiumでPDF情報を取得できませんでした: {exc}"}), 500
        finally:
            if document is not None:
                document.close()

    @blueprint.get("/projects/<int:project_id>/pdfium-page")
    def pdfium_page(project_id):
        page_number = request.args.get("page", type=int, default=1)
        long_edge = request.args.get("longEdge", type=int, default=1600)
        image_format = request.args.get("format", default="png").lower()
        if page_number < 1:
            return "ページ番号が不正です。", 400
        if long_edge < 500 or long_edge > 6000:
            return "longEdgeは500〜6000で指定してください。", 400
        if image_format not in {"png", "jpeg"}:
            return "formatはpngまたはjpegで指定してください。", 400

        pdf_path = get_project_pdf_path(project_id)
        project_cache = get_project_cache_dir(project_id)
        if pdf_path is None or project_cache is None:
            return "PDFが見つかりません。", 404

        suffix = "jpg" if image_format == "jpeg" else "png"
        cache_path = project_cache / f"page-{page_number}-{long_edge}.{suffix}"
        try:
            image_path, cache_hit = render_cached(
                pdf_path, cache_path, page_number, long_edge, image_format
            )
            response = send_file(
                image_path,
                mimetype="image/jpeg" if image_format == "jpeg" else "image/png",
                max_age=31536000,
            )
            response.headers["X-Render-Cache"] = "HIT" if cache_hit else "MISS"
            return response
        except ValueError as exc:
            return str(exc), 400
        except Exception as exc:
            return f"PDFiumレンダリングに失敗しました: {exc}", 500

    @blueprint.post("/projects/<int:project_id>/ocr-page")
    def ocr_project_page(project_id):
        body = request.get_json(silent=True) or {}
        page_number = body.get("pageNumber")
        if not isinstance(page_number, int) or page_number < 1:
            return jsonify({"error": "ページ番号が不正です。"}), 400

        pdf_path = get_project_pdf_path(project_id)
        project_cache = get_project_cache_dir(project_id)
        if pdf_path is None or project_cache is None:
            return jsonify({"error": "PDFが見つかりません。"}), 404

        cache_path = project_cache / f"page-{page_number}-6000.jpg"
        try:
            image_path, cache_hit = render_cached(
                pdf_path, cache_path, page_number, 6000, "jpeg"
            )
            result = vision_ocr(image_path, page_number, Path(__file__).resolve().parent)
            result["renderCache"] = "hit" if cache_hit else "miss"
            return jsonify(result)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502

    @blueprint.get("/projects/<int:project_id>/number-map")
    def get_project_number_map(project_id):
        page_number = request.args.get("page", type=int)
        if page_number is None or page_number < 1:
            return jsonify({"error": "ページ番号が不正です。"}), 400

        drawing_key = project_drawing_key(project_id)
        with connect() as connection:
            if connection.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
                return jsonify({"error": "工事が見つかりません。"}), 404
            rows = connection.execute(
                """
                SELECT number_text, source, x, y, width, height, saved_at
                FROM number_map
                WHERE drawing_key = ? AND page_number = ?
                ORDER BY item_order
                """,
                (drawing_key, page_number),
            ).fetchall()

        return jsonify({
            "drawingKey": drawing_key,
            "pageNumber": page_number,
            "saved": bool(rows),
            "savedAt": rows[0]["saved_at"] if rows else None,
            "candidates": [
                {
                    "number": row["number_text"],
                    "source": row["source"],
                    "bbox": {
                        "x": row["x"], "y": row["y"],
                        "w": row["width"], "h": row["height"],
                    },
                }
                for row in rows
            ],
        })

    @blueprint.post("/projects/<int:project_id>/number-map")
    def save_project_number_map(project_id):
        body = request.get_json(silent=True) or {}
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

        drawing_key = project_drawing_key(project_id)
        saved_at = datetime.now(timezone.utc).isoformat()
        with connect() as connection:
            if connection.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
                return jsonify({"error": "工事が見つかりません。"}), 404
            connection.execute(
                "DELETE FROM number_map WHERE drawing_key = ? AND page_number = ?",
                (drawing_key, page_number),
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
                        drawing_key, page_number, index,
                        candidate["number"], candidate["source"],
                        candidate["bbox"]["x"], candidate["bbox"]["y"],
                        candidate["bbox"]["w"], candidate["bbox"]["h"],
                        saved_at,
                    )
                    for index, candidate in enumerate(candidates)
                ],
            )

        return jsonify({
            "drawingKey": drawing_key,
            "pageNumber": page_number,
            "savedAt": saved_at,
            "count": len(candidates),
        })

    @blueprint.get("/pdfs/<path:stored_name>")
    def get_project_pdf(stored_name):
        if not stored_name.endswith(".pdf") or "/" in stored_name or "\\" in stored_name:
            return jsonify({"error": "PDFが見つかりません。"}), 404
        return send_from_directory(upload_dir, stored_name, mimetype="application/pdf")

    return blueprint
