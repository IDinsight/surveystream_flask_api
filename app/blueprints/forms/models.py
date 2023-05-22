from app import db
from sqlalchemy.dialects.postgresql import JSONB

from app.blueprints.surveys.models import Survey


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
            "schema": "config_sandbox"
        }
    )

    form_uid = db.Column(db.Integer, primary_key=True)

    survey_uid = db.Column(
        db.Integer, db.ForeignKey(Survey.survey_uid)
    )
    scto_form_id = db.Column(db.String(), nullable=False)
    form_name = db.Column(db.String(), nullable=False)
    tz_name = db.Column(db.String())
    scto_server_name = db.Column(db.String())
    encryption_key_shared = db.Column(db.Boolean())
    server_access_role_granted = db.Column(db.Boolean())
    server_access_allowed = db.Column(db.Boolean())
    scto_variable_mapping = db.Column(JSONB)
    last_ingested_at = db.Column(db.DateTime())

    def __init__(
        self,
        form_uid,
        survey_uid,
        scto_form_id,
        form_name,
        tz_name,
        scto_server_name,
        encryption_key_shared,
        server_access_role_granted,
        server_access_allowed,
        scto_variable_mapping,
        last_ingested_at
    ):
        self.form_uid = form_uid
        self.survey_uid = survey_uid
        self.scto_form_id = scto_form_id
        self.form_name = form_name
        self.tz_name = tz_name
        self.scto_server_name = scto_server_name
        self.encryption_key_shared = encryption_key_shared
        self.server_access_role_granted = server_access_role_granted
        self.server_access_allowed = server_access_allowed
        self.scto_variable_mapping = scto_variable_mapping
        self.last_ingested_at = last_ingested_at

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
    

class SCTOQuestions(db.Model):
    """
    SQLAlchemy data model for storing scto questions
    This table contains information about the varibl
    within the survey, which are the main forms posed to respondents
    """

    __tablename__ = "scto_questionnaire_questions"

    __table_args__ = (
        db.PrimaryKeyConstraint(
            "survey_questionnaire_id",
            "variable_name",
        ),
        {}
    )
    survey_questionnaire_id = db.Column(db.String(), nullable=False)
    survey_id = db.Column(db.String(), nullable=False)
    questionnaire_id = db.Column(db.String(), nullable=False)
    variable_name = db.Column(db.String())
    variable_type = db.Column(db.String())
    question_no = db.Column(db.String())
    choice_name = db.Column(db.String())

    def __init__(
        self,
        survey_questionnaire_id,
        survey_id,
        questionnaire_id,
        variable_name,
        variable_type,
        question_no,
        choice_name
    ):
        self.survey_questionnaire_id = survey_questionnaire_id
        self.survey_id = survey_id
        self.questionnaire_id = questionnaire_id
        self.variable_name = variable_name
        self.variable_type = variable_type
        self.question_no = question_no
        self.choice_name = choice_name

    def to_dict(self):
        return {
            "survey_questionnaire_id": self.survey_questionnaire_id,
            "survey_id": self.survey_id,
            "questionnaire_id": self.questionnaire_id,
            "variable_name": self.variable_name,
            "variable_type": self.variable_type,
            "question_no": self.question_no,
            "choice_name": self.choice_name
        }