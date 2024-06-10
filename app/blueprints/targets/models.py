from app import db
from app.blueprints.forms.models import Form
from app.blueprints.locations.models import Location
from sqlalchemy import CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import backref
from sqlalchemy.ext.mutable import MutableDict


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
    custom_fields = db.Column(MutableDict.as_mutable(JSONB), nullable=True)
    form_uid = db.Column(db.Integer(), db.ForeignKey(Form.form_uid), nullable=False)

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
        form_uid,
        language=None,
        gender=None,
        location_uid=None,
    ):
        self.target_id = target_id
        self.language = language
        self.gender = gender
        self.location_uid = location_uid
        self.form_uid = form_uid

    def to_dict(self):
        result = {
            "target_uid": self.target_uid,
            "target_id": self.target_id,
            "language": self.language,
            "gender": self.gender,
            "location_uid": self.location_uid,
            "form_uid": self.form_uid,
            "custom_fields": self.custom_fields,
        }

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
    final_survey_status = db.Column(db.Integer())
    final_survey_status_label = db.Column(db.String())
    target_assignable = db.Column(db.Boolean())
    webapp_tag_color = db.Column(db.String())
    revisit_sections = db.Column(ARRAY(db.String()))
    scto_fields = db.Column(MutableDict.as_mutable(JSONB), nullable=True)

    __table_args__ = ({"schema": "webapp"},)

    def __init__(
        self,
        target_uid,
        completed_flag,
        refusal_flag,
        num_attempts,
        last_attempt_survey_status,
        last_attempt_survey_status_label,
        final_survey_status,
        final_survey_status_label,
        target_assignable,
        webapp_tag_color,
        revisit_sections,
        scto_fields=None,
    ):
        self.target_uid = target_uid
        self.completed_flag = completed_flag
        self.refusal_flag = refusal_flag
        self.num_attempts = num_attempts
        self.last_attempt_survey_status = last_attempt_survey_status
        self.last_attempt_survey_status_label = last_attempt_survey_status_label
        self.final_survey_status = final_survey_status
        self.final_survey_status_label = final_survey_status_label
        self.target_assignable = target_assignable
        self.webapp_tag_color = webapp_tag_color
        self.revisit_sections = revisit_sections
        if self.scto_fields is None:
            scto_fields = {}
        self.scto_fields = scto_fields

    def to_dict(self):
        result = {
            "target_uid": self.target_uid,
            "completed_flag": self.completed_flag,
            "refusal_flag": self.refusal_flag,
            "num_attempts": self.num_attempts,
            "last_attempt_survey_status": self.last_attempt_survey_status,
            "last_attempt_survey_status_label": self.last_attempt_survey_status_label,
            "final_survey_status": self.final_survey_status,
            "final_survey_status_label": self.final_survey_status_label,
            "target_assignable": self.target_assignable,
            "webapp_tag_color": self.webapp_tag_color,
            "revisit_sections": self.revisit_sections,
            "scto_fields": self.scto_fields,
        }

        return result


class TargetColumnConfig(db.Model):
    """
    SQLAlchemy data model for Target column configuration
    """

    __tablename__ = "target_column_config"

    form_uid = db.Column(db.Integer(), db.ForeignKey(Form.form_uid), nullable=False)
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
