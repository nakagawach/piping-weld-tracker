import sqlite3
from pathlib import Path

from flask import Blueprint, render_template, request


def create_mock_progress_blueprint(db_path: Path):
    blueprint = Blueprint("mock_progress", __name__)

    def connect():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @blueprint.get("/mock/progress-split")
    def progress_split_mock():
        requested_id = request.args.get("project", type=int)
        with connect() as connection:
            projects = connection.execute(
                """
                SELECT p.id, p.project_name, p.original_pdf_name,
                       EXISTS(
                         SELECT 1 FROM number_map nm
                         WHERE nm.drawing_key = 'project:' || p.id
                       ) AS has_map
                FROM projects p
                ORDER BY p.id DESC
                """
            ).fetchall()

        if not projects:
            return render_template("mock_progress_split.html", project=None, projects=[])

        selected = None
        if requested_id is not None:
            selected = next((row for row in projects if row["id"] == requested_id), None)
        if selected is None:
            selected = next((row for row in projects if row["has_map"]), projects[0])

        return render_template(
            "mock_progress_split.html",
            project={
                "id": selected["id"],
                "name": selected["project_name"],
                "pdfName": selected["original_pdf_name"],
                "hasMap": bool(selected["has_map"]),
            },
            projects=[
                {
                    "id": row["id"],
                    "name": row["project_name"],
                    "pdfName": row["original_pdf_name"],
                    "hasMap": bool(row["has_map"]),
                }
                for row in projects
            ],
        )

    return blueprint
