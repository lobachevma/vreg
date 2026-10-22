from app import create_app, db
from app.models import Building, Recorder, RecorderComment, SystemSetting, User
import os

from sqlalchemy import text
from datetime import datetime, timezone

app = create_app()

with app.app_context():
    db.create_all()

    db.session.execute(
        text(
            "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS login VARCHAR(256) NOT NULL DEFAULT ''"
        )
    )
    db.session.execute(
        text(
            "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS password VARCHAR(256) NOT NULL DEFAULT ''"
        )
    )
    db.session.execute(
        text(
            "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS storage_depth INTEGER NOT NULL DEFAULT 0"
        )
    )
    db.session.execute(
        text(
            "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS comment TEXT NOT NULL DEFAULT ''"
        )
    )
    db.session.execute(
        text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE"
        )
    )
    db.session.execute(
        text(
            "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS building_id INTEGER REFERENCES buildings(id)"
        )
    )
    db.session.execute(
        text(
            "ALTER TABLE buildings ADD COLUMN IF NOT EXISTS building_type VARCHAR(16) NOT NULL DEFAULT 'DOU'"
        )
    )
    db.session.execute(
        text(
            "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS time_sync BOOLEAN NOT NULL DEFAULT FALSE"
        )
    )
    db.session.execute(
        text(
            "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS available BOOLEAN NOT NULL DEFAULT TRUE"
        )
    )
    db.session.execute(
        text(
            "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS hdd1_id INTEGER REFERENCES hdds(id)"
        )
    )
    db.session.execute(
        text(
            "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS hdd2_id INTEGER REFERENCES hdds(id)"
        )
    )
    db.session.execute(
        text(
            "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS recorder_type VARCHAR(16) NOT NULL DEFAULT ''"
        )
    )
    db.session.execute(
        text(
            "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS camera_capacity INTEGER"
        )
    )
    db.session.execute(
        text(
            "ALTER TABLE recorder_models ADD COLUMN IF NOT EXISTS camera_capacity INTEGER"
        )
    )
    db.session.execute(
        text(
            "ALTER TABLE recorder_models ADD COLUMN IF NOT EXISTS recorder_type VARCHAR(16) NOT NULL DEFAULT ''"
        )
    )
    db.session.execute(
        text(
            "ALTER TABLE recorder_models ADD COLUMN IF NOT EXISTS hdd_count INTEGER NOT NULL DEFAULT 2"
        )
    )
    db.session.execute(
        text(
            "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS hdd3_id INTEGER REFERENCES hdds(id)"
        )
    )
    db.session.execute(
        text(
            "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS hdd4_id INTEGER REFERENCES hdds(id)"
        )
    )
    db.session.execute(
        text(
            "ALTER TABLE recorders ADD COLUMN IF NOT EXISTS last_inspection_date DATE"
        )
    )
    db.session.commit()

    admin = User.query.filter_by(username="admin").first()
    if admin:
        admin.is_admin = True
        db.session.commit()
    else:
        admin_password = os.environ.get("ADMIN_PASSWORD")
        if not admin_password:
            raise RuntimeError("ADMIN_PASSWORD is required")
        admin = User(username="admin", is_admin=True)
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()
        print("Admin user created.")

    for recorder in Recorder.query.filter(Recorder.building_id.is_(None)).all():
        if not recorder.address:
            continue
        building = Building.query.filter_by(address=recorder.address).first()
        if not building:
            building = Building(address=recorder.address, building_type="DOU")
            db.session.add(building)
            db.session.flush()
        recorder.building_id = building.id
    db.session.query(Building).filter(Building.building_type.is_(None)).update(
        {Building.building_type: "DOU"}
    )

    admin_user = User.query.filter_by(username="admin").first()
    if admin_user:
        for recorder in Recorder.query.filter(Recorder.comment.isnot(None), Recorder.comment != "").all():
            if not RecorderComment.query.filter_by(recorder_id=recorder.id).first():
                db.session.add(
                    RecorderComment(
                        recorder_id=recorder.id,
                        user_id=admin_user.id,
                        comment=recorder.comment,
                        created_at=datetime.now(timezone.utc),
                    )
                )
                recorder.comment = ""

    for recorder in Recorder.query.filter(Recorder.password.is_(None)).all():
        recorder.password = ""

    if not SystemSetting.query.filter_by(key="session_idle_timeout_seconds").first():
        db.session.add(SystemSetting(key="session_idle_timeout_seconds", value="300"))

    if not SystemSetting.query.filter_by(key="recorder_availability_ping_count").first():
        db.session.add(SystemSetting(key="recorder_availability_ping_count", value="3"))

    db.session.commit()

    print("Database ready.")