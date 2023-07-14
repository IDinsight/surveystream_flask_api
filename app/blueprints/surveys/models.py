import datetime
from app import db
from app.blueprints.auth.models import User
from sqlalchemy import CheckConstraint


class Survey(db.Model):
    __tablename__ = "surveys"
    __table_args__ = {
        "schema": "webapp",
    }

    survey_uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    survey_id = db.Column(db.String(64), unique=True, nullable=False)
    survey_name = db.Column(db.String(256), unique=True, nullable=False)
    project_name = db.Column(db.String(256), nullable=True)
    survey_description = db.Column(db.String(1024), nullable=True)
    surveying_method = db.Column(
        db.String(16),
        CheckConstraint("surveying_method IN ('phone', 'in-person')"),
        nullable=False,
    )
    planned_start_date = db.Column(db.Date, nullable=False)
    planned_end_date = db.Column(db.Date, nullable=False)
    irb_approval = db.Column(
        db.String(8),
        CheckConstraint("irb_approval IN ('Yes','No','Pending')"),
        nullable=False,
    )
    config_status = db.Column(
        db.String(32),
        CheckConstraint(
            "config_status IN ('In Progress - Configuration','In Progress - Backend Setup','Done')"
        ),
        nullable=True,
    )
    state = db.Column(
        db.String(16),
        CheckConstraint("state IN ('Draft','Active','Past')"),
        nullable=True,
    )
    created_by_user_uid = db.Column(db.Integer(), db.ForeignKey(User.user_uid))
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
        self.last_updated_at = datetime.datetime.now()

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
            "config_status": self.config_status,
            "state": self.state,
            "last_updated_at": str(self.last_updated_at),
        }
