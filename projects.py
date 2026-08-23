import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request, send_from_directory


def create_projects_blueprint(db_path: Path, data_dir: Path):
    blueprint = Blueprint("projects", __name__)
    upload_dir = data_dir / "pdfs"

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

    def get_project_row(project_id):
        with connect() as connection:
            return connection.execute(
                """
                SELECT id, project_name, original_pdf_name, stored_pdf_name, created_at
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()

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

    @blueprint.get("/projects/<int:project_id>/entry")
    def project_entry(project_id):
        row = get_project_row(project_id)
        if row is None:
            return "工事が見つかりません。", 404

        return render_template(
            "project_entry.html",
            project_id=row["id"],
            project_name=row["project_name"],
            pdf_name=row["original_pdf_name"],
            pdf_url=f"../../pdfs/{row['stored_pdf_name']}",
        )

    @blueprint.get("/pdfs/<path:stored_name>")
    def get_project_pdf(stored_name):
        if not stored_name.endswith(".pdf") or "/" in stored_name or "\\" in stored_name:
            return jsonify({"error": "PDFが見つかりません。"}), 404
        return send_from_directory(upload_dir, stored_name, mimetype="application/pdf")

    return blueprint
