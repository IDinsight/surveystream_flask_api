from app import db
from app.blueprints.forms.models import ParentForm
from app.blueprints.locations.models import Location
from sqlalchemy import CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import backref


class Target(db.Model):
    """
    SQLAlchemy data model for Target
    This table defines information on targets for a given form
    """

    __tablename__ = "targets"

    target_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    target_id = db.Column(db.String(), nullable=False)
    language = db.Column(db.String(), nullable=True)
    gender = db.Column(db.String(), nullable=True)
    location_uid = db.Column(
        db.Integer(), db.ForeignKey(Location.location_uid), nullable=True
    )
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
        language,
        gender,
        location_uid,
        form_uid,
    ):
        self.target_id = target_id
        self.language = language
        self.gender = gender
        self.location_uid = location_uid
        self.form_uid = form_uid

    def to_dict(self, joined_keys=None):
        result = {
            "target_uid": self.target_uid,
            "target_id": self.target_id,
            "language": self.language,
            "gender": self.gender,
            "location_uid": self.location_uid,
            "form_uid": self.form_uid,
        }

        if hasattr(self, "custom_fields"):
            result["custom_fields"] = self.custom_fields

        if joined_keys is not None:
            result.update(
                {joined_key: getattr(self, joined_key) for joined_key in joined_keys}
            )

        return result


class TargetStatus(db.Model):
    """
    SQLAlchemy data model for TargetStatus
    This table contains the status information for each target
    """

    __tablename__ = "target_status"

    target_uid = db.Column(
        db.Integer(), db.ForeignKey(Target.target_uid), primary_key=True
    )
    completed_flag = db.Column(db.Boolean())
    refusal_flag = db.Column(db.Boolean())
    num_attempts = db.Column(db.Integer())
    last_attempt_survey_status = db.Column(db.Integer())
    last_attempt_survey_status_label = db.Column(db.String())
    target_assignable = db.Column(db.Boolean())
    webapp_tag_color = db.Column(db.String())
    revisit_sections = db.Column(ARRAY(db.String()))

    __table_args__ = ({"schema": "webapp"},)


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
            "column_type IN ('basic_details','location','custom_fields')",
            name="ck_target_column_config_column_type",
        ),
        nullable=False,
    )
    bulk_editable = db.Column(db.Boolean(), nullable=False, default=False)
    contains_pii = db.Column(db.Boolean(), nullable=True)

    __table_args__ = (
        db.PrimaryKeyConstraint("form_uid", "column_name"),
        {"schema": "webapp"},
    )
