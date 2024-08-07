from sqlalchemy import CheckConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.mutable import MutableDict

from app import db
from app.blueprints.enumerators.models import Enumerator
from app.blueprints.forms.models import Form
from app.blueprints.targets.models import Target
from app.blueprints.users.models import User


class UserTargetMapping(db.Model):
    __tablename__ = "user_target_mapping"

    target_uid = db.Column(
        db.Integer(),
        db.ForeignKey(Target.target_uid),
        primary_key=True,
        nullable=False,
        ondelete="CASCADE",
    )
    user_uid = db.Column(db.Integer, db.ForeignKey(User.user_uid, ondelete="CASCADE"))

    def __init__(self, target_uid, user_uid):
        self.target_uid = target_uid
        self.user_uid = user_uid

    def to_dict(self):
        return {
            "target_uid": self.target_uid,
            "user_uid": self.user_uid,
        }


class UserSurveyorMapping(db.Model):
    __tablename__ = "user_surveyor_mapping"

    form_uid = db.Column(
        db.Integer(), db.ForeignKey(Form.form_uid), nullable=False, ondelete="CASCADE"
    )
    enumerator_uid = db.Column(
        db.Integer(),
        db.ForeignKey(Enumerator.enumerator_uid),
        nullable=False,
        ondelete="CASCADE",
    )
    user_uid = db.Column(db.Integer, db.ForeignKey(User.user_uid, ondelete="CASCADE"))

    __table_args__ = (
        db.PrimaryKeyConstraint("form_uid", "enumerator_uid"),
        {"schema": "webapp"},
    )

    def __init__(self, form_uid, enumerator_uid, user_uid):
        self.form_uid = form_uid
        self.enumerator_uid = enumerator_uid
        self.user_uid = user_uid

    def to_dict(self):
        return {
            "form_uid": self.form_uid,
            "enumerator_uid": self.enumerator_uid,
            "user_uid": self.user_uid,
        }


class UserMappingConfig(db.Model):
    __tablename__ = "user_mapping_config"

    form_uid = db.Column(
        db.Integer(), db.ForeignKey(Form.form_uid), nullable=False, ondelete="CASCADE"
    )

    mapping_type = db.Column(
        db.String(),
        CheckConstraint(
            "mapping_type IN ('target', 'surveyor')",
            name="ck_user_mapping_config_mapping_type",
        ),
    )

    mapping_values = db.Column(MutableDict.as_mutable(JSONB), nullable=False)
    mapped_to = db.Column(MutableDict.as_mutable(JSONB), nullable=False)

    __table_args__ = (
        db.PrimaryKeyConstraint("form_uid", "mapping_type", "mapping_values"),
        {"schema": "webapp"},
    )

    def __init__(self, form_uid, mapping_type, mapping_values, mapped_to):
        self.form_uid = form_uid
        self.mapping_type = mapping_type
        self.mapping_values = mapping_values
        self.mapped_to = mapped_to

    def to_dict(self):
        return {
            "form_uid": self.form_uid,
            "mapping_type": self.mapping_type,
            "mapping_values": self.mapping_values,
            "mapped_to": self.mapped_to,
        }
