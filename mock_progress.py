from flask import Blueprint, render_template


def create_mock_progress_blueprint():
    blueprint = Blueprint("mock_progress", __name__)

    @blueprint.get("/mock/progress-fixed-layout")
    def progress_fixed_layout():
        return render_template("mock_progress_fixed_layout.html")

    return blueprint
