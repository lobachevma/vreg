from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Building(db.Model):
    __tablename__ = "buildings"

    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(512), unique=True, nullable=False)
    building_type = db.Column(db.String(16), nullable=False, default="DOU")

    recorders = db.relationship("Recorder", back_populates="building")

    @property
    def display_type(self) -> str:
        return "ДОУ" if self.building_type == "DOU" else "ШКОЛА"


class Hdd(db.Model):
    __tablename__ = "hdds"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(512), unique=True, nullable=False)
    volume = db.Column(db.String(64), nullable=False)


class RecorderModel(db.Model):
    __tablename__ = "recorder_models"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), unique=True, nullable=False)
    camera_capacity = db.Column(db.Integer, nullable=True)
    recorder_type = db.Column(db.String(16), nullable=False, default="")
    hdd_count = db.Column(db.Integer, nullable=False, default=2)

    @property
    def display_recorder_type(self) -> str:
        types = {
            "ANALOG": "Аналоговый",
            "IP": "IP",
            "HYBRID": "Гибридный",
        }
        return types.get(self.recorder_type, "Не задан")


class Recorder(db.Model):
    __tablename__ = "recorders"

    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), nullable=True)
    address = db.Column(db.String(512), nullable=False)
    model = db.Column(db.String(256), nullable=False)
    camera_capacity = db.Column(db.Integer, nullable=True)
    camera_count = db.Column(db.Integer, nullable=False, default=0)
    ip_address = db.Column(db.String(45), nullable=False)
    login = db.Column(db.String(256), nullable=False, default="")
    password = db.Column(db.String(256), nullable=False, default="")
    storage_depth = db.Column(db.Integer, nullable=False, default=0)
    recorder_type = db.Column(db.String(16), nullable=False, default="")
    time_sync = db.Column(db.Boolean, nullable=False, default=False)
    hdd1_id = db.Column(db.Integer, db.ForeignKey("hdds.id"), nullable=True)
    hdd2_id = db.Column(db.Integer, db.ForeignKey("hdds.id"), nullable=True)
    hdd3_id = db.Column(db.Integer, db.ForeignKey("hdds.id"), nullable=True)
    hdd4_id = db.Column(db.Integer, db.ForeignKey("hdds.id"), nullable=True)
    comment = db.Column(db.Text, nullable=False, default="")

    building = db.relationship("Building", back_populates="recorders")
    hdd1 = db.relationship("Hdd", foreign_keys=[hdd1_id])
    hdd2 = db.relationship("Hdd", foreign_keys=[hdd2_id])
    hdd3 = db.relationship("Hdd", foreign_keys=[hdd3_id])
    hdd4 = db.relationship("Hdd", foreign_keys=[hdd4_id])
    comments = db.relationship(
        "RecorderComment",
        back_populates="recorder",
        cascade="all, delete-orphan",
        order_by=lambda: RecorderComment.created_at.desc(),
    )

    @property
    def display_address(self) -> str:
        if self.building:
            return self.building.address
        return self.address

    @property
    def display_recorder_type(self) -> str:
        types = {
            "ANALOG": "Аналоговый",
            "IP": "IP",
            "HYBRID": "Гибридный",
        }
        return types.get(self.recorder_type, "Не задан")

    @property
    def catalog_hdd_count(self) -> int:
        if self.model:
            catalog_model = RecorderModel.query.filter_by(name=self.model).first()
            if catalog_model:
                return catalog_model.hdd_count
        filled = sum(
            1
            for slot_id in (self.hdd1_id, self.hdd2_id, self.hdd3_id, self.hdd4_id)
            if slot_id
        )
        if filled <= 1:
            return 1 if filled else 2
        if filled <= 2:
            return 2
        return 4


class RecorderComment(db.Model):
    __tablename__ = "recorder_comments"

    id = db.Column(db.Integer, primary_key=True)
    recorder_id = db.Column(db.Integer, db.ForeignKey("recorders.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)

    recorder = db.relationship("Recorder", back_populates="comments")
    user = db.relationship("User")


class SystemSetting(db.Model):
    __tablename__ = "system_settings"

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.String(256), nullable=False)
