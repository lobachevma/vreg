SESSION_TIMEOUT_KEY = "session_idle_timeout_seconds"
DEFAULT_SESSION_TIMEOUT_SECONDS = 300
MIN_SESSION_TIMEOUT_MINUTES = 1
MAX_SESSION_TIMEOUT_MINUTES = 480

PING_COUNT_KEY = "recorder_availability_ping_count"
DEFAULT_PING_COUNT = 3
MIN_PING_COUNT = 1
MAX_PING_COUNT = 10

PROBLEMATIC_FILTER_KEYS = {
    "depth": "problematic_filter_depth",
    "availability": "problematic_filter_availability",
    "time_sync": "problematic_filter_time_sync",
    "inspection_date": "problematic_filter_inspection_date",
}

PROBLEMATIC_FILTER_LABELS = {
    "depth": "Глубина",
    "availability": "Доступность",
    "time_sync": "Синхронизация времени",
    "inspection_date": "Дата проверки",
}

DEFAULT_PROBLEMATIC_FILTER = {
    "depth": True,
    "availability": True,
    "time_sync": False,
    "inspection_date": True,
}


def get_session_timeout_seconds(default=DEFAULT_SESSION_TIMEOUT_SECONDS) -> int:
    from app.models import SystemSetting

    setting = SystemSetting.query.filter_by(key=SESSION_TIMEOUT_KEY).first()
    if not setting:
        return default
    try:
        value = int(setting.value)
    except ValueError:
        return default
    return value if value > 0 else default


def set_session_timeout_seconds(seconds: int) -> None:
    from app import db
    from app.models import SystemSetting

    setting = SystemSetting.query.filter_by(key=SESSION_TIMEOUT_KEY).first()
    if setting:
        setting.value = str(seconds)
    else:
        db.session.add(SystemSetting(key=SESSION_TIMEOUT_KEY, value=str(seconds)))
    db.session.commit()


def apply_session_timeout_to_app(app) -> None:
    try:
        app.config["SESSION_IDLE_TIMEOUT_SECONDS"] = get_session_timeout_seconds()
    except Exception:
        app.config["SESSION_IDLE_TIMEOUT_SECONDS"] = DEFAULT_SESSION_TIMEOUT_SECONDS


def get_availability_ping_count(default=DEFAULT_PING_COUNT) -> int:
    from app.models import SystemSetting

    setting = SystemSetting.query.filter_by(key=PING_COUNT_KEY).first()
    if not setting:
        return default
    try:
        value = int(setting.value)
    except ValueError:
        return default
    if not MIN_PING_COUNT <= value <= MAX_PING_COUNT:
        return default
    return value


def set_availability_ping_count(count: int) -> None:
    from app import db
    from app.models import SystemSetting

    setting = SystemSetting.query.filter_by(key=PING_COUNT_KEY).first()
    if setting:
        setting.value = str(count)
    else:
        db.session.add(SystemSetting(key=PING_COUNT_KEY, value=str(count)))
    db.session.commit()


def _parse_yes_no(value: str, default: bool) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in ("yes", "1", "true", "on"):
        return True
    if normalized in ("no", "0", "false", "off"):
        return False
    return default


def get_problematic_filter_criteria() -> dict:
    from app.models import SystemSetting

    result = dict(DEFAULT_PROBLEMATIC_FILTER)
    for key, setting_key in PROBLEMATIC_FILTER_KEYS.items():
        setting = SystemSetting.query.filter_by(key=setting_key).first()
        if setting:
            result[key] = _parse_yes_no(setting.value, DEFAULT_PROBLEMATIC_FILTER[key])
    return result


def set_problematic_filter_criteria(criteria: dict) -> None:
    from app import db
    from app.models import SystemSetting

    for key, setting_key in PROBLEMATIC_FILTER_KEYS.items():
        enabled = bool(criteria.get(key, False))
        value = "yes" if enabled else "no"
        setting = SystemSetting.query.filter_by(key=setting_key).first()
        if setting:
            setting.value = value
        else:
            db.session.add(SystemSetting(key=setting_key, value=value))
    db.session.commit()
