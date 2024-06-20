from sqlalchemy import TIME, CheckConstraint, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from app import db
from app.blueprints.forms.models import Form


class EmailConfig(db.Model):
    __tablename__ = "email_configs"

    email_config_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    config_type = db.Column(db.String(100), nullable=False)  # assignments, #finance
    form_uid = db.Column(db.Integer, db.ForeignKey(Form.form_uid), nullable=False)
    report_users = db.Column(db.ARRAY(db.Integer), nullable=True)
    email_source = db.Column(
        db.String(20),
        CheckConstraint(
            "email_source IN ('Google Sheet', 'SurveyStream Data')",
            name="ck_email_configs_source",
        ),
        server_default="SurveyStream Data",
        nullable=False,
    )  # Gsheet/SurveyStream
    email_source_gsheet_link = db.Column(db.String(512), nullable=True)  # Gsheet Link
    email_source_gsheet_tab = db.Column(db.String(256), nullable=True)  # Gsheet tab
    email_source_gsheet_header_row = db.Column(db.Integer, nullable=True)
    email_source_tablename = db.Column(db.String(256), nullable=True)
    email_source_columns = db.Column(
        db.ARRAY(db.String(128)), nullable=True
    )  # List of columns from Gsheet or Table

    schedules = db.relationship(
        "EmailSchedule",
        backref="email_config",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    templates = db.relationship(
        "EmailTemplate",
        backref="email_config",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    manual_triggers = db.relationship(
        "ManualEmailTrigger",
        backref="email_config",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        # Ensure that configs are not duplicated per form
        db.UniqueConstraint(
            "config_type",
            "form_uid",
            name="_email_configs_config_type_form_uid_uc",
        ),
        {"schema": "webapp"},
    )

    def __init__(
        self,
        config_type,
        form_uid,
        email_source,
        report_users=None,
        email_source_gsheet_link=None,
        email_source_gsheet_tab=None,
        email_source_gsheet_header_row=None,
        email_source_tablename=None,
        email_source_columns=None,
    ):
        self.config_type = config_type
        self.form_uid = form_uid
        self.report_users = report_users
        self.email_source = email_source
        self.email_source_gsheet_link = email_source_gsheet_link
        self.email_source_gsheet_tab = email_source_gsheet_tab
        self.email_source_gsheet_header_row = email_source_gsheet_header_row
        self.email_source_tablename = email_source_tablename
        self.email_source_columns = email_source_columns

    def to_dict(self):
        return {
            "email_config_uid": self.email_config_uid,
            "config_type": self.config_type,
            "form_uid": self.form_uid,
            "report_users": self.report_users,
            "email_source": self.email_source,
            "email_source_gsheet_link": self.email_source_gsheet_link,
            "email_source_gsheet_tab": self.email_source_gsheet_tab,
            "email_source_gsheet_header_row": self.email_source_gsheet_header_row,
            "email_source_tablename": self.email_source_tablename,
            "email_source_columns": self.email_source_columns,
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
        email_template_variables = EmailTemplateVariable.query.filter_by(
            email_template_uid=self.email_template_uid
        ).all()
        return {
            "email_template_uid": self.email_template_uid,
            "subject": self.subject,
            "language": self.language,
            "content": self.content,
            "email_config_uid": self.email_config_uid,
            "variable_list": [
                variable.to_dict() for variable in email_template_variables
            ],
        }


class EmailTemplateVariable(db.Model):
    __tablename__ = "email_template_variables"

    email_template_uid = db.Column(
        db.Integer(), db.ForeignKey(EmailTemplate.email_template_uid), nullable=False
    )

    variable_name = db.Column(db.String(100), nullable=False)
    variable_type = db.Column(
        db.String(32),
        CheckConstraint(
            "variable_type IN ('string', 'table')",
            name="ck_email_template_variables_variable_type",
        ),
        nullable=False,
    )
    source_table = db.Column(db.String(255), nullable=True)
    variable_expression = db.Column(db.String(255), nullable=True)
    table_column_mapping = db.Column(MutableDict.as_mutable(JSONB), nullable=True)

    __table_args__ = (
        db.PrimaryKeyConstraint("email_template_uid", "variable_name"),
        {"schema": "webapp"},
    )

    def __init__(
        self,
        email_template_uid,
        variable_name,
        variable_type,
        source_table,
        variable_expression,
        table_column_mapping,
    ):
        self.email_template_uid = email_template_uid
        self.variable_name = variable_name
        self.variable_type = variable_type
        self.source_table = source_table
        self.variable_expression = variable_expression
        self.table_column_mapping = table_column_mapping

    def to_dict(self):
        return {
            "variable_name": self.variable_name,
            "variable_type": self.variable_type,
            "source_table": self.source_table,
            "variable_expression": self.variable_expression,
            "table_column_mapping": self.table_column_mapping,
        }
