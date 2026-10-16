"""Seller Information Finder - Flask application factory."""
from __future__ import annotations

import logging
from datetime import date, datetime

from bson import ObjectId
from flask import Flask, jsonify
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS

from .config import Config
from .errors import register_error_handlers
from .routes import api


class IsoJSONProvider(DefaultJSONProvider):
    """Emit ISO-8601 datetimes and stringify ObjectId values."""

    @staticmethod
    def default(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        return DefaultJSONProvider.default(obj)


def create_app(config_object=Config) -> Flask:
    import os
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'dist'))
    app = Flask(__name__, static_folder=static_dir, static_url_path='/') if os.path.exists(static_dir) else Flask(__name__)
    app.config.from_object(config_object)
    app.json = IsoJSONProvider(app)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Restrict CORS to the configured frontend origins only.
    CORS(
        app,
        resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS", [])}},
        supports_credentials=False,
        allow_headers=["Content-Type", "Authorization", "X-Admin-Token"],
        methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    )

    register_error_handlers(app)
    app.register_blueprint(api)

    _register_root_routes(app)
    _register_security_headers(app)
    _init_database(app)
    return app


def _register_root_routes(app: Flask) -> None:
    @app.get("/")
    def root():
        # serve frontend if built
        import os
        from flask import send_from_directory
        static_dir = app.static_folder
        if static_dir and os.path.exists(os.path.join(static_dir, 'index.html')):
            return send_from_directory(static_dir, 'index.html')
        return jsonify(
            {
                "name": "Seller Information Finder API",
                "version": "1.0.0",
                "docs": "/api/health",
            }
        )


def _register_security_headers(app: Flask) -> None:
    @app.after_request
    def _headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response


def _init_database(app: Flask) -> None:
    """Try to create indexes, but never crash the app if MongoDB is down."""
    if app.config.get("TESTING"):
        return
    try:
        from .schema import ensure_indexes
        ensure_indexes()
    except Exception as exc:  # noqa: BLE001
        app.logger.warning("Could not ensure MongoDB indexes on startup: %s", exc)

    @app.errorhandler(404)
    def spa_fallback(e):
        import os
        from flask import send_from_directory
        static_dir = app.static_folder
        if static_dir and os.path.exists(os.path.join(static_dir, 'index.html')):
            return send_from_directory(static_dir, 'index.html')
        from flask import jsonify
        return jsonify({"error": "not_found"}), 404
