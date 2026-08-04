SESSION_TIMEOUT_KEY = "session_idle_timeout_seconds"
DEFAULT_SESSION_TIMEOUT_SECONDS = 300
MIN_SESSION_TIMEOUT_MINUTES = 1
MAX_SESSION_TIMEOUT_MINUTES = 480


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
