from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import CheckConstraint
from app import db
from app.blueprints.surveys.models import Survey


class ModuleQuestionnaire(db.Model):
    __tablename__ = "module_questionnaire"
    __table_args__ = {
        "schema": "webapp",
    }

    survey_uid = db.Column(
        db.Integer, db.ForeignKey(Survey.survey_uid), primary_key=True
    )
    target_assignment_criteria = db.Column(ARRAY(db.String()))
    target_mapping_criteria = db.Column(ARRAY(db.String()))
    surveyor_mapping_criteria = db.Column(ARRAY(db.String()))
    supervisor_hierarchy_exists = db.Column(db.Boolean())
    reassignment_required = db.Column(db.Boolean())
    assignment_process = db.Column(
        db.String(),
        CheckConstraint(
            "assignment_process IN ('Manual','Random')",
            name="ck_module_questionnaire_assignment_process",
        ),
    )
    supervisor_surveyor_relation = db.Column(
        db.String(),
        CheckConstraint(
            "supervisor_surveyor_relation IN ('1:1', '1:many', 'many:1', 'many:many')",
            name="ck_module_questionnaire_supervisor_surveyor_relation",
        ),
    )
    language_location_mapping = db.Column(db.Boolean())

    def __init__(
        self,
        survey_uid,
        target_assignment_criteria,
        target_mapping_criteria,
        surveyor_mapping_criteria,
        supervisor_hierarchy_exists,
        reassignment_required,
        assignment_process,
        supervisor_surveyor_relation,
        language_location_mapping,
    ):
        self.survey_uid = survey_uid
        self.target_assignment_criteria = target_assignment_criteria
        self.target_mapping_criteria = target_mapping_criteria
        self.surveyor_mapping_criteria = surveyor_mapping_criteria
        self.supervisor_hierarchy_exists = supervisor_hierarchy_exists
        self.reassignment_required = reassignment_required
        self.assignment_process = assignment_process
        self.supervisor_surveyor_relation = supervisor_surveyor_relation
        self.language_location_mapping = language_location_mapping

    def to_dict(self):
        return {
            "survey_uid": self.survey_uid,
            "target_assignment_criteria": self.target_assignment_criteria,
            "target_mapping_criteria": self.target_mapping_criteria,
            "surveyor_mapping_criteria": self.surveyor_mapping_criteria,
            "supervisor_hierarchy_exists": self.supervisor_hierarchy_exists,
            "reassignment_required": self.reassignment_required,
            "assignment_process": self.assignment_process,
            "supervisor_surveyor_relation": self.supervisor_surveyor_relation,
            "language_location_mapping": self.language_location_mapping,
        }
