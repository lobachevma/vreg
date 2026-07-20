from functools import wraps

from flask import flash, redirect, session, url_for

from app.models import User


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Необходимо войти в систему.", "warning")
            return redirect(url_for("main.login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Необходимо войти в систему.", "warning")
            return redirect(url_for("main.login"))

        user = User.query.get(session["user_id"])
        if not user or not user.is_admin:
            flash("Доступ запрещён.", "danger")
            return redirect(url_for("main.recorders"))
        return view(*args, **kwargs)

    return wrapped
