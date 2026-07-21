from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app import db
from app.auth import admin_required
from app.models import Building, Recorder, User

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@admin_required
def index():
    users_count = User.query.count()
    buildings_count = Building.query.count()
    return render_template(
        "admin/index.html",
        users_count=users_count,
        buildings_count=buildings_count,
    )


@bp.route("/users")
@admin_required
def users():
    items = User.query.order_by(User.username.asc()).all()
    return render_template("admin/users.html", users=items)


@bp.route("/users/add", methods=["POST"])
@admin_required
def add_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    is_admin = request.form.get("is_admin") == "on"

    if not username or not password:
        flash("Укажите логин и пароль.", "danger")
        return redirect(url_for("admin.users"))

    if User.query.filter_by(username=username).first():
        flash("Пользователь с таким логином уже существует.", "danger")
        return redirect(url_for("admin.users"))

    user = User(username=username, is_admin=is_admin)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f"Пользователь «{username}» создан.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.username == "admin":
        flash("Учётную запись admin удалить нельзя.", "danger")
        return redirect(url_for("admin.users"))

    if user.id == session.get("user_id"):
        flash("Нельзя удалить текущего пользователя.", "danger")
        return redirect(url_for("admin.users"))

    if user.is_admin and User.query.filter_by(is_admin=True).count() <= 1:
        flash("Нельзя удалить последнего администратора.", "danger")
        return redirect(url_for("admin.users"))

    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f"Пользователь «{username}» удалён.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/buildings")
@admin_required
def buildings():
    items = Building.query.order_by(Building.address.asc()).all()
    return render_template("admin/buildings.html", buildings=items)


@bp.route("/buildings/add", methods=["POST"])
@admin_required
def add_building():
    address = request.form.get("address", "").strip()
    building_type = request.form.get("building_type", "DOU").strip().upper()

    if not address:
        flash("Укажите адрес здания.", "danger")
        return redirect(url_for("admin.buildings"))

    if building_type not in {"DOU", "SCHOOL"}:
        flash("Выберите тип здания.", "danger")
        return redirect(url_for("admin.buildings"))

    if Building.query.filter_by(address=address).first():
        flash("Такой адрес уже существует.", "danger")
        return redirect(url_for("admin.buildings"))

    building = Building(address=address, building_type=building_type)
    db.session.add(building)
    db.session.commit()
    flash(f"Адрес «{address}» добавлен.", "success")
    return redirect(url_for("admin.buildings"))


@bp.route("/buildings/<int:building_id>/delete", methods=["POST"])
@admin_required
def delete_building(building_id):
    building = Building.query.get_or_404(building_id)

    if building.recorders:
        flash("Нельзя удалить адрес, используемый в регистраторах.", "danger")
        return redirect(url_for("admin.buildings"))

    address = building.address
    db.session.delete(building)
    db.session.commit()
    flash(f"Адрес «{address}» удалён.", "success")
    return redirect(url_for("admin.buildings"))
