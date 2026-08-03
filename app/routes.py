from flask import (
    Blueprint,
    jsonify,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import func

from app import db
from app.auth import admin_required, login_required
from app.models import Building, Hdd, Recorder, RecorderComment, User

bp = Blueprint("main", __name__)


def _get_buildings():
    return Building.query.order_by(Building.address.asc()).all()


def _get_hdds():
    return Hdd.query.order_by(Hdd.name.asc()).all()


@bp.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("main.recorders"))
    return redirect(url_for("main.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("main.recorders"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["is_admin"] = user.is_admin
            session["last_activity"] = datetime.now(timezone.utc).timestamp()
            flash("Вы успешно вошли в систему.", "success")
            return redirect(url_for("main.recorders"))

        flash("Неверный логин или пароль.", "danger")

    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из системы.", "info")
    return redirect(url_for("main.login"))


@bp.route("/recorders")
@login_required
def recorders():
    sort = request.args.get("sort", "id")
    order = request.args.get("order", "desc")
    selected_address = request.args.get("address", "").strip()
    selected_device = request.args.get("device", "").strip()

    query = Recorder.query.outerjoin(Building)

    if selected_address:
        query = query.filter(Recorder.address == selected_address)

    if selected_device:
        if selected_device == "__empty__":
            query = query.filter(db.or_(Recorder.model.is_(None), Recorder.model == ""))
        else:
            query = query.filter(Recorder.model == selected_device)

    if sort == "address":
        column = Building.address
    else:
        sort = "id"
        column = Recorder.id

    if order == "asc":
        items = query.order_by(column.asc()).all()
    else:
        order = "desc"
        items = query.order_by(column.desc()).all()

    comment_counts = dict(
        db.session.query(
            RecorderComment.recorder_id,
            func.count(RecorderComment.id),
        )
        .group_by(RecorderComment.recorder_id)
        .all()
    )

    return render_template(
        "recorders.html",
        recorders=items,
        comment_counts=comment_counts,
        addresses=[
            row[0]
            for row in Recorder.query.with_entities(Recorder.address)
            .filter(Recorder.address.isnot(None))
            .distinct()
            .order_by(Recorder.address.asc())
            .all()
            if row[0]
        ],
        devices=[
            row[0]
            for row in Recorder.query.with_entities(Recorder.model)
            .filter(Recorder.model.isnot(None), Recorder.model != "")
            .distinct()
            .order_by(Recorder.model.asc())
            .all()
            if row[0]
        ],
        has_empty_device=Recorder.query.filter(
            db.or_(Recorder.model.is_(None), Recorder.model == "")
        ).count()
        > 0,
        sort=sort,
        order=order,
        selected_address=selected_address,
        selected_device=selected_device,
    )


@bp.route("/recorders/<int:recorder_id>", methods=["GET", "POST"])
@login_required
def recorder_detail(recorder_id):
    recorder = Recorder.query.get_or_404(recorder_id)
    if request.method == "POST":
        comment_text = request.form.get("comment", "").strip()
        action = request.form.get("action", "save")

        if action == "delete_comment":
            if not session.get("is_admin"):
                flash("Удалять комментарии может только администратор.", "danger")
                return redirect(url_for("main.recorder_detail", recorder_id=recorder.id))

            comment_id_raw = request.form.get("comment_id", "").strip()
            try:
                comment_id = int(comment_id_raw)
            except ValueError:
                flash("Некорректный комментарий.", "danger")
                return redirect(url_for("main.recorder_detail", recorder_id=recorder.id))

            comment = RecorderComment.query.filter_by(id=comment_id, recorder_id=recorder.id).first_or_404()
            db.session.delete(comment)
            db.session.commit()
            flash("Комментарий удалён.", "success")
            return redirect(url_for("main.recorder_detail", recorder_id=recorder.id))

        if not comment_text:
            flash("Комментарий не может быть пустым.", "danger")
            return redirect(url_for("main.recorder_detail", recorder_id=recorder.id))

        comment = RecorderComment(
            recorder_id=recorder.id,
            user_id=session["user_id"],
            comment=comment_text,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(comment)
        db.session.commit()
        flash("Комментарий сохранён.", "success")
        return redirect(url_for("main.recorder_detail", recorder_id=recorder.id))

    moscow = ZoneInfo("Europe/Moscow")
    comments = [
        {
            "id": comment.id,
            "login": comment.user.username,
            "comment": comment.comment,
            "created_at": comment.created_at.astimezone(moscow).strftime("%d.%m.%Y %H:%M"),
        }
        for comment in recorder.comments
    ]
    return render_template("recorder_detail.html", recorder=recorder, comments=comments)


@bp.route("/recorders/<int:recorder_id>/password")
@login_required
def recorder_password(recorder_id):
    recorder = Recorder.query.get_or_404(recorder_id)
    response = jsonify(password=recorder.password or "")
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.route("/recorders/<int:recorder_id>/time-sync", methods=["POST"])
@login_required
def recorder_time_sync(recorder_id):
    recorder = Recorder.query.get_or_404(recorder_id)
    data = request.get_json(silent=True) or {}
    recorder.time_sync = bool(data.get("time_sync"))
    db.session.commit()
    response = jsonify(time_sync=recorder.time_sync)
    response.headers["Cache-Control"] = "no-store"
    return response


def _parse_recorder_form():
    building_id_raw = request.form.get("building_id", "").strip()
    model = request.form.get("model", "").strip()
    camera_count_raw = request.form.get("camera_count", "").strip()
    ip_address = request.form.get("ip_address", "").strip()
    login = request.form.get("login", "").strip()
    password = request.form.get("password", "").strip()
    storage_depth_raw = request.form.get("storage_depth", "").strip()
    recorder_type = request.form.get("recorder_type", "").strip().upper()
    time_sync = request.form.get("time_sync") == "on"
    hdd1_id_raw = request.form.get("hdd1_id", "").strip()
    hdd2_id_raw = request.form.get("hdd2_id", "").strip()

    form = {
        "building_id": building_id_raw,
        "model": model,
        "camera_count": camera_count_raw,
        "ip_address": ip_address,
        "login": login,
        "password": password,
        "storage_depth": storage_depth_raw,
        "recorder_type": recorder_type,
        "time_sync": time_sync,
        "hdd1_id": hdd1_id_raw,
        "hdd2_id": hdd2_id_raw,
    }

    errors = []
    building = None
    hdd1_id = None
    hdd2_id = None

    try:
        building_id = int(building_id_raw)
        building = Building.query.get(building_id)
        if not building:
            raise ValueError
    except ValueError:
        errors.append("Выберите адрес здания.")

    camera_count = None
    storage_depth = None

    if camera_count_raw:
        try:
            camera_count = int(camera_count_raw)
            if camera_count < 0:
                raise ValueError
        except ValueError:
            errors.append("Количество камер должно быть неотрицательным числом.")
    else:
        camera_count = 0

    try:
        storage_depth = int(storage_depth_raw)
        if storage_depth < 0:
            raise ValueError
    except ValueError:
        errors.append("Глубина хранения должна быть неотрицательным числом.")

    if recorder_type not in {"ANALOG", "IP", "HYBRID"}:
        errors.append("Выберите тип регистратора.")

    camera_count = camera_count if camera_count is not None else 0

    for label, raw in (("HDD 1", hdd1_id_raw), ("HDD 2", hdd2_id_raw)):
        if not raw:
            continue
        try:
            hdd_id = int(raw)
            if not Hdd.query.get(hdd_id):
                raise ValueError
            if label == "HDD 1":
                hdd1_id = hdd_id
            else:
                hdd2_id = hdd_id
        except ValueError:
            errors.append(f"Выберите корректный {label}.")

    return form, errors, building, camera_count, storage_depth, hdd1_id, hdd2_id


@bp.route("/recorders/add", methods=["GET", "POST"])
@admin_required
def add_recorder():
    buildings = _get_buildings()
    hdds = _get_hdds()

    if request.method == "POST":
        form, errors, building, camera_count, storage_depth, hdd1_id, hdd2_id = _parse_recorder_form()

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "recorder_form.html",
                form=form,
                buildings=buildings,
                hdds=hdds,
                title="Добавить регистратор",
                action=url_for("main.add_recorder"),
            )

        recorder = Recorder(
            building_id=building.id,
            address=building.address,
            model=form["model"],
            camera_count=camera_count,
            ip_address=form["ip_address"],
            login=form["login"],
            password=form["password"],
            storage_depth=storage_depth,
            recorder_type=form["recorder_type"],
            time_sync=form["time_sync"],
            hdd1_id=hdd1_id,
            hdd2_id=hdd2_id,
        )
        db.session.add(recorder)
        db.session.commit()
        flash("Регистратор добавлен.", "success")
        return redirect(url_for("main.recorders"))

    if not buildings:
        flash("Сначала добавьте адреса зданий в админ-панели.", "warning")

    return render_template(
        "recorder_form.html",
        form={},
        buildings=buildings,
        hdds=hdds,
        title="Добавить регистратор",
        action=url_for("main.add_recorder"),
    )


@bp.route("/recorders/<int:recorder_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_recorder(recorder_id):
    recorder = Recorder.query.get_or_404(recorder_id)
    buildings = _get_buildings()
    hdds = _get_hdds()

    if request.method == "POST":
        form, errors, building, camera_count, storage_depth, hdd1_id, hdd2_id = _parse_recorder_form()

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "recorder_form.html",
                form=form,
                buildings=buildings,
                hdds=hdds,
                title="Редактировать регистратор",
                action=url_for("main.edit_recorder", recorder_id=recorder.id),
            )

        recorder.building_id = building.id
        recorder.address = building.address
        recorder.model = form["model"]
        recorder.camera_count = camera_count
        recorder.ip_address = form["ip_address"]
        recorder.login = form["login"]
        recorder.password = form["password"]
        recorder.storage_depth = storage_depth
        recorder.recorder_type = form["recorder_type"]
        recorder.time_sync = form["time_sync"]
        recorder.hdd1_id = hdd1_id
        recorder.hdd2_id = hdd2_id
        db.session.commit()
        flash("Данные регистратора обновлены.", "success")
        return redirect(url_for("main.recorders"))

    return render_template(
        "recorder_form.html",
        form={
            "building_id": recorder.building_id or "",
            "model": recorder.model,
            "camera_count": recorder.camera_count,
            "ip_address": recorder.ip_address,
            "login": recorder.login,
            "password": recorder.password,
            "storage_depth": recorder.storage_depth,
            "recorder_type": recorder.recorder_type,
            "time_sync": recorder.time_sync,
            "hdd1_id": recorder.hdd1_id or "",
            "hdd2_id": recorder.hdd2_id or "",
        },
        buildings=buildings,
        hdds=hdds,
        title="Редактировать регистратор",
        action=url_for("main.edit_recorder", recorder_id=recorder.id),
    )


@bp.route("/recorders/<int:recorder_id>/delete", methods=["POST"])
@admin_required
def delete_recorder(recorder_id):
    recorder = Recorder.query.get_or_404(recorder_id)
    db.session.delete(recorder)
    db.session.commit()
    flash("Регистратор удалён.", "success")
    return redirect(url_for("main.recorders"))
