"""LifeLink application factory.

Run:  python -m backend.app
"""
import os

from flask import Flask, jsonify, send_from_directory

from .config import Config
from .models.db import close_db, init_db
from .routes.api import api
from .services.validators import ValidationError

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


def create_app(overrides=None):
    app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="/static")
    app.config.from_object(Config)
    app.config.update(overrides or {})
    init_db(app)
    app.teardown_appcontext(close_db)
    app.register_blueprint(api)

    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.errorhandler(ValidationError)
    def on_validation(err):
        return jsonify(error="Validation failed", errors=err.errors), 400

    @app.errorhandler(404)
    def on_missing(_err):
        return jsonify(error="Not found"), 404

    @app.errorhandler(405)
    def on_method(_err):
        return jsonify(error="Method not allowed"), 405

    @app.errorhandler(Exception)
    def on_error(err):
        app.logger.exception("Unhandled error: %s", err)
        return jsonify(error="Internal server error"), 500

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
