import sqlite3
from pathlib import Path

from flask import Blueprint, jsonify, make_response, render_template


def create_dashboard_blueprint(db_path: Path):
    blueprint = Blueprint("dashboard", __name__)

    def connect():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def table_exists(connection, table_name):
        return connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone() is not None

    def empty_payload():
        return {
            "totals": {
                "projects": 0,
                "total": 0,
                "untouched": 0,
                "working": 0,
                "done": 0,
                "completionRate": 0,
                "unenteredProjects": 0,
                "completeProjects": 0,
            },
            "projects": [],
        }

    @blueprint.get("/progress-dashboard")
    def progress_dashboard():
        return render_template("progress_dashboard.html")

    @blueprint.get("/progress-dashboard-data")
    def progress_dashboard_data():
        with connect() as connection:
            if not table_exists(connection, "projects"):
                response = jsonify(empty_payload())
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                response.headers["Pragma"] = "no-cache"
                return response

            has_number_map = table_exists(connection, "number_map")
            has_weld_progress = table_exists(connection, "weld_progress")

            if not has_number_map:
                project_rows = connection.execute(
                    """
                    SELECT id, project_name, original_pdf_name, created_at
                    FROM projects
                    ORDER BY id DESC
                    """
                ).fetchall()
                rows = [
                    {
                        "id": row["id"],
                        "project_name": row["project_name"],
                        "original_pdf_name": row["original_pdf_name"],
                        "created_at": row["created_at"],
                        "total": 0,
                        "untouched": 0,
                        "working": 0,
                        "done": 0,
                        "last_updated_at": None,
                    }
                    for row in project_rows
                ]
            elif not has_weld_progress:
                rows = connection.execute(
                    """
                    SELECT
                        p.id,
                        p.project_name,
                        p.original_pdf_name,
                        p.created_at,
                        COUNT(nm.id) AS total,
                        COUNT(nm.id) AS untouched,
                        0 AS working,
                        0 AS done,
                        NULL AS last_updated_at
                    FROM projects AS p
                    LEFT JOIN number_map AS nm
                      ON nm.drawing_key = ('project:' || p.id)
                    GROUP BY p.id, p.project_name, p.original_pdf_name, p.created_at
                    ORDER BY p.id DESC
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT
                        p.id,
                        p.project_name,
                        p.original_pdf_name,
                        p.created_at,
                        COUNT(nm.id) AS total,
                        SUM(
                            CASE
                                WHEN nm.id IS NOT NULL
                                 AND COALESCE(wp.status, '未着手') NOT IN ('施工中', '完了')
                                THEN 1 ELSE 0
                            END
                        ) AS untouched,
                        SUM(
                            CASE
                                WHEN nm.id IS NOT NULL AND wp.status = '施工中'
                                THEN 1 ELSE 0
                            END
                        ) AS working,
                        SUM(
                            CASE
                                WHEN nm.id IS NOT NULL AND wp.status = '完了'
                                THEN 1 ELSE 0
                            END
                        ) AS done,
                        MAX(wp.updated_at) AS last_updated_at
                    FROM projects AS p
                    LEFT JOIN number_map AS nm
                      ON nm.drawing_key = ('project:' || p.id)
                    LEFT JOIN weld_progress AS wp
                      ON wp.drawing_key = nm.drawing_key
                     AND wp.page_number = nm.page_number
                     AND ABS(wp.position_x - (nm.x + nm.width / 2.0)) < 2
                     AND ABS(wp.position_y - (nm.y + nm.height / 2.0)) < 2
                    GROUP BY p.id, p.project_name, p.original_pdf_name, p.created_at
                    ORDER BY p.id DESC
                    """
                ).fetchall()

        projects = []
        totals = {
            "projects": len(rows),
            "total": 0,
            "untouched": 0,
            "working": 0,
            "done": 0,
            "completionRate": 0,
            "unenteredProjects": 0,
            "completeProjects": 0,
        }

        for row in rows:
            total = int(row["total"] or 0)
            untouched = int(row["untouched"] or 0)
            working = int(row["working"] or 0)
            done = int(row["done"] or 0)

            if total == 0:
                derived_status = "未エントリー"
                totals["unenteredProjects"] += 1
            elif done == total:
                derived_status = "完了"
                totals["completeProjects"] += 1
            elif working > 0 or done > 0:
                derived_status = "施工中"
            else:
                derived_status = "未着手"

            completion_rate = round(done / total * 100, 1) if total else 0

            totals["total"] += total
            totals["untouched"] += untouched
            totals["working"] += working
            totals["done"] += done

            projects.append(
                {
                    "id": row["id"],
                    "projectName": row["project_name"],
                    "pdfName": row["original_pdf_name"],
                    "createdAt": row["created_at"],
                    "total": total,
                    "untouched": untouched,
                    "working": working,
                    "done": done,
                    "completionRate": completion_rate,
                    "lastUpdatedAt": row["last_updated_at"],
                    "status": derived_status,
                    "progressUrl": f"projects/{row['id']}/progress",
                }
            )

        if totals["total"]:
            totals["completionRate"] = round(totals["done"] / totals["total"] * 100, 1)

        response = make_response(jsonify({"totals": totals, "projects": projects}))
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response

    return blueprint
