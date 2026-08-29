from flask import Flask, jsonify
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from app import app as weld_app
from tests.seed_preview_fixture import seed_preview_fixture


seed_preview_fixture()

root_app = Flask("render_preview_root")


@root_app.get("/")
def preview_root():
    return jsonify({"service": "piping-weld-tracker-render-test", "weld": "/weld/"})


@root_app.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})


application = DispatcherMiddleware(root_app, {"/weld": weld_app})
