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
    name = db.Column(db.String(), nullable=False)
    email = db.Column(db.String(), nullable=False)
    mobile_primary = db.Column(db.String(), nullable=False)
    language = db.Column(db.String(), nullable=True)
    home_address = db.Column(db.String(), nullable=True)
    gender = db.Column(db.String(), nullable=True)
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
        name,
        email,
        mobile_primary,
        form_uid,
        home_address=None,
        language=None,
        gender=None,
        custom_fields=None,
    ):
        self.enumerator_id = enumerator_id
        self.name = name
        self.email = email
        self.mobile_primary = mobile_primary
        self.home_address = home_address
        self.form_uid = form_uid
        self.language = language
        self.gender = gender
        self.custom_fields = custom_fields

    def to_dict(self, joined_keys=None):
        result = {
            "enumerator_uid": self.enumerator_uid,
            "enumerator_id": self.enumerator_id,
            "name": self.name,
            "email": self.email,
            "mobile_primary": self.mobile_primary,
            "home_address": self.home_address,
            "gender": self.gender,
            "language": self.language,
            "custom_fields": self.custom_fields,
        }

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

class SurveyorStats(db.Model):
    """
    SQLAlchemy data model for SurveyorStats
    This table contains the stats for each surveyor per form
    """

    __tablename__ = "surveyor_stats"

    enumerator_uid = db.Column(
        db.Integer(), db.ForeignKey(Enumerator.enumerator_uid), nullable=False
    )
    form_uid = db.Column(
        db.Integer(), db.ForeignKey(ParentForm.form_uid), nullable=False
    )
    avg_num_submissions_per_day = db.Column(db.Integer())
    avg_num_completed_per_day = db.Column(db.Integer())

    __table_args__ = (
        db.PrimaryKeyConstraint("form_uid", "enumerator_uid"),
        {"schema": "webapp"},
    )

    def __init__(
        self,
        enumerator_uid,
        form_uid,
        avg_num_submissions_per_day,
        avg_num_completed_per_day
    ):
        self.enumerator_uid = enumerator_uid
        self.form_uid = form_uid
        self.avg_num_submissions_per_day = avg_num_submissions_per_day
        self.avg_num_completed_per_day = avg_num_completed_per_day

    def to_dict(self):
        result = {
            "enumerator_uid": self.enumerator_uid,
            "form_uid": self.form_uid,
            "avg_num_submissions_per_day": self.avg_num_submissions_per_day,
            "avg_num_completed_per_day": self.avg_num_completed_per_day,
        }

        return result
    
class EnumeratorColumnConfig(db.Model):
    """
    SQLAlchemy data model for Enumerator column configuration
    """

    __tablename__ = "enumerator_column_config"

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
