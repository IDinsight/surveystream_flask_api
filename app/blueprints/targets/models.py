from app import db
from app.blueprints.forms.models import ParentForm
from app.blueprints.locations.models import Location
from sqlalchemy import CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import backref


class Target(db.Model):
    """
    SQLAlchemy data model for Target
    This table defines information on targets for a given form
    """

    __tablename__ = "enumerators"

    target_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    target_id = db.Column(db.String(), nullable=False)
    name = db.Column(db.String(), nullable=False)
    email = db.Column(db.String(), nullable=False)
    mobile_primary = db.Column(db.String(), nullable=False)
    language = db.Column(db.String(), nullable=True)
    home_address = db.Column(db.String(), nullable=True)
    gender = db.Column(db.String(), nullable=False)
    custom_fields = db.Column(JSONB, nullable=True)
    form_uid = db.Column(
        db.Integer(), db.ForeignKey(ParentForm.form_uid), nullable=False
    )

    __table_args__ = (
        # We need this because we don't have a user-friendly way of enforcing teams to create unique targets_id's across forms
        db.UniqueConstraint(
            "form_uid",
            "target_id",
            name="_targets_form_uid_target_id_uc",
        ),
        {"schema": "webapp"},
    )

    def __init__(
        self,
        target_id,
        name,
        email,
        mobile_primary,
        language,
        home_address,
        gender,
        form_uid,
    ):
        self.target_id = target_id
        self.name = name
        self.email = email
        self.mobile_primary = mobile_primary
        self.language = language
        self.home_address = home_address
        self.gender = gender
        self.form_uid = form_uid

    def to_dict(self, joined_keys=None):
        result = {
            "target_uid": self.target_uid,
            "target_id": self.target_id,
            "name": self.name,
            "email": self.email,
            "mobile_primary": self.mobile_primary,
            "language": self.language,
            "home_address": self.home_address,
            "gender": self.gender,
        }

        if hasattr(self, "custom_fields"):
            result["custom_fields"] = self.custom_fields

        if joined_keys is not None:
            result.update(
                {joined_key: getattr(self, joined_key) for joined_key in joined_keys}
            )

        return result


class TargetColumnConfig(db.Model):
    """
    SQLAlchemy data model for Target column configuration
    """

    __tablename__ = "target_column_config"

    form_uid = db.Column(
        db.Integer(), db.ForeignKey(ParentForm.form_uid), nullable=False
    )
    column_name = db.Column(db.String(), nullable=False)
    column_type = db.Column(
        db.String(),
        CheckConstraint(
            "column_type IN ('personal_details','location','custom_fields')",
            name="ck_enumerator_column_config_column_type",
        ),
        nullable=False,
    )
    bulk_editable = db.Column(db.Boolean(), nullable=False, default=False)

    __table_args__ = (
        db.PrimaryKeyConstraint("form_uid", "column_name"),
        {"schema": "webapp"},
    )
