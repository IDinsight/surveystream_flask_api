from app import db
from app.blueprints.forms.models import ParentForm
from app.blueprints.locations.models import Location
from sqlalchemy import CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import backref


class Enumerator(db.Model):
    """
    SQLAlchemy data model for Enumerator
    This table defines information on enumerators that is constant across surveys and forms
    """

    __tablename__ = "enumerators"

    enumerator_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    enumerator_id = db.Column(db.String(), nullable=False)
    first_name = db.Column(db.String(), nullable=False)
    middle_name = db.Column(db.String(), nullable=True)
    last_name = db.Column(db.String(), nullable=False)
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
        # We need this because we don't have a user-friendly way of enforcing teams to create unique enumerator_id's across forms
        # In the future if we have a global enumerator db we can remove this constraint and the form_uid field and add a unique constraint on enumerator_id
        db.UniqueConstraint(
            "form_uid",
            "enumerator_id",
            name="_enumerators_form_uid_enumerator_id_uc",
        ),
        {"schema": "webapp"},
    )

    def __init__(
        self,
        enumerator_id,
        first_name,
        middle_name,
        last_name,
        email,
        mobile_primary,
        language,
        home_address,
        gender,
        form_uid,
    ):
        self.enumerator_id = enumerator_id
        self.first_name = first_name
        self.middle_name = middle_name
        self.last_name = last_name
        self.email = email
        self.mobile_primary = mobile_primary
        self.language = language
        self.home_address = home_address
        self.gender = gender
        self.form_uid = form_uid

    def to_dict(self, joined_keys=None):
        result = {
            "enumerator_uid": self.enumerator_uid,
            "enumerator_id": self.enumerator_id,
            "first_name": self.first_name,
            "middle_name": self.middle_name,
            "last_name": self.last_name,
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


class SurveyorForm(db.Model):
    """
    SQLAlchemy data model for Surveyor Form
    This table contains information on which forms a surveyor is working
    """

    __tablename__ = "surveyor_forms"

    enumerator_uid = db.Column(
        db.Integer(), db.ForeignKey(Enumerator.enumerator_uid), nullable=False
    )
    form_uid = db.Column(
        db.Integer(), db.ForeignKey(ParentForm.form_uid), nullable=False
    )
    status = db.Column(
        db.String(),
        CheckConstraint(
            "status IN ('Active','Dropout','Temp. Inactive')",
            name="ck_surveyor_forms_status",
        ),
        nullable=False,
        server_default="Active",
    )
    user_uid = db.Column(db.Integer(), default=-1)

    __table_args__ = (
        db.PrimaryKeyConstraint("form_uid", "enumerator_uid"),
        {"schema": "webapp"},
    )


class SurveyorLocation(db.Model):
    """
    SQLAlchemy data model for Surveyor Location
    This table describes the location that a surveyor can do surveys on for a given form
    """

    __tablename__ = "location_surveyor_mapping"

    form_uid = db.Column(
        db.Integer(), db.ForeignKey(ParentForm.form_uid), nullable=False
    )
    enumerator_uid = db.Column(
        db.Integer(), db.ForeignKey(Enumerator.enumerator_uid), nullable=False
    )
    location_uid = db.Column(db.Integer(), db.ForeignKey(Location.location_uid))

    __table_args__ = (
        db.PrimaryKeyConstraint("form_uid", "enumerator_uid", "location_uid"),
        {"schema": "webapp"},
    )


class MonitorForm(db.Model):
    """
    SQLAlchemy data model for Monitor Form
    This table contains information on which forms a monitor is working
    """

    __tablename__ = "monitor_forms"

    enumerator_uid = db.Column(
        db.Integer(), db.ForeignKey(Enumerator.enumerator_uid), nullable=False
    )
    form_uid = db.Column(
        db.Integer(), db.ForeignKey(ParentForm.form_uid), nullable=False
    )
    status = db.Column(
        db.String(),
        CheckConstraint(
            "status IN ('Active','Dropout','Temp. Inactive')",
            name="ck_monitor_forms_status",
        ),
        nullable=False,
        server_default="Active",
    )
    user_uid = db.Column(db.Integer(), default=-1)

    __table_args__ = (
        db.PrimaryKeyConstraint("form_uid", "enumerator_uid"),
        {"schema": "webapp"},
    )


class MonitorLocation(db.Model):
    """
    SQLAlchemy data model for Monitor Location
    This table describes the location that a monitor can do surveys on for a given form
    """

    __tablename__ = "location_monitor_mapping"

    form_uid = db.Column(
        db.Integer(), db.ForeignKey(ParentForm.form_uid), nullable=False
    )
    enumerator_uid = db.Column(
        db.Integer(), db.ForeignKey(Enumerator.enumerator_uid), nullable=False
    )
    location_uid = db.Column(db.Integer(), db.ForeignKey(Location.location_uid))

    __table_args__ = (
        db.PrimaryKeyConstraint("form_uid", "enumerator_uid", "location_uid"),
        {"schema": "webapp"},
    )
