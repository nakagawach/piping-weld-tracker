import sqlite3
from pathlib import Path

from flask import Blueprint, render_template, request


def create_thumbnail_grid_blueprint(db_path: Path):
    blueprint = Blueprint("thumbnail_grid", __name__)

    @blueprint.get("/projects/<int:project_id>/thumbnails")
    def project_thumbnail_grid(project_id):
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            project = connection.execute(
                "SELECT project_name, original_pdf_name FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        if project is None:
            return "工事が見つかりません。", 404
        source = "progress" if request.args.get("source") == "progress" else "entry"
        current_page = max(1, request.args.get("page", default=1, type=int) or 1)
        return render_template(
            "project_thumbnail_grid_v2.html",
            project_id=project_id,
            project_name=project["project_name"],
            pdf_name=project["original_pdf_name"],
            source=source,
            current_page=current_page,
        )

    return blueprint
