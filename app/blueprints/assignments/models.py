from app import db
from app.blueprints.targets.models import Target
from app.blueprints.enumerators.models import Enumerator


class SurveyorAssignment(db.Model):
    """
    SQLAlchemy data model for Surveyor Assignment
    Description: This table contains all the assignments for surveyors
    """

    __tablename__ = "surveyor_assignments"

    target_uid = db.Column(
        db.Integer(), db.ForeignKey(Target.target_uid), primary_key=True
    )
    enumerator_uid = db.Column(
        db.Integer(), db.ForeignKey("enumerators.enumerator_uid"), nullable=False
    )
    user_uid = db.Column(db.Integer(), default=-1)
    to_delete = db.Column(db.Integer(), default=0, nullable=False)
