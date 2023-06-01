from datetime import date
from app import db


class Survey(db.Model):
    __tablename__ = "surveys"
    __table_args__ = {
        "extend_existing": True,
        "schema": "config_sandbox",
    }

    survey_uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    survey_id = db.Column(db.String(64), unique=True, nullable=False)
    survey_name = db.Column(db.String(256), unique=True, nullable=False)
    project_name = db.Column(db.String(256), nullable=True)
    survey_description = db.Column(db.String(1024), nullable=True)
    surveying_method = db.Column(db.String(16), nullable=False)
    planned_start_date = db.Column(db.Date, nullable=False)
    planned_end_date = db.Column(db.Date, nullable=False)
    irb_approval = db.Column(db.String(8), nullable=False)
    config_status = db.Column(db.String(32), nullable=True)
    state = db.Column(db.String(16), nullable=True)
    created_by_user_uid = db.Column(
        db.Integer, db.ForeignKey("users.user_uid"), nullable=False
    )
    last_updated_at = db.Column(
        db.TIMESTAMP, nullable=False, default=db.func.current_timestamp()
    )

    def __init__(
        self,
        survey_id,
        survey_name,
        project_name,
        survey_description,
        surveying_method,
        planned_start_date,
        planned_end_date,
        irb_approval,
        config_status,
        state,
        created_by_user_uid,
    ):
        self.survey_id = survey_id
        self.survey_name = survey_name
        self.project_name = project_name
        self.survey_description = survey_description
        self.surveying_method = surveying_method
        self.planned_start_date = planned_start_date
        self.planned_end_date = planned_end_date
        self.irb_approval = irb_approval
        self.config_status = config_status
        self.state = state
        self.created_by_user_uid = created_by_user_uid
        self.last_updated_at = date.today()

    def to_dict(self):
        return {
            "survey_uid": self.survey_uid,
            "survey_id": self.survey_id,
            "survey_name": self.survey_name,
            "project_name": self.project_name,
            "survey_description": self.survey_description,
            "surveying_method": self.surveying_method,
            "irb_approval": self.irb_approval,
            "planned_start_date": str(self.planned_start_date),
            "planned_end_date": str(self.planned_end_date),
            "state": self.state,
            "last_updated_at": str(self.last_updated_at),
        }

    def validate(self):
        errors = []
        if self.planned_start_date >= self.planned_end_date:
            errors.append("Start time must be earlier than end time.")
        if self.surveying_method not in ("phone", "in-person"):
            errors.append('Surveying method must be either "phone" or "in-person".')
        if self.irb_approval not in ("Yes", "No", "Pending"):
            errors.append('IRB approval must be either "Yes", "No", or "Pending".')
        if self.config_status not in (
            "In Progress - Configuration",
            "In Progress - Backend Setup",
            "Done",
        ):
            errors.append(
                'Config status must be either "In Progress - Configuration", "In Progress - Backend Setup", or "Done".'
            )
        if self.state not in ("Draft", "Active", "Past"):
            errors.append('State must be either "Draft", "Active", or "Past".')
        return errors
