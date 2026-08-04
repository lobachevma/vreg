from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from app import db
from app.auth import admin_required
from app.models import Building, Hdd, Recorder, RecorderModel, User
from app.system_settings import (
    MAX_SESSION_TIMEOUT_MINUTES,
    MIN_SESSION_TIMEOUT_MINUTES,
    get_session_timeout_seconds,
    set_session_timeout_seconds,
)

bp = Blueprint("admin", __name__, url_prefix="/admin")

CAMERA_CAPACITY_OPTIONS = (4, 8, 16, 24, 32)
HDD_COUNT_OPTIONS = (1, 2, 4)
RECORDER_TYPE_CHOICES = (
    ("ANALOG", "Аналоговый"),
    ("IP", "IP"),
    ("HYBRID", "Гибридный"),
)


def _parse_model_fields(form_data, current_id=None):
    name = form_data.get("name", "").strip()
    camera_capacity_raw = form_data.get("camera_capacity", "").strip()
    recorder_type = form_data.get("recorder_type", "").strip().upper()
    hdd_count_raw = form_data.get("hdd_count", "").strip()

    errors = []
    camera_capacity = None
    hdd_count = None

    if not name:
        errors.append("Укажите название модели.")

    existing = RecorderModel.query.filter_by(name=name).first()
    if existing and (current_id is None or existing.id != current_id):
        errors.append("Такая модель уже существует.")

    if camera_capacity_raw:
        try:
            camera_capacity = int(camera_capacity_raw)
            if camera_capacity not in CAMERA_CAPACITY_OPTIONS:
                raise ValueError
        except ValueError:
            errors.append("Выберите количество камер.")
    else:
        errors.append("Выберите количество камер.")

    if recorder_type not in {value for value, _ in RECORDER_TYPE_CHOICES}:
        errors.append("Выберите тип регистратора.")

    if hdd_count_raw:
        try:
            hdd_count = int(hdd_count_raw)
            if hdd_count not in HDD_COUNT_OPTIONS:
                raise ValueError
        except ValueError:
            errors.append("Выберите количество HDD.")
    else:
        errors.append("Выберите количество HDD.")

    return name, camera_capacity, recorder_type, hdd_count, errors


@bp.route("/")
@admin_required
def index():
    users_count = User.query.count()
    buildings_count = Building.query.count()
    hdd_count = Hdd.query.count()
    models_count = RecorderModel.query.count()
    return render_template(
        "admin/index.html",
        users_count=users_count,
        buildings_count=buildings_count,
        hdd_count=hdd_count,
        models_count=models_count,
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


@bp.route("/hdd")
@admin_required
def hdd():
    items = Hdd.query.order_by(Hdd.name.asc()).all()
    return render_template("admin/hdd.html", hdds=items)


@bp.route("/hdd/add", methods=["POST"])
@admin_required
def add_hdd():
    name = request.form.get("name", "").strip()
    volume = request.form.get("volume", "").strip()

    if not name:
        flash("Укажите название HDD.", "danger")
        return redirect(url_for("admin.hdd"))

    if not volume:
        flash("Укажите объём HDD.", "danger")
        return redirect(url_for("admin.hdd"))

    if Hdd.query.filter_by(name=name).first():
        flash("HDD с таким названием уже существует.", "danger")
        return redirect(url_for("admin.hdd"))

    item = Hdd(name=name, volume=volume)
    db.session.add(item)
    db.session.commit()
    flash(f"HDD «{name}» добавлен.", "success")
    return redirect(url_for("admin.hdd"))


@bp.route("/hdd/<int:hdd_id>/delete", methods=["POST"])
@admin_required
def delete_hdd(hdd_id):
    item = Hdd.query.get_or_404(hdd_id)

    if Recorder.query.filter(
        db.or_(
            Recorder.hdd1_id == item.id,
            Recorder.hdd2_id == item.id,
            Recorder.hdd3_id == item.id,
            Recorder.hdd4_id == item.id,
        )
    ).first():
        flash("Нельзя удалить HDD, используемый в регистраторах.", "danger")
        return redirect(url_for("admin.hdd"))

    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f"HDD «{name}» удалён.", "success")
    return redirect(url_for("admin.hdd"))


@bp.route("/models")
@admin_required
def models():
    items = RecorderModel.query.order_by(RecorderModel.name.asc()).all()
    return render_template(
        "admin/models.html",
        models=items,
        camera_capacity_options=CAMERA_CAPACITY_OPTIONS,
        hdd_count_options=HDD_COUNT_OPTIONS,
        recorder_type_choices=RECORDER_TYPE_CHOICES,
    )


@bp.route("/models/add", methods=["POST"])
@admin_required
def add_model():
    name, camera_capacity, recorder_type, hdd_count, errors = _parse_model_fields(request.form)

    if errors:
        for error in errors:
            flash(error, "danger")
        return redirect(url_for("admin.models"))

    item = RecorderModel(
        name=name,
        camera_capacity=camera_capacity,
        recorder_type=recorder_type,
        hdd_count=hdd_count,
    )
    db.session.add(item)
    db.session.commit()
    flash(f"Модель «{name}» добавлена.", "success")
    return redirect(url_for("admin.models"))


@bp.route("/models/<int:model_id>/edit", methods=["POST"])
@admin_required
def edit_model(model_id):
    item = RecorderModel.query.get_or_404(model_id)
    name, camera_capacity, recorder_type, hdd_count, errors = _parse_model_fields(
        request.form,
        current_id=item.id,
    )

    if errors:
        for error in errors:
            flash(error, "danger")
        return redirect(url_for("admin.models"))

    old_name = item.name
    item.name = name
    item.camera_capacity = camera_capacity
    item.recorder_type = recorder_type
    item.hdd_count = hdd_count
    db.session.commit()

    if old_name != name:
        Recorder.query.filter_by(model=old_name).update({Recorder.model: name})

    flash(f"Модель «{name}» обновлена.", "success")
    return redirect(url_for("admin.models"))


@bp.route("/models/<int:model_id>/delete", methods=["POST"])
@admin_required
def delete_model(model_id):
    item = RecorderModel.query.get_or_404(model_id)

    if Recorder.query.filter_by(model=item.name).first():
        flash("Нельзя удалить модель, используемую в регистраторах.", "danger")
        return redirect(url_for("admin.models"))

    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f"Модель «{name}» удалена.", "success")
    return redirect(url_for("admin.models"))


@bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    if request.method == "POST":
        minutes_raw = request.form.get("timeout_minutes", "").strip()
        try:
            timeout_minutes = int(minutes_raw)
            if not MIN_SESSION_TIMEOUT_MINUTES <= timeout_minutes <= MAX_SESSION_TIMEOUT_MINUTES:
                raise ValueError
        except ValueError:
            flash(
                f"Таймаут должен быть от {MIN_SESSION_TIMEOUT_MINUTES} "
                f"до {MAX_SESSION_TIMEOUT_MINUTES} минут.",
                "danger",
            )
            return redirect(url_for("admin.settings"))

        timeout_seconds = timeout_minutes * 60
        set_session_timeout_seconds(timeout_seconds)
        current_app.config["SESSION_IDLE_TIMEOUT_SECONDS"] = timeout_seconds
        flash("Настройки сохранены.", "success")
        return redirect(url_for("admin.settings"))

    timeout_seconds = get_session_timeout_seconds()
    return render_template(
        "admin/settings.html",
        timeout_seconds=timeout_seconds,
        timeout_minutes=timeout_seconds // 60,
        min_timeout_minutes=MIN_SESSION_TIMEOUT_MINUTES,
        max_timeout_minutes=MAX_SESSION_TIMEOUT_MINUTES,
    )
