from app import db


class EmailSchedule(db.Model):
    __tablename__ = "email_schedules"

    email_schedule_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    form_uid = db.Column(db.Integer, unique=True)
    date = db.Column(db.ARRAY(db.Date))
    time = db.Column(db.TIMESTAMP)
    template_uid = db.Column(db.Integer)


class ManualEmailTrigger(db.Model):
    __tablename__ = "manual_email_triggers"

    manual_email_trigger_id = db.Column(
        db.Integer(), primary_key=True, autoincrement=True
    )
    form_uid = db.Column(db.Integer, unique=True)
    date = db.Column(db.Date)
    time = db.Column(db.TIMESTAMP)
    recipients = db.Column(db.ARRAY(db.Integer))
    template_uid = db.Column(db.Integer)
    status = db.Column(db.String(50))


class EmailTemplate(db.Model):
    __tablename__ = "email_templates"

    email_template_id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    template_name = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(255))
    sender_email = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text(), nullable=False)
