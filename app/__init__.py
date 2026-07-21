import os
from datetime import datetime, timezone

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    app.config["SESSION_IDLE_TIMEOUT_SECONDS"] = 300
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        "postgresql://vreg:vreg@db:5432/vreg",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    @app.before_request
    def refresh_session_state():
        from flask import flash, redirect, request, session, url_for

        user_id = session.get("user_id")
        if not user_id:
            return

        last_activity = session.get("last_activity")
        now = datetime.now(timezone.utc).timestamp()
        timeout = app.config["SESSION_IDLE_TIMEOUT_SECONDS"]

        if last_activity is not None and now - float(last_activity) > timeout:
            session.clear()
            flash("Сеанс завершён из-за бездействия.", "info")
            return redirect(url_for("main.login"))

        from app.models import User

        user = User.query.get(user_id)
        if user:
            session["is_admin"] = user.is_admin
            session["last_activity"] = now
        else:
            session.clear()
            flash("Сеанс завершён.", "info")
            return redirect(url_for("main.login"))

    from app.routes import bp
    from app.admin import bp as admin_bp

    app.register_blueprint(bp)
    app.register_blueprint(admin_bp)

    return app
