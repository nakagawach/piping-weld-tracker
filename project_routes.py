from flask import render_template

from projects import create_projects_blueprint


def register_project_routes(app, db_path, data_dir):
    app.register_blueprint(create_projects_blueprint(db_path, data_dir))

    @app.get('/projects-screen')
    def projects_screen():
        return render_template('projects.html')
