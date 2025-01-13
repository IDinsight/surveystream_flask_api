from app import db
from sqlalchemy.dialects.postgresql import JSONB
from app.blueprints.surveys.models import Survey
from sqlalchemy.orm import backref
from sqlalchemy import CheckConstraint


class Form(db.Model):
    """
    SQLAlchemy data model for Form
    This table contains information about the forms
    Forms can be of different types depending on how they are used on the survey
    Parent forms are the main forms posed to respondents
    DQ forms are used to enter data quality information related to a given parent form
    """

    __tablename__ = "forms"

    __table_args__ = (
        db.UniqueConstraint(
            "survey_uid",
            "scto_form_id",
            name="_forms_survey_uid_scto_form_id_uc",
        ),
        db.UniqueConstraint(
            "survey_uid", "form_name", name="_forms_survey_uid_form_name_uc"
        ),
        {
            "schema": "webapp",
        },
    )

    form_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    survey_uid = db.Column(
        db.Integer(),
        db.ForeignKey(Survey.survey_uid, ondelete="CASCADE"),
        nullable=False,
    )
    form_type = db.Column(
        db.String(),
        CheckConstraint(
            "form_type IN ('parent', 'dq', 'admin')",
            name="ck_forms_form_type",
        ),
        nullable=False,
    )
    dq_form_type = db.Column(
        db.String(),
        CheckConstraint(
            "dq_form_type IN ('audioaudit','spotcheck','backcheck')",
            name="ck_forms_dq_form_type",
        ),
        nullable=True,
    )
    admin_form_type = db.Column(
        db.String(),
        CheckConstraint(
            "admin_form_type IN ('bikelog', 'account_details', 'other')",
            name="ck_forms_admin_form_type",
        ),
        nullable=True,
    )
    parent_form_uid = db.Column(
        db.Integer(),
        db.ForeignKey(form_uid, ondelete="CASCADE"),
        nullable=True,
    )
    scto_form_id = db.Column(db.String(), nullable=False)
    form_name = db.Column(db.String(), nullable=False)
    tz_name = db.Column(db.String())
    scto_server_name = db.Column(db.String())
    encryption_key_shared = db.Column(db.Boolean())
    server_access_role_granted = db.Column(db.Boolean())
    server_access_allowed = db.Column(db.Boolean())
    last_ingested_at = db.Column(db.DateTime(), nullable=True)
    surveys = db.relationship(Survey, backref=backref("forms", passive_deletes=True))

    def __init__(
        self,
        survey_uid,
        scto_form_id,
        form_name,
        tz_name,
        scto_server_name,
        encryption_key_shared,
        server_access_role_granted,
        server_access_allowed,
        form_type,
        dq_form_type=None,
        admin_form_type=None,
        parent_form_uid=None,
    ):
        self.survey_uid = survey_uid
        self.scto_form_id = scto_form_id
        self.form_name = form_name
        self.tz_name = tz_name
        self.scto_server_name = scto_server_name
        self.encryption_key_shared = encryption_key_shared
        self.server_access_role_granted = server_access_role_granted
        self.server_access_allowed = server_access_allowed
        self.form_type = form_type
        self.dq_form_type = dq_form_type
        self.admin_form_type = admin_form_type
        self.parent_form_uid = parent_form_uid

    def to_dict(self):
        return {
            "form_uid": self.form_uid,
            "survey_uid": self.survey_uid,
            "scto_form_id": self.scto_form_id,
            "form_name": self.form_name,
            "form_type": self.form_type,
            "dq_form_type": self.dq_form_type,
            "admin_form_type": self.admin_form_type,
            "parent_form_uid": self.parent_form_uid,
            "tz_name": self.tz_name,
            "scto_server_name": self.scto_server_name,
            "encryption_key_shared": self.encryption_key_shared,
            "server_access_role_granted": self.server_access_role_granted,
            "server_access_allowed": self.server_access_allowed,
            "last_ingested_at": self.last_ingested_at,
        }


class SCTOFormSettings(db.Model):
    """
    SQLAlchemy data model for SurveyCTO Form Settings
    This table contains top-level metadata about the form
    """

    __tablename__ = "scto_form_settings"

    __table_args__ = (
        {
            "schema": "webapp",
        },
    )

    form_uid = db.Column(
        db.Integer(),
        db.ForeignKey(Form.form_uid, ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    form_title = db.Column(db.String())
    version = db.Column(db.String(), nullable=False)
    public_key = db.Column(db.String())
    submission_url = db.Column(db.String())
    default_language = db.Column(db.String())
    forms = db.relationship(
        Form, backref=backref("scto_form_settings", passive_deletes=True)
    )

    def __init__(
        self,
        form_uid,
        form_title,
        version,
        public_key,
        submission_url,
        default_language,
    ):
        self.form_uid = form_uid
        self.form_title = form_title
        self.version = version
        self.public_key = public_key
        self.submission_url = submission_url
        self.default_language = default_language

    def to_dict(self):
        return {
            "form_uid": self.form_uid,
            "form_title": self.form_title,
            "version": self.version,
            "public_key": self.public_key,
            "submission_url": self.submission_url,
            "default_language": self.default_language,
        }


class SCTOQuestionMapping(db.Model):
    """
    SQLAlchemy data model for SurveyCTO Question Mapping
    This table contains information about the questions
    in the SurveyCTO form that correspond to required fields
    for various functionalities of the SurveyStream application
    """

    __tablename__ = "scto_question_mapping"

    __table_args__ = (
        {
            "schema": "webapp",
        },
    )

    form_uid = db.Column(
        db.Integer(),
        db.ForeignKey(Form.form_uid, ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    survey_status = db.Column(db.String())
    revisit_section = db.Column(db.String())
    target_id = db.Column(db.String())
    enumerator_id = db.Column(db.String(), nullable=False)
    dq_enumerator_id = db.Column(db.String())
    locations = db.Column(JSONB)
    forms = db.relationship(
        Form, backref=backref("scto_question_mapping", passive_deletes=True)
    )

    def __init__(
        self,
        form_uid,
        survey_status,
        revisit_section,
        target_id,
        enumerator_id,
        dq_enumerator_id,
        locations,
    ):
        self.form_uid = form_uid
        self.survey_status = survey_status
        self.revisit_section = revisit_section
        self.target_id = target_id
        self.enumerator_id = enumerator_id
        self.dq_enumerator_id = dq_enumerator_id
        self.locations = locations

    def to_dict(self):
        return {
            "form_uid": self.form_uid,
            "survey_status": self.survey_status,
            "revisit_section": self.revisit_section,
            "target_id": self.target_id,
            "enumerator_id": self.enumerator_id,
            "dq_enumerator_id": self.dq_enumerator_id,
            "locations": self.locations,
        }


class SCTOChoiceList(db.Model):
    """
    SQLAlchemy data model for storing scto choice lists
    """

    __tablename__ = "scto_form_choice_lists"

    __table_args__ = (
        db.UniqueConstraint(
            "form_uid",
            "list_name",
        ),
        {
            "schema": "webapp",
        },
    )

    list_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    form_uid = db.Column(
        db.Integer(),
        db.ForeignKey(Form.form_uid, ondelete="CASCADE"),
        nullable=False,
    )
    list_name = db.Column(db.String(), nullable=False)
    forms = db.relationship(
        Form, backref=backref("scto_form_choice_lists", passive_deletes=True)
    )

    def __init__(self, form_uid, list_name):
        self.form_uid = form_uid
        self.list_name = list_name

    def to_dict(self):
        return {
            "list_uid": self.list_uid,
            "form_uid": self.form_uid,
            "list_name": self.list_name,
        }


class SCTOChoiceLabel(db.Model):
    """
    SQLAlchemy data model for storing scto choice labels in
    all defined languages. This table contains information about
    the variables defined in the SurveyCTO form
    """

    __tablename__ = "scto_form_choice_labels"

    __table_args__ = (
        db.PrimaryKeyConstraint(
            "list_uid",
            "choice_value",
            "language",
        ),
        {
            "schema": "webapp",
        },
    )
    list_uid = db.Column(
        db.Integer(),
        db.ForeignKey(SCTOChoiceList.list_uid, ondelete="CASCADE"),
        nullable=False,
    )
    choice_value = db.Column(db.String(), nullable=False)
    language = db.Column(db.String(), nullable=False)
    label = db.Column(db.String(), nullable=False)
    choice_lists = db.relationship(
        SCTOChoiceList, backref=backref("scto_form_choice_labels", passive_deletes=True)
    )

    def __init__(
        self,
        list_uid,
        choice_value,
        language,
        label,
    ):
        self.list_uid = list_uid
        self.choice_value = choice_value
        self.language = language
        self.label = label

    def to_dict(self):
        return {
            "list_uid": self.list_uid,
            "choice_value": self.choice_value,
            "language": self.language,
            "label": self.label,
        }


class SCTOQuestion(db.Model):
    """
    SQLAlchemy data model for storing scto questions
    This table contains information about the variables
    defined in the SurveyCTO form
    """

    __tablename__ = "scto_form_questions"

    __table_args__ = (
        {
            "schema": "webapp",
        },
    )
    question_uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    form_uid = db.Column(
        db.Integer(),
        db.ForeignKey(Form.form_uid, ondelete="CASCADE"),
        nullable=False,
    )
    question_name = db.Column(db.String(), nullable=False)
    question_type = db.Column(db.String(), nullable=False)
    list_uid = db.Column(db.Integer(), db.ForeignKey(SCTOChoiceList.list_uid))
    is_repeat_group = db.Column(db.Boolean(), nullable=False)
    is_required = db.Column(db.Boolean(), default=False)
    forms = db.relationship(
        Form, backref=backref("scto_form_questions", passive_deletes=True)
    )

    def __init__(
        self,
        form_uid,
        question_name,
        question_type,
        list_uid,
        is_repeat_group,
        is_required,
    ):
        self.form_uid = form_uid
        self.question_name = question_name
        self.question_type = question_type
        self.list_uid = list_uid
        self.is_repeat_group = is_repeat_group
        self.is_required = is_required

    def to_dict(self):
        return {
            "question_uid": self.question_uid,
            "form_uid": self.form_uid,
            "question_name": self.question_name,
            "question_type": self.question_type,
            "list_uid": self.list_uid,
            "is_repeat_group": self.is_repeat_group,
            "is_required": self.is_required,
        }


class SCTOQuestionLabel(db.Model):
    """
    SQLAlchemy data model for storing scto questions labels in
    all defined languages. This table contains information about
    the variables defined in the SurveyCTO form
    """

    __tablename__ = "scto_form_question_labels"

    __table_args__ = (
        db.PrimaryKeyConstraint(
            "question_uid",
            "language",
        ),
        {
            "schema": "webapp",
        },
    )

    question_uid = db.Column(
        db.Integer(),
        db.ForeignKey(SCTOQuestion.question_uid, ondelete="CASCADE"),
        nullable=False,
    )
    language = db.Column(db.String(), nullable=False)
    label = db.Column(db.String())
    questions = db.relationship(
        SCTOQuestion, backref=backref("scto_form_question_labels", passive_deletes=True)
    )

    def __init__(
        self,
        question_uid,
        language,
        label,
    ):
        self.question_uid = question_uid
        self.language = language
        self.label = label

    def to_dict(self):
        return {
            "question_uid": self.question_uid,
            "language": self.language,
            "label": self.label,
        }
