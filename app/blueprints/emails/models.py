from app import db
from app.blueprints.forms.models import Form


class EmailSchedule(db.Model):
    __tablename__ = "email_schedules"

    email_schedule_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    form_uid = db.Column(db.Integer, db.ForeignKey(Form.form_uid), nullable=False)
    date = db.Column(db.ARRAY(db.Date), nullable=False)
    time = db.Column(db.TIMESTAMP, nullable=False)
    template_uid = db.Column(db.Integer, nullable=True)


class ManualEmailTrigger(db.Model):
    __tablename__ = "manual_email_triggers"

    manual_email_trigger_id = db.Column(
        db.Integer(), primary_key=True, autoincrement=True
    )
    form_uid = db.Column(db.Integer, db.ForeignKey(Form.form_uid), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.TIMESTAMP, nullable=False)
    recipients = db.Column(db.ARRAY(db.Integer), nullable=False)
    template_uid = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(50))


class EmailTemplate(db.Model):
    __tablename__ = "email_templates"

    email_template_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    template_name = db.Column(db.String(100), nullable=False, unique=True)
    subject = db.Column(db.String(255), nullable=False)
    sender_email = db.Column(db.String(100), nullable=True)
    content = db.Column(db.Text(), nullable=False)
