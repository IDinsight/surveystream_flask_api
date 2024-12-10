from sqlalchemy import CheckConstraint

from app import db
from app.blueprints.auth.models import User
from app.blueprints.module_selection.models import Module
from app.blueprints.surveys.models import Survey


class SurveyNotification(db.Model):
    __tablename__ = "survey_notifications"

    notification_uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    survey_uid = db.Column(
        db.Integer, db.ForeignKey(Survey.survey_uid, ondelete="CASCADE"), nullable=False
    )
    module_id = db.Column(
        db.Integer, db.ForeignKey(Module.module_id, ondelete="CASCADE"), nullable=False
    )
    severity = db.Column(
        db.String(8),
        CheckConstraint(
            "severity IN ('alert','warning','error')",
            name="ck_survey_notifications_severity",
        ),
        nullable=False,
        server_default="alert",
    )
    resolution_status = db.Column(
        db.String(16),
        CheckConstraint(
            "resolution_status IN ('in progress','done')",
            name="ck_survey_notifications_resolution_status",
        ),
        nullable=False,
        server_default="in progress",
    )
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.TIMESTAMP, nullable=False, server_default=db.func.current_timestamp()
    )

    __table_args__ = {
        "schema": "webapp",
    }

    def __init__(
        self,
        survey_uid,
        module_id,
        severity,
        resolution_status,
        message,
    ):
        self.survey_uid = survey_uid
        self.module_id = module_id
        self.severity = severity
        self.resolution_status = resolution_status
        self.message = message

    def to_dict(self):
        return {
            "notification_uid": self.notification_uid,
            "severity": self.severity,
            "resolution_status": self.resolution_status,
            "message": self.message,
            "created_at": self.created_at,
        }


class UserNotification(db.Model):
    __tablename__ = "user_notifications"

    notification_uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_uid = db.Column(db.Integer, db.ForeignKey(User.user_uid, ondelete="CASCADE"))
    severity = db.Column(
        db.String(8),
        CheckConstraint(
            "severity IN ('alert','warning','error')",
            name="ck_user_notifications_severity",
        ),
        server_default="alert",
        nullable=False,
    )
    resolution_status = db.Column(
        db.String(16),
        CheckConstraint(
            "resolution_status IN ('in progress','done')",
            name="ck_user_notifications_resolution_status",
        ),
        server_default="in progress",
        nullable=False,
    )
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.TIMESTAMP, nullable=False, server_default=db.func.current_timestamp()
    )

    __table_args__ = {
        "schema": "webapp",
    }

    def __init__(
        self,
        user_uid,
        severity,
        resolution_status,
        message,
    ):
        self.user_uid = user_uid
        self.severity = severity
        self.resolution_status = resolution_status
        self.message = message

    def to_dict(self):
        return {
            "notification_uid": self.notification_uid,
            "severity": self.severity,
            "resolution_status": self.resolution_status,
            "message": self.message,
            "created_at": self.created_at,
        }
