from datetime import datetime, timedelta
from flask_app.database import db
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy import Enum
from passlib.hash import pbkdf2_sha256


class User(db.Model):
    """
    SQLAlchemy data model for User
    """

    __tablename__ = "users"

    user_uid = db.Column(db.Integer(), primary_key=True)
    email = db.Column(db.String(), unique=True, nullable=False)
    password_secure = db.Column(db.String(), nullable=False)
    first_name = db.Column(db.String())
    middle_name = db.Column(db.String())
    last_name = db.Column(db.String())
    home_state = db.Column(db.String())
    home_district = db.Column(db.String())
    phone_primary = db.Column(db.String())
    phone_secondary = db.Column(db.String())
    avatar_s3_filekey = db.Column(db.String())
    active = db.Column(db.Boolean(), nullable=False)

    def __init__(self, email, password):
        self.email = email
        self.password_secure = pbkdf2_sha256.hash(password)
        self.active = True
        db.session.add(self)
        db.session.commit()

    def verify_password(self, password):
        return pbkdf2_sha256.verify(password, self.password_secure)

    def change_password(self, new_password):
        self.password_secure = pbkdf2_sha256.hash(new_password)
        db.session.add(self)
        db.session.commit()

    ##############################################################################
    # NECESSARY CALLABLES FOR FLASK-LOGIN
    ##############################################################################

    def is_active(self):
        """
        Return True if the user is active
        """
        return self.active

    def get_id(self):
        """
        Return the uid to satisfy Flask-Login's requirements.
        """
        return self.user_uid

    def is_authenticated(self):
        """
        Return True if the user is authenticated.
        """
        return True

    def is_anonymous(self):
        """
        False, as anonymous users aren't supported.
        """
        return False


class ResetPasswordToken(db.Model):
    """
    SQLAlchemy data model for Reset Password Token
    """

    __tablename__ = "reset_password_tokens"

    reset_uid = db.Column(db.Integer(), primary_key=True)
    user_uid = db.Column(db.Integer(), db.ForeignKey("users.user_uid"), nullable=False)
    secret_token = db.Column(db.String(), nullable=False)
    generated_utc = db.Column(db.DateTime())

    def __init__(self, user_uid, email_token):
        self.user_uid = user_uid
        self.secret_token = pbkdf2_sha256.hash(email_token)
        self.generated_utc = datetime.utcnow()

    def use_token(self, email_token):
        if datetime.utcnow() - self.generated_utc >= timedelta(hours=24):
            return False

        return pbkdf2_sha256.verify(email_token, self.secret_token)


class SamplingFrame(db.Model):
    """
    SQLAlchemy data model for Sampling Frame
    This table defines our unique sampling frames
    """

    __tablename__ = "sampling_frames"

    sampling_frame_uid = db.Column(db.Integer(), primary_key=True)
    survey_name = db.Column(db.String(), unique=True)
    description = db.Column(db.String())


class SamplingFrameGeoLevel(db.Model):
    """
    SQLAlchemy data model for Sampling Frame Geo Level
    This table defines each geographic level within the sampling frame
    """

    __tablename__ = "sampling_frame_geo_levels"

    geo_level_uid = db.Column(db.Integer(), primary_key=True)
    sampling_frame_uid = db.Column(
        db.Integer(), db.ForeignKey("sampling_frames.sampling_frame_uid")
    )
    geo_level_name = db.Column(db.String())
    level = db.Column(db.Integer())

    __table_args__ = (
        db.UniqueConstraint(
            "sampling_frame_uid",
            "geo_level_name",
            name="_sampling_frame_uid_geo_level_name_uc",
        ),
        db.UniqueConstraint(
            "sampling_frame_uid",
            "level",
            name="_sampling_frame_uid_level_uc",
        ),
    )


class Location(db.Model):
    """
    SQLAlchemy data model for Location
    This table contains all the locations within the sampling frame
    """

    __tablename__ = "locations"

    location_uid = db.Column(db.Integer(), primary_key=True)
    sampling_frame_uid = db.Column(
        db.Integer(), db.ForeignKey("sampling_frames.sampling_frame_uid")
    )
    geo_level_uid = db.Column(
        db.Integer(), db.ForeignKey("sampling_frame_geo_levels.geo_level_uid")
    )
    location_id = db.Column(db.String())
    location_name = db.Column(db.String())

    __table_args__ = (
        db.UniqueConstraint(
            "sampling_frame_uid",
            "location_id",
            name="_sampling_frame_uid_location_id_uc",
        ),
    )


class LocationHierarchy(db.Model):
    """
    SQLAlchemy data model for Location Hierarchy
    This table defines the hierarchy (parent-child relationship)
    between the locations in the location table
    """

    __tablename__ = "location_hierarchy"

    location_uid = db.Column(
        db.Integer(), db.ForeignKey("locations.location_uid"), primary_key=True
    )
    parent_location_uid = db.Column(
        db.Integer(), db.ForeignKey("locations.location_uid")
    )


class Survey(db.Model):
    """
    SQLAlchemy data model for Survey
    """

    __tablename__ = "surveys"

    survey_uid = db.Column(db.Integer(), primary_key=True)
    survey_id = db.Column(db.String(), unique=True, nullable=False)
    survey_name = db.Column(db.String(), unique=True, nullable=False)
    sampling_frame_uid = db.Column(
        db.Integer(), db.ForeignKey("sampling_frame.sampling_frame_uid")
    )
    prime_geo_level_uid = db.Column(
        db.Integer(), db.ForeignKey("sampling_frame_geo_levels.geo_level_uid")
    )
    active = db.Column(db.Boolean(), nullable=False)


class AdminForm(db.Model):
    """
    SQLAlchemy data model for Admin Form
    This table contains information about the admin forms within
    the survey like finance forms, bike log forms, etc, which are
    needed to help administer the survey
    """

    __tablename__ = "admin_forms"

    form_uid = db.Column(db.Integer(), primary_key=True)
    scto_form_id = db.Column(db.String(), nullable=False)
    form_name = db.Column(db.String(), nullable=False)
    form_type = db.Column(db.String(), nullable=False)
    planned_start_date = db.Column(db.Date())
    planned_end_date = db.Column(db.Date())
    last_ingested_at = db.Column(db.DateTime(timezone=False))
    tz_name = db.Column(db.String())
    survey_uid = db.Column(db.Integer, db.ForeignKey("surveys.survey_uid"))

    __table_args__ = (
        db.UniqueConstraint(
            "survey_uid", "scto_form_id", name="_admin_forms_survey_uid_scto_form_id_uc"
        ),
        db.UniqueConstraint(
            "survey_uid", "form_name", name="_admin_forms_survey_uid_form_name_uc"
        ),
    )


class ParentForm(db.Model):
    """
    SQLAlchemy data model for Parent Form
    This table contains information about the parent forms
    within the survey, which are the main forms posed to respondents
    """

    __tablename__ = "parent_forms"

    form_uid = db.Column(db.Integer(), primary_key=True)
    scto_form_id = db.Column(db.String(), nullable=False)
    form_name = db.Column(db.String(), nullable=False)
    surveying_method = db.Column(db.String(), nullable=False)
    planned_start_date = db.Column(db.Date())
    planned_end_date = db.Column(db.Date())
    last_ingested_at = db.Column(db.DateTime(timezone=False))
    tz_name = db.Column(db.String())
    survey_uid = db.Column(db.Integer, db.ForeignKey("surveys.survey_uid"))

    __table_args__ = (
        db.UniqueConstraint(
            "survey_uid",
            "scto_form_id",
            name="_parent_forms_survey_uid_scto_form_id_uc",
        ),
        db.UniqueConstraint(
            "survey_uid", "form_name", name="_parent_forms_survey_uid_form_name_uc"
        ),
    )


class ChildForm(db.Model):
    """
    SQLAlchemy data model for Child Form
    This table contains information about the child forms
    (data quality forms, etc) for each parent form
    """

    __tablename__ = "child_forms"

    form_uid = db.Column(db.Integer(), primary_key=True)
    scto_form_id = db.Column(db.String(), nullable=False)
    form_type = db.Column(db.String(), nullable=False)
    parent_form_uid = db.Column(db.Integer, db.ForeignKey("parent_forms.form_uid"))

    __table_args__ = (
        db.UniqueConstraint(
            "parent_form_uid", "scto_form_id", name="_parent_form_uid_scto_form_id_uc"
        ),
    )


class Role(db.Model):
    """
    SQLAlchemy data model for Role
    This tables defines the supervisor roles for a given survey
    """

    __tablename__ = "roles"

    role_uid = db.Column(db.Integer(), primary_key=True)
    survey_uid = db.Column(db.Integer, db.ForeignKey("surveys.survey_uid"))
    role_name = db.Column(db.String())
    level = db.Column(db.Integer())

    __table_args__ = (
        db.UniqueConstraint("survey_uid", "role_name", name="_survey_uid_role_name_uc"),
        db.UniqueConstraint("survey_uid", "level", name="_survey_uid_level_uc"),
    )


class UserHierarchy(db.Model):
    """
    SQLAlchemy data model for User Hierarchy
    This table defines the relationship between a user and their
    supervisor and defines the user’s role on the survey.
    Core team members will be included in this table for the purposes
    of role definition, however they will not be referenced as a
    parent user because of the many-to-many relationship that would result.
    """

    __tablename__ = "user_hierarchy"

    survey_uid = db.Column(
        db.Integer,
        db.ForeignKey("surveys.survey_uid"),
    )
    role_uid = db.Column(db.Integer(), db.ForeignKey("roles.role_uid"))
    user_uid = db.Column(db.Integer(), db.ForeignKey("users.user_uid"))
    parent_user_uid = db.Column(db.Integer(), db.ForeignKey("users.user_uid"))

    __table_args__ = (
        db.PrimaryKeyConstraint("survey_uid", "user_uid", name="user_hierarchy_pk"),
    )


class LocationUserMapping(db.Model):
    """
    SQLAlchemy data model for User Hierarchy
    This table maps FSLn to GL Prime - mapping the
    lowest supervisor level to the geographical level that they oversee.
    """

    __tablename__ = "location_user_mapping"

    survey_uid = db.Column(
        db.Integer,
        db.ForeignKey("surveys.survey_uid"),
    )
    user_uid = db.Column(db.Integer(), db.ForeignKey("users.user_uid"))
    location_uid = db.Column(db.Integer(), db.ForeignKey("locations.location_uid"))

    __table_args__ = (
        db.PrimaryKeyConstraint(
            "survey_uid", "location_uid", name="location_user_mapping_pk"
        ),
    )


class Enumerator(db.Model):
    """
    SQLAlchemy data model for Enumerator
    This table contains information on enumerators
    that is constant across surveys and forms
    """

    __tablename__ = "enumerators"

    enumerator_uid = db.Column(db.Integer(), primary_key=True)
    enumerator_id = db.Column(db.String(), nullable=False, unique=True)
    first_name = db.Column(db.String())
    middle_name = db.Column(db.String())
    last_name = db.Column(db.String())
    gender = db.Column(db.String())
    language = db.Column(db.String())
    phone_primary = db.Column(db.String())
    phone_secondary = db.Column(db.String())
    email = db.Column(db.String())
    home_address = db.Column(JSONB)


class SurveyorForm(db.Model):
    """
    SQLAlchemy data model for Surveyor Form
    This table contains information on which forms a
    surveyor is working
    """

    __tablename__ = "surveyor_forms"

    enumerator_uid = db.Column(
        db.Integer(), db.ForeignKey("enumerators.enumerator_uid"), nullable=False
    )
    form_uid = db.Column(
        db.Integer(), db.ForeignKey("parent_forms.form_uid"), nullable=False
    )
    status = db.Column(
        Enum(
            "Active",
            "Dropout",
            "Temp. Inactive",
            name="enumerator_status",
            create_type=False,
        )
    )
    user_uid = db.Column(db.Integer(), default=-1)

    __table_args__ = (db.PrimaryKeyConstraint("form_uid", "enumerator_uid"),)


class LocationSurveyorMapping(db.Model):
    """
    SQLAlchemy data model for Surveyor Form
    This table describes the location that a
    surveyor can do surveys on for a given form
    """

    __tablename__ = "location_surveyor_mapping"

    form_uid = db.Column(
        db.Integer(), db.ForeignKey("parent_forms.form_uid"), nullable=False
    )
    enumerator_uid = db.Column(
        db.Integer(), db.ForeignKey("enumerators.enumerator_uid"), nullable=False
    )
    location_uid = db.Column(db.Integer(), db.ForeignKey("locations.location_uid"))

    __table_args__ = (
        db.PrimaryKeyConstraint("form_uid", "enumerator_uid", "location_uid"),
    )


class MonitorForm(db.Model):
    """
    SQLAlchemy data model for Monitor Form
    This table contains information on which
    forms a monitor is working
    """

    __tablename__ = "monitor_forms"

    enumerator_uid = db.Column(
        db.Integer(), db.ForeignKey("enumerators.enumerator_uid"), nullable=False
    )
    form_uid = db.Column(
        db.Integer(), db.ForeignKey("child_forms.form_uid"), nullable=False
    )
    status = db.Column(
        Enum(
            "Active",
            "Dropout",
            "Temp. Inactive",
            name="enumerator_status",
            create_type=False,
        )
    )

    __table_args__ = (db.PrimaryKeyConstraint("form_uid", "enumerator_uid"),)


class LocationMonitorMapping(db.Model):
    """
    SQLAlchemy data model for Surveyor Form
    This table describes the location that a
    monitor can do dq forms on for a given form
    """

    __tablename__ = "location_monitor_mapping"

    form_uid = db.Column(
        db.Integer(), db.ForeignKey("child_forms.form_uid"), nullable=False
    )
    enumerator_uid = db.Column(
        db.Integer(), db.ForeignKey("enumerators.enumerator_uid"), nullable=False
    )
    location_uid = db.Column(db.Integer(), db.ForeignKey("locations.location_uid"))

    __table_args__ = (
        db.PrimaryKeyConstraint("form_uid", "enumerator_uid", "location_uid"),
    )


class Target(db.Model):
    """
    SQLAlchemy data model for Target
    This table contains all the survey targets
    """

    __tablename__ = "targets"

    target_uid = db.Column(db.Integer(), primary_key=True)
    target_id = db.Column(db.String(), nullable=False)
    form_uid = db.Column(
        db.Integer(), db.ForeignKey("parent_forms.form_uid"), nullable=False
    )
    respondent_names = db.Column(ARRAY(db.String()))
    respondent_phone_primary = db.Column(db.String())
    respondent_phone_secondary = db.Column(db.String())
    address = db.Column(db.String())
    gps_latitude = db.Column(db.String())
    gps_longitude = db.Column(db.String())
    prime_location_uid = db.Column(
        db.Integer(), db.ForeignKey("locations.location_uid")
    )
    geo_level_n_location_uid = db.Column(
        db.Integer(), db.ForeignKey("locations.location_uid")
    )
    active = db.Column(db.Boolean(), default=True)
    custom_fields = db.Column(JSONB)

    __table_args__ = (
        db.UniqueConstraint("form_uid", "target_id", name="_form_uid_target_id_uc"),
    )


class TargetStatus(db.Model):
    """
    SQLAlchemy data model for TargetStatus
    This table contains the status information for each target
    """

    __tablename__ = "target_status"

    target_uid = db.Column(
        db.Integer(), db.ForeignKey("targets.target_uid"), primary_key=True
    )
    completed_flag = db.Column(db.Boolean())
    refusal_flag = db.Column(db.Boolean())
    num_attempts = db.Column(db.Integer())
    last_attempt_survey_status = db.Column(db.Integer())
    last_attempt_survey_status_label = db.Column(db.String())
    target_assignable = db.Column(db.Boolean())
    webapp_tag_color = db.Column(db.String())
    revisit_sections = db.Column(ARRAY(db.String()))


class SurveyorAssignment(db.Model):
    """
    SQLAlchemy data model for Surveyor Assignment
    Description: This table contains all the assignments for surveyors
    """

    __tablename__ = "surveyor_assignments"

    target_uid = db.Column(
        db.Integer(), db.ForeignKey("targets.target_uid"), primary_key=True
    )
    enumerator_uid = db.Column(
        db.Integer(), db.ForeignKey("enumerators.enumerator_uid"), nullable=False
    )
    user_uid = db.Column(db.Integer(), default=-1)
    to_delete = db.Column(db.Integer(), default=0, nullable=False)


class TableConfig(db.Model):
    """
    SQLAlchemy data model for Table Config
    Description: This table contains the column configurations for the web flask_app tables
    """

    __tablename__ = "webapp_columns"

    form_uid = db.Column(db.Integer(), db.ForeignKey("parent_forms.form_uid"))
    webapp_table_name = db.Column(db.String())
    group_label = db.Column(db.String())
    column_label = db.Column(db.String())
    column_key = db.Column(db.String())
    column_order = db.Column(db.Integer())

    __table_args__ = (
        db.PrimaryKeyConstraint("form_uid", "webapp_table_name", "column_key"),
    )


"""
References
https://amercader.net/blog/beware-of-json-fields-in-sqlalchemy/
"""
