from app import db
from sqlalchemy.dialects.postgresql import JSONB
from app.blueprints.surveys.models import Survey
from sqlalchemy.orm import backref


class ParentForm(db.Model):
    """
    SQLAlchemy data model for Parent Form
    This table contains information about the parent forms
    within the survey, which are the main forms posed to respondents
    """

    __tablename__ = "parent_forms"

    __table_args__ = (
        db.UniqueConstraint(
            "survey_uid",
            "scto_form_id",
            name="_parent_forms_survey_uid_scto_form_id_uc",
        ),
        db.UniqueConstraint(
            "survey_uid", "form_name", name="_parent_forms_survey_uid_form_name_uc"
        ),
        {
            "schema": "config_sandbox",
            "extend_existing": True,
        },
    )

    form_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    survey_uid = db.Column(
        db.Integer(),
        db.ForeignKey(Survey.survey_uid, ondelete="CASCADE"),
        nullable=False,
    )
    scto_form_id = db.Column(db.String(), nullable=False)
    form_name = db.Column(db.String(), nullable=False)
    tz_name = db.Column(db.String())
    scto_server_name = db.Column(db.String())
    encryption_key_shared = db.Column(db.Boolean())
    server_access_role_granted = db.Column(db.Boolean())
    server_access_allowed = db.Column(db.Boolean())
    scto_variable_mapping = db.Column(JSONB)
    last_ingested_at = db.Column(db.DateTime(), nullable=True)
    surveys = db.relationship(
        Survey, backref=backref("parent_forms", passive_deletes=True)
    )

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
        scto_variable_mapping,
    ):
        self.survey_uid = survey_uid
        self.scto_form_id = scto_form_id
        self.form_name = form_name
        self.tz_name = tz_name
        self.scto_server_name = scto_server_name
        self.encryption_key_shared = encryption_key_shared
        self.server_access_role_granted = server_access_role_granted
        self.server_access_allowed = server_access_allowed
        self.scto_variable_mapping = scto_variable_mapping

    def to_dict(self):
        return {
            "form_uid": self.form_uid,
            "survey_uid": self.survey_uid,
            "scto_form_id": self.scto_form_id,
            "form_name": self.form_name,
            "tz_name": self.tz_name,
            "scto_server_name": self.scto_server_name,
            "encryption_key_shared": self.encryption_key_shared,
            "server_access_role_granted": self.server_access_role_granted,
            "server_access_allowed": self.server_access_allowed,
            "scto_variable_mapping": self.scto_variable_mapping,
            "last_ingested_at": self.last_ingested_at,
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
            "schema": "config_sandbox",
            "extend_existing": True,
        },
    )

    list_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    form_uid = db.Column(
        db.Integer(),
        db.ForeignKey(ParentForm.form_uid, ondelete="CASCADE"),
        nullable=False,
    )
    list_name = db.Column(db.String(), nullable=False)
    forms = db.relationship(
        ParentForm, backref=backref("scto_form_choice_lists", passive_deletes=True)
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
            "schema": "config_sandbox",
            "extend_existing": True,
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
        db.UniqueConstraint(
            "form_uid",
            "question_name",
            "question_type",
        ),
        {
            "schema": "config_sandbox",
            "extend_existing": True,
        },
    )
    question_uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    form_uid = db.Column(
        db.Integer(),
        db.ForeignKey(ParentForm.form_uid, ondelete="CASCADE"),
        nullable=False,
    )
    question_name = db.Column(db.String(), nullable=False)
    question_type = db.Column(db.String(), nullable=False)
    list_uid = db.Column(db.Integer(), db.ForeignKey(SCTOChoiceList.list_uid))
    is_repeat_group = db.Column(db.Boolean(), nullable=False)
    forms = db.relationship(
        ParentForm, backref=backref("scto_form_questions", passive_deletes=True)
    )

    def __init__(
        self, form_uid, question_name, question_type, list_uid, is_repeat_group
    ):
        self.form_uid = form_uid
        self.question_name = question_name
        self.question_type = question_type
        self.list_uid = list_uid
        self.is_repeat_group = is_repeat_group

    def to_dict(self):
        return {
            "question_uid": self.question_uid,
            "form_uid": self.form_uid,
            "question_name": self.question_name,
            "question_type": self.question_type,
            "list_uid": self.list_uid,
            "is_repeat_group": self.is_repeat_group,
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
            "schema": "config_sandbox",
            "extend_existing": True,
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
