from app import db
from app.blueprints.forms.models import Form
from sqlalchemy import CheckConstraint


class DefaultTargetStatusMapping(db.Model):
    """
    SQLAlchemy data model for default target_status_mapping
    This table defines the default target status mapping for each surveying method
    """

    __tablename__ = "default_target_status_mapping"

    surveying_method = db.Column(
        db.String(16),
        CheckConstraint(
            "surveying_method IN ('phone', 'in-person', 'mixed-mode')",
            name="ck_surveys_surveying_method",
        ),
        nullable=False,
    )

    survey_status = db.Column(db.Integer(), nullable=False)
    survey_status_label = db.Column(db.String(), nullable=False)

    completed_flag = db.Column(db.Boolean(), default=False, nullable=False)
    refusal_flag = db.Column(db.Boolean(), default=False, nullable=False)
    target_assignable = db.Column(db.Boolean(), default=True, nullable=False)
    webapp_tag_color = db.Column(db.String(), nullable=False)

    __table_args__ = (
        db.PrimaryKeyConstraint("surveying_method", "survey_status"),
        {"schema": "webapp"},
    )

    def __init__(
        self,
        surveying_method,
        survey_status,
        survey_status_label,
        completed_flag,
        refusal_flag,
        target_assignable,
        webapp_tag_color
    ):
        self.surveying_method = surveying_method
        self.survey_status = survey_status
        self.survey_status_label = survey_status_label
        self.completed_flag = completed_flag
        self.refusal_flag = refusal_flag
        self.target_assignable = target_assignable
        self.webapp_tag_color = webapp_tag_color

    def to_dict(self):
        result = {
            "surveying_method": self.surveying_method,
            "survey_status": self.survey_status,
            "survey_status_label": self.survey_status_label,
            "completed_flag": self.completed_flag,
            "refusal_flag": self.refusal_flag,
            "target_assignable": self.target_assignable,
            "webapp_tag_color": self.webapp_tag_color,
        }

        return result


class TargetStatusMapping(db.Model):
    """
    SQLAlchemy data model for target_status_mapping
    This table defines custom target status mapping for a specific form
    """

    __tablename__ = "target_status_mapping"

    form_uid = db.Column(
        db.Integer(), db.ForeignKey(Form.form_uid), nullable=False
    )
    survey_status = db.Column(db.Integer(), nullable=False)
    survey_status_label = db.Column(db.String(), nullable=False)

    completed_flag = db.Column(db.Boolean(), default=False, nullable=False)
    refusal_flag = db.Column(db.Boolean(), default=False, nullable=False)
    target_assignable = db.Column(db.Boolean(), default=True, nullable=False)
    webapp_tag_color = db.Column(db.String(), nullable=False)

    __table_args__ = (
        db.PrimaryKeyConstraint("form_uid", "survey_status"),
        {"schema": "webapp"},
    )

    def __init__(
        self,
        form_uid,
        survey_status,
        survey_status_label,
        completed_flag,
        refusal_flag,
        target_assignable,
        webapp_tag_color
    ):
        self.form_uid = form_uid
        self.survey_status = survey_status
        self.survey_status_label = survey_status_label
        self.completed_flag = completed_flag
        self.refusal_flag = refusal_flag
        self.target_assignable = target_assignable
        self.webapp_tag_color = webapp_tag_color

    def to_dict(self):
        result = {
            "form_uid": self.form_uid,
            "survey_status": self.survey_status,
            "survey_status_label": self.survey_status_label,
            "completed_flag": self.completed_flag,
            "refusal_flag": self.refusal_flag,
            "target_assignable": self.target_assignable,
            "webapp_tag_color": self.webapp_tag_color,
        }

        return result
