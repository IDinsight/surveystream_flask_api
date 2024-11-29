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
    notification_type = db.Column(
        db.String(8),
        CheckConstraint(
            "notification_type IN ('alert','warning','error')",
            name="ck_survey_notifications_type",
        ),
        nullable=False,
        server_default="alert",
    )
    notification_status = db.Column(
        db.String(16),
        CheckConstraint(
            "notification_status IN ('in progress','done')",
            name="ck_survey_notifications_status",
        ),
        nullable=False,
        server_default="in progress",
    )
    notification_message = db.Column(db.Text, nullable=False)
    notification_timestamp = db.Column(
        db.TIMESTAMP, nullable=False, server_default=db.func.current_timestamp()
    )

    __table_args__ = {
        "schema": "webapp",
    }

    def __init__(
        self,
        survey_uid,
        module_id,
        notification_type,
        notification_status,
        notification_message,
    ):
        self.survey_uid = survey_uid
        self.module_id = module_id
        self.notification_type = notification_type
        self.notification_status = notification_status
        self.notification_message = notification_message

    def to_dict(self):
        return {
            "notification_type": self.notification_type,
            "notification_status": self.notification_status,
            "notification_message": self.notification_message,
            "notification_timestamp": self.notification_timestamp,
        }


class UserNotification(db.Model):
    __tablename__ = "user_notifications"

    user_notification_uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_uid = db.Column(db.Integer, db.ForeignKey(User.user_uid, ondelete="CASCADE"))
    notification_type = db.Column(
        db.String(8),
        CheckConstraint(
            "notification_type IN ('alert','warning','error')",
            name="ck_user_notifications_type",
        ),
        nullable=False,
    )
    notification_status = db.Column(
        db.String(16),
        CheckConstraint(
            "notification_status IN ('in progress','done')",
            name="ck_user_notifications_status",
        ),
        nullable=False,
    )
    notification_message = db.Column(db.Text, nullable=False)
    notification_timestamp = db.Column(
        db.TIMESTAMP, nullable=False, server_default=db.func.current_timestamp()
    )

    __table_args__ = {
        "schema": "webapp",
    }

    def __init__(
        self,
        user_uid,
        notification_type,
        notification_status,
        notification_message,
    ):
        self.user_uid = user_uid
        self.notification_type = notification_type
        self.notification_status = notification_status
        self.notification_message = notification_message

    def to_dict(self):
        return {
            "notification_type": self.notification_type,
            "notification_status": self.notification_status,
            "notification_message": self.notification_message,
            "notification_timestamp": self.notification_timestamp,
        }
