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
from datetime import date, datetime, timedelta, timezone
import ipaddress
import subprocess
from zoneinfo import ZoneInfo
from sqlalchemy import func

from app import db
from app.auth import admin_required, login_required
from app.models import (
    INSPECTION_FRESH_DAYS,
    Building,
    Hdd,
    Recorder,
    RecorderComment,
    RecorderModel,
    User,
)
from app.system_settings import get_availability_ping_count

bp = Blueprint("main", __name__)

CAMERA_CAPACITY_OPTIONS = (4, 8, 16, 24, 32)

RECORDER_LIST_QUERY_KEYS = (
    "address",
    "device",
    "building_type",
    "problematic",
    "sort",
    "order",
)


def _recorder_list_query_args(source=None):
    src = request.args if source is None else source
    params = {}
    address = src.get("address", "").strip()
    if address:
        params["address"] = address
    device = src.get("device", "").strip()
    if device:
        params["device"] = device
    building_type = src.get("building_type", "").strip().upper()
    if building_type in {"DOU", "SCHOOL"}:
        params["building_type"] = building_type
    if src.get("problematic") == "on":
        params["problematic"] = "on"
    sort = src.get("sort", "").strip()
    if sort in {"id", "address"}:
        params["sort"] = sort
    order = src.get("order", "").strip()
    if order in {"asc", "desc"}:
        params["order"] = order
    return params


def _recorder_list_query_args_from_request():
    params = _recorder_list_query_args(request.args)
    if request.method == "POST":
        params.update(_recorder_list_query_args(request.form))
    return params


def _redirect_to_recorders(**overrides):
    params = _recorder_list_query_args_from_request()
    params.update(overrides)
    return redirect(url_for("main.recorders", **params))


def _redirect_to_recorder_detail(recorder_id):
    return redirect(
        url_for(
            "main.recorder_detail",
            recorder_id=recorder_id,
            **_recorder_list_query_args_from_request(),
        )
    )


@bp.app_context_processor
def _inject_recorder_list_query():
    return {"recorder_list_query": _recorder_list_query_args_from_request()}


def _problematic_recorders_condition():
    today = datetime.now(ZoneInfo("Europe/Moscow")).date()
    stale_before = today - timedelta(days=INSPECTION_FRESH_DAYS)
    return db.or_(
        Recorder.storage_depth < 30,
        Recorder.available.is_(False),
        Recorder.last_inspection_date.is_(None),
        Recorder.last_inspection_date < stale_before,
    )


def _check_recorder_availability(ip_address):
    if not ip_address:
        return False

    try:
        normalized_ip = str(ipaddress.ip_address(ip_address.strip()))
    except ValueError:
        return False

    ping_count = get_availability_ping_count()

    try:
        result = subprocess.run(
            ["ping", "-c", str(ping_count), "-W", "1", normalized_ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=max(5, ping_count * 2),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False

    return result.returncode == 0


def _get_buildings():
    return Building.query.order_by(Building.address.asc()).all()


def _get_hdds():
    return Hdd.query.order_by(Hdd.name.asc()).all()


def _get_recorder_models():
    return RecorderModel.query.order_by(RecorderModel.name.asc()).all()


def _get_visible_hdd_count(model_name=None, recorder=None):
    if model_name:
        catalog_model = RecorderModel.query.filter_by(name=model_name).first()
        if catalog_model:
            return catalog_model.hdd_count
    if recorder:
        filled = sum(
            1
            for slot in (recorder.hdd1_id, recorder.hdd2_id, recorder.hdd3_id, recorder.hdd4_id)
            if slot
        )
        if filled:
            if filled <= 1:
                return 1
            if filled <= 2:
                return 2
            return 4
    return 2


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


def _recorder_row_group_key(recorder):
    if recorder.building_id is not None:
        return ("building", recorder.building_id)
    return ("address", recorder.address or "")


def _recorder_row_shades(recorders):
    """Map each recorder row to shade 0/1; one building/address = one shade."""
    labels = {}
    for recorder in recorders:
        key = _recorder_row_group_key(recorder)
        if key not in labels:
            labels[key] = (recorder.display_address or "").casefold()

    shade_by_key = {
        key: index % 2 for index, key in enumerate(sorted(labels.keys(), key=labels.get))
    }
    return {
        recorder.id: shade_by_key[_recorder_row_group_key(recorder)]
        for recorder in recorders
    }


@bp.route("/recorders")
@login_required
def recorders():
    sort = request.args.get("sort", "id")
    order = request.args.get("order", "desc")
    selected_address = request.args.get("address", "").strip()
    selected_device = request.args.get("device", "").strip()
    selected_building_type = request.args.get("building_type", "").strip().upper()
    show_problematic = request.args.get("problematic") == "on"

    query = Recorder.query.outerjoin(Building)

    if selected_address:
        query = query.filter(Recorder.address == selected_address)

    if selected_device:
        if selected_device == "__empty__":
            query = query.filter(db.or_(Recorder.model.is_(None), Recorder.model == ""))
        else:
            query = query.filter(Recorder.model == selected_device)

    if selected_building_type in {"DOU", "SCHOOL"}:
        query = query.filter(Building.building_type == selected_building_type)

    if show_problematic:
        query = query.filter(_problematic_recorders_condition())

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
        recorder_row_shades=_recorder_row_shades(items),
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
        selected_building_type=selected_building_type,
        show_problematic=show_problematic,
    )


@bp.route("/recorders/availability-check", methods=["POST"])
@login_required
def recorders_availability_check():
    data = request.get_json(silent=True) or {}
    ids_raw = data.get("recorder_ids")
    if not isinstance(ids_raw, list) or not ids_raw:
        response = jsonify(error="recorder_ids required")
        response.status_code = 400
        return response

    recorder_ids = []
    for raw in ids_raw:
        try:
            recorder_ids.append(int(raw))
        except (TypeError, ValueError):
            continue

    if not recorder_ids:
        response = jsonify(error="recorder_ids required")
        response.status_code = 400
        return response

    recorders = Recorder.query.filter(Recorder.id.in_(recorder_ids)).all()
    results = {}
    for recorder in recorders:
        is_available = _check_recorder_availability(recorder.ip_address)
        recorder.available = is_available
        results[str(recorder.id)] = is_available

    db.session.commit()
    response = jsonify(results=results)
    response.headers["Cache-Control"] = "no-store"
    return response


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
                return _redirect_to_recorder_detail(recorder.id)

            comment_id_raw = request.form.get("comment_id", "").strip()
            try:
                comment_id = int(comment_id_raw)
            except ValueError:
                flash("Некорректный комментарий.", "danger")
                return _redirect_to_recorder_detail(recorder.id)

            comment = RecorderComment.query.filter_by(id=comment_id, recorder_id=recorder.id).first_or_404()
            db.session.delete(comment)
            db.session.commit()
            flash("Комментарий удалён.", "success")
            return _redirect_to_recorder_detail(recorder.id)

        if action == "save_inspection_date":
            raw_date = request.form.get("last_inspection_date", "").strip()
            if raw_date:
                try:
                    recorder.last_inspection_date = date.fromisoformat(raw_date)
                except ValueError:
                    flash("Некорректная дата инспекции.", "danger")
                    return _redirect_to_recorder_detail(recorder.id)
            else:
                recorder.last_inspection_date = None
            db.session.commit()
            flash("Дата последней инспекции сохранена.", "success")
            return _redirect_to_recorder_detail(recorder.id)

        if not comment_text:
            flash("Комментарий не может быть пустым.", "danger")
            return _redirect_to_recorder_detail(recorder.id)

        comment = RecorderComment(
            recorder_id=recorder.id,
            user_id=session["user_id"],
            comment=comment_text,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(comment)
        db.session.commit()
        flash("Комментарий сохранён.", "success")
        return _redirect_to_recorder_detail(recorder.id)

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
    last_inspection_date_input = (
        recorder.last_inspection_date.isoformat() if recorder.last_inspection_date else ""
    )
    return render_template(
        "recorder_detail.html",
        recorder=recorder,
        comments=comments,
        last_inspection_date_input=last_inspection_date_input,
    )


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


@bp.route("/recorders/<int:recorder_id>/availability", methods=["POST"])
@login_required
def recorder_availability_check(recorder_id):
    recorder = Recorder.query.get_or_404(recorder_id)
    is_available = _check_recorder_availability(recorder.ip_address)
    recorder.available = is_available
    db.session.commit()
    response = jsonify(available=is_available)
    response.headers["Cache-Control"] = "no-store"
    return response


def _parse_recorder_form():
    building_id_raw = request.form.get("building_id", "").strip()
    model = request.form.get("model", "").strip()
    camera_capacity_raw = request.form.get("camera_capacity", "").strip()
    camera_count_raw = request.form.get("camera_count", "").strip()
    ip_address = request.form.get("ip_address", "").strip()
    login = request.form.get("login", "").strip()
    password = request.form.get("password", "").strip()
    storage_depth_raw = request.form.get("storage_depth", "").strip()
    recorder_type = request.form.get("recorder_type", "").strip().upper()
    time_sync = request.form.get("time_sync") == "on"
    available = request.form.get("available") == "on"
    hdd1_id_raw = request.form.get("hdd1_id", "").strip()
    hdd2_id_raw = request.form.get("hdd2_id", "").strip()
    hdd3_id_raw = request.form.get("hdd3_id", "").strip()
    hdd4_id_raw = request.form.get("hdd4_id", "").strip()

    form = {
        "building_id": building_id_raw,
        "model": model,
        "camera_capacity": camera_capacity_raw,
        "camera_count": camera_count_raw,
        "ip_address": ip_address,
        "login": login,
        "password": password,
        "storage_depth": storage_depth_raw,
        "recorder_type": recorder_type,
        "time_sync": time_sync,
        "available": available,
        "hdd1_id": hdd1_id_raw,
        "hdd2_id": hdd2_id_raw,
        "hdd3_id": hdd3_id_raw,
        "hdd4_id": hdd4_id_raw,
    }

    errors = []
    building = None
    hdd_ids = {1: None, 2: None, 3: None, 4: None}
    visible_hdd_count = _get_visible_hdd_count(model_name=model)

    try:
        building_id = int(building_id_raw)
        building = Building.query.get(building_id)
        if not building:
            raise ValueError
    except ValueError:
        errors.append("Выберите адрес здания.")

    camera_capacity = None
    camera_count = None
    storage_depth = None

    catalog_model = RecorderModel.query.filter_by(name=model).first() if model else None
    if catalog_model and catalog_model.camera_capacity is not None:
        camera_capacity = catalog_model.camera_capacity
    elif camera_capacity_raw:
        try:
            camera_capacity = int(camera_capacity_raw)
            if camera_capacity not in CAMERA_CAPACITY_OPTIONS:
                raise ValueError
        except ValueError:
            errors.append("Выберите модель из справочника.")
    else:
        errors.append("Выберите модель из справочника.")

    if camera_count_raw:
        try:
            camera_count = int(camera_count_raw)
            if camera_count < 0:
                raise ValueError
        except ValueError:
            errors.append("Количество подключенных камер должно быть неотрицательным числом.")
    else:
        camera_count = 0

    try:
        storage_depth = int(storage_depth_raw)
        if storage_depth < 0:
            raise ValueError
    except ValueError:
        errors.append("Глубина хранения должна быть неотрицательным числом.")

    if catalog_model and catalog_model.recorder_type:
        recorder_type = catalog_model.recorder_type
    elif recorder_type not in {"ANALOG", "IP", "HYBRID"}:
        errors.append("Выберите модель из справочника.")

    camera_count = camera_count if camera_count is not None else 0

    for slot, label in (
        (1, "HDD 1"),
        (2, "HDD 2"),
        (3, "HDD 3"),
        (4, "HDD 4"),
    ):
        raw = request.form.get(f"hdd{slot}_id", "").strip()
        if slot > visible_hdd_count:
            continue
        if not raw:
            continue
        try:
            hdd_id = int(raw)
            if not Hdd.query.get(hdd_id):
                raise ValueError
            hdd_ids[slot] = hdd_id
        except ValueError:
            errors.append(f"Выберите корректный {label}.")

    return (
        form,
        errors,
        building,
        camera_capacity,
        camera_count,
        storage_depth,
        hdd_ids[1],
        hdd_ids[2],
        hdd_ids[3],
        hdd_ids[4],
        available,
    )


@bp.route("/recorders/add", methods=["GET", "POST"])
@admin_required
def add_recorder():
    buildings = _get_buildings()
    hdds = _get_hdds()
    recorder_models = _get_recorder_models()

    if request.method == "POST":
        form, errors, building, camera_capacity, camera_count, storage_depth, hdd1_id, hdd2_id, hdd3_id, hdd4_id, available = _parse_recorder_form()

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "recorder_form.html",
                form=form,
                buildings=buildings,
                hdds=hdds,
                recorder_models=recorder_models,
                visible_hdd_count=_get_visible_hdd_count(model_name=form.get("model")),
                title="Добавить регистратор",
                action=url_for("main.add_recorder"),
            )

        recorder = Recorder(
            building_id=building.id,
            address=building.address,
            model=form["model"],
            camera_capacity=camera_capacity,
            camera_count=camera_count,
            ip_address=form["ip_address"],
            login=form["login"],
            password=form["password"],
            storage_depth=storage_depth,
            recorder_type=form["recorder_type"],
            time_sync=form["time_sync"],
            available=available,
            hdd1_id=hdd1_id,
            hdd2_id=hdd2_id,
            hdd3_id=hdd3_id,
            hdd4_id=hdd4_id,
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
        recorder_models=recorder_models,
        visible_hdd_count=0,
        title="Добавить регистратор",
        action=url_for("main.add_recorder"),
    )


@bp.route("/recorders/<int:recorder_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_recorder(recorder_id):
    recorder = Recorder.query.get_or_404(recorder_id)
    buildings = _get_buildings()
    hdds = _get_hdds()
    recorder_models = _get_recorder_models()

    if request.method == "POST":
        form, errors, building, camera_capacity, camera_count, storage_depth, hdd1_id, hdd2_id, hdd3_id, hdd4_id, available = _parse_recorder_form()

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "recorder_form.html",
                form=form,
                buildings=buildings,
                hdds=hdds,
                recorder_models=recorder_models,
                visible_hdd_count=_get_visible_hdd_count(
                    model_name=form.get("model"),
                    recorder=recorder,
                ),
                title="Редактировать регистратор",
                action=url_for(
                    "main.edit_recorder",
                    recorder_id=recorder.id,
                    **_recorder_list_query_args_from_request(),
                ),
            )

        recorder.building_id = building.id
        recorder.address = building.address
        recorder.model = form["model"]
        recorder.camera_capacity = camera_capacity
        recorder.camera_count = camera_count
        recorder.ip_address = form["ip_address"]
        recorder.login = form["login"]
        recorder.password = form["password"]
        recorder.storage_depth = storage_depth
        recorder.recorder_type = form["recorder_type"]
        recorder.time_sync = form["time_sync"]
        recorder.available = available
        recorder.hdd1_id = hdd1_id
        recorder.hdd2_id = hdd2_id
        recorder.hdd3_id = hdd3_id
        recorder.hdd4_id = hdd4_id
        db.session.commit()
        flash("Данные регистратора обновлены.", "success")
        return _redirect_to_recorders()

    list_query = _recorder_list_query_args_from_request()
    return render_template(
        "recorder_form.html",
        form={
            "building_id": recorder.building_id or "",
            "model": recorder.model,
            "camera_capacity": recorder.camera_capacity or "",
            "camera_count": recorder.camera_count,
            "ip_address": recorder.ip_address,
            "login": recorder.login,
            "password": recorder.password,
            "storage_depth": recorder.storage_depth,
            "recorder_type": recorder.recorder_type,
            "time_sync": recorder.time_sync,
            "available": recorder.available,
            "hdd1_id": recorder.hdd1_id or "",
            "hdd2_id": recorder.hdd2_id or "",
            "hdd3_id": recorder.hdd3_id or "",
            "hdd4_id": recorder.hdd4_id or "",
        },
        buildings=buildings,
        hdds=hdds,
        recorder_models=recorder_models,
        visible_hdd_count=_get_visible_hdd_count(
            model_name=recorder.model,
            recorder=recorder,
        ),
        selected_recorder_model_id=next(
            (item.id for item in recorder_models if item.name == recorder.model),
            "",
        ),
        title="Редактировать регистратор",
        action=url_for("main.edit_recorder", recorder_id=recorder.id, **list_query),
    )


@bp.route("/recorders/<int:recorder_id>/delete", methods=["POST"])
@admin_required
def delete_recorder(recorder_id):
    recorder = Recorder.query.get_or_404(recorder_id)
    db.session.delete(recorder)
    db.session.commit()
    flash("Регистратор удалён.", "success")
    return _redirect_to_recorders()
