from sqlalchemy.dialects.postgresql import ARRAY

from flask_app.database import db
from flask_app.surveys.models import Survey


class ModuleQuestionnaire(db.Model):

    __tablename__ = "module_questionnaire"
    __table_args__ = {
        "extend_existing": True,
        "schema": "config_sandbox",
    }

    survey_uid = db.Column(
        db.Integer, db.ForeignKey(Survey.survey_uid), primary_key=True
    )
    target_assignment_criteria = db.Column(ARRAY(db.String()))
    supervisor_assignment_criteria = db.Column(ARRAY(db.String()))
    supervisor_hierarchy_exists = db.Column(db.Boolean())
    reassignment_required = db.Column(db.Boolean())
    assignment_process = db.Column(db.String())
    supervisor_enumerator_relation = db.Column(db.String())
    language_lacation_mapping = db.Column(db.Boolean())

    def __init__(
        self,
        survey_uid,
        target_assignment_criteria,
        supervisor_assignment_criteria,
        supervisor_hierarchy_exists,
        reassignment_required,
        assignment_process,
        supervisor_enumerator_relation,
        language_lacation_mapping,
    ):
        self.survey_uid = survey_uid
        self.target_assignment_criteria = target_assignment_criteria
        self.supervisor_assignment_criteria = supervisor_assignment_criteria
        self.supervisor_hierarchy_exists = supervisor_hierarchy_exists
        self.reassignment_required = reassignment_required
        self.assignment_process = assignment_process
        self.supervisor_enumerator_relation = supervisor_enumerator_relation
        self.language_lacation_mapping = language_lacation_mapping

    def to_dict(self):
        return {
            "survey_uid": self.survey_uid,
            "target_assignment_criteria": self.target_assignment_criteria,
            "supervisor_assignment_criteria": self.supervisor_assignment_criteria,
            "supervisor_hierarchy_exists": self.supervisor_hierarchy_exists,
            "reassignment_required": self.reassignment_required,
            "assignment_process": self.assignment_process,
            "supervisor_enumerator_relation": self.supervisor_enumerator_relation,
            "language_lacation_mapping": self.language_lacation_mapping,
        }

    def validate(self):
        errors = []
        if self.assignment_process not in ("Random", "Manual"):
            errors.append('Assignment methos must be either "Random" or "Manual".')
        return errors
