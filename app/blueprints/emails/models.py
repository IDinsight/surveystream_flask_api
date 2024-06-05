from sqlalchemy import TIME, CheckConstraint, Enum

from app import db
from app.blueprints.forms.models import Form


class EmailConfig(db.Model):
    __tablename__ = "email_configs"

    email_config_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    config_type = db.Column(db.String(100), nullable=False)  # assignments, #finance
    form_uid = db.Column(db.Integer, db.ForeignKey(Form.form_uid), nullable=False)

    __table_args__ = (
        # ensure that configs are not duplicated per form
        db.UniqueConstraint(
            "config_type",
            "form_uid",
            name="_email_configs_config_type_form_uid_uc",
        ),
        {"schema": "webapp"},
    )

    def __init__(self, config_type, form_uid):
        self.config_type = config_type
        self.form_uid = form_uid

    def to_dict(self):
        return {
            "email_config_uid": self.email_config_uid,
            "config_type": self.config_type,
            "form_uid": self.form_uid,
        }


class EmailSchedule(db.Model):
    __tablename__ = "email_schedules"
    __table_args__ = {
        "schema": "webapp",
    }

    email_schedule_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    email_config_uid = db.Column(
        db.Integer, db.ForeignKey(EmailConfig.email_config_uid), nullable=False
    )
    email_schedule_name = db.Column(
        db.String(255), nullable=False
    )  # Morning, Evening, Daily, Weekly
    dates = db.Column(db.ARRAY(db.Date), nullable=False)
    time = db.Column(TIME, nullable=False)

    def __init__(self, dates, time, email_config_uid, email_schedule_name):
        self.email_config_uid = email_config_uid
        self.dates = dates
        self.time = time
        self.email_schedule_name = email_schedule_name

    def to_dict(self):
        return {
            "email_schedule_uid": self.email_schedule_uid,
            "email_config_uid": self.email_config_uid,
            "email_schedule_name": self.email_schedule_name,
            "dates": self.dates,
            "time": str(self.time),
        }


class ManualEmailTrigger(db.Model):
    __tablename__ = "manual_email_triggers"
    __table_args__ = {
        "schema": "webapp",
    }

    manual_email_trigger_uid = db.Column(
        db.Integer(), primary_key=True, autoincrement=True
    )
    email_config_uid = db.Column(
        db.Integer, db.ForeignKey(EmailConfig.email_config_uid), nullable=False
    )
    date = db.Column(db.Date, nullable=False)
    time = db.Column(TIME, nullable=False)
    recipients = db.Column(db.ARRAY(db.Integer), nullable=True)
    status = db.Column(
        db.String(100),
        CheckConstraint(
            "status IN ('queued', 'sent', 'failed', 'running', 'progress')",
            name="ck_manual_email_triggers_status",
        ),
        nullable=False,
        default="queued",
    )

    def __init__(self, email_config_uid, date, time, recipients, status="queued"):
        self.email_config_uid = email_config_uid
        self.date = date
        self.time = time
        self.recipients = recipients
        self.status = status

    def to_dict(self):
        return {
            "manual_email_trigger_uid": self.manual_email_trigger_uid,
            "email_config_uid": self.email_config_uid,
            "date": self.date,
            "time": str(self.time),
            "recipients": self.recipients,
            "status": self.status,
        }


class EmailTemplate(db.Model):
    __tablename__ = "email_templates"

    email_template_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    subject = db.Column(db.String(255), nullable=False)
    language = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text(), nullable=False)
    email_config_uid = db.Column(
        db.Integer, db.ForeignKey(EmailConfig.email_config_uid), nullable=False
    )

    __table_args__ = (
        # ensure that language templates are not duplicated per config_uid
        db.UniqueConstraint(
            "email_config_uid",
            "language",
            name="_email_templates_email_config_uid_language_uc",
        ),
        {"schema": "webapp"},
    )

    def __init__(self, subject, content, language, email_config_uid):
        self.subject = subject
        self.content = content
        self.language = language
        self.email_config_uid = email_config_uid

    def to_dict(self):
        return {
            "email_template_uid": self.email_template_uid,
            "subject": self.subject,
            "language": self.language,
            "content": self.content,
            "email_config_uid": self.email_config_uid,
        }
