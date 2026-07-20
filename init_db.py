from app import create_app, db
from app.models import Building, Recorder, RecorderComment, User
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
    db.session.commit()

    admin = User.query.filter_by(username="admin").first()
    if admin:
        admin.is_admin = True
        db.session.commit()
    else:
        admin = User(username="admin", is_admin=True)
        admin.set_password(os.environ.get("ADMIN_PASSWORD", "qpKE4zzhmf"))
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

    db.session.commit()

    print("Database ready.")
