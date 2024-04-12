from app import db
from app.blueprints.forms.models import Form
from sqlalchemy import Enum, CheckConstraint, TIME


class EmailSchedule(db.Model):
    __tablename__ = "email_schedules"
    __table_args__ = {
        "schema": "webapp",
    }

    email_schedule_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    form_uid = db.Column(db.Integer, db.ForeignKey(Form.form_uid), nullable=False)
    dates = db.Column(db.ARRAY(db.Date), nullable=False)
    time = db.Column(TIME, nullable=False)
    template_uid = db.Column(db.Integer, nullable=True)

    def __init__(self, form_uid, dates, time, template_uid=None):
        self.form_uid = form_uid
        self.dates = dates
        self.time = time
        self.template_uid = template_uid

    def to_dict(self):
        return {
            "email_schedule_uid": self.email_schedule_uid,
            "form_uid": self.form_uid,
            "dates": self.dates,
            "time": str(self.time),
            "template_uid": self.template_uid,
        }


class ManualEmailTrigger(db.Model):
    __tablename__ = "manual_email_triggers"
    __table_args__ = {
        "schema": "webapp",
    }

    manual_email_trigger_uid = db.Column(
        db.Integer(), primary_key=True, autoincrement=True
    )
    form_uid = db.Column(db.Integer, db.ForeignKey(Form.form_uid), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(TIME, nullable=False)
    recipients = db.Column(db.ARRAY(db.Integer), nullable=False)
    template_uid = db.Column(db.Integer, nullable=True)
    status = db.Column(
        Enum("queued", "sent", "failed", name="status_enum"),
        CheckConstraint("status IN ('queued', 'sent', 'failed')", name="check_status"),
        nullable=False,
    )

    def __init__(
        self, form_uid, date, time, recipients, template_uid=None, status=None
    ):
        self.form_uid = form_uid
        self.date = date
        self.time = time
        self.recipients = recipients
        self.template_uid = template_uid
        self.status = status

    def to_dict(self):
        return {
            "manual_email_trigger_uid": self.manual_email_trigger_uid,
            "form_uid": self.form_uid,
            "date": self.date,
            "time": str(self.time),
            "recipients": self.recipients,
            "template_uid": self.template_uid,
            "status": self.status,
        }


class EmailTemplate(db.Model):
    __tablename__ = "email_templates"
    __table_args__ = {
        "schema": "webapp",
    }

    email_template_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    template_name = db.Column(db.String(100), nullable=False, unique=True)
    subject = db.Column(db.String(255), nullable=False)
    sender_email = db.Column(db.String(100), nullable=True)
    content = db.Column(db.Text(), nullable=False)

    def __init__(self, template_name, subject, content, sender_email=None):
        self.template_name = template_name
        self.subject = subject
        self.content = content
        self.sender_email = sender_email

    def to_dict(self):
        return {
            "email_template_uid": self.email_template_uid,
            "template_name": self.template_name,
            "subject": self.subject,
            "sender_email": self.sender_email,
            "content": self.content,
        }
