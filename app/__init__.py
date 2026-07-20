import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        "postgresql://vreg:vreg@db:5432/vreg",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    @app.before_request
    def refresh_session_role():
        from flask import session

        user_id = session.get("user_id")
        if not user_id:
            return

        from app.models import User

        user = User.query.get(user_id)
        if user:
            session["is_admin"] = user.is_admin
        else:
            session.clear()

    from app.routes import bp
    from app.admin import bp as admin_bp

    app.register_blueprint(bp)
    app.register_blueprint(admin_bp)

    return app
