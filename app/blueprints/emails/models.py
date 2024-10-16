from sqlalchemy import TIME, CheckConstraint
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.ext.mutable import MutableDict

from app import db
from app.blueprints.enumerators.models import Enumerator
from app.blueprints.forms.models import Form
from app.blueprints.surveys.models import Survey


class EmailConfig(db.Model):
    __tablename__ = "email_configs"

    email_config_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    config_name = db.Column(db.String(100), nullable=False)  # assignments, #finance
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
    email_source_columns = db.Column(db.ARRAY(db.String(128)), nullable=True)
    cc_users = db.Column(db.ARRAY(db.Integer), nullable=True)
    pdf_attachment = db.Column(db.Boolean, nullable=False, server_default="false")
    pdf_encryption = db.Column(db.Boolean, nullable=False, server_default="false")
    pdf_encryption_password_type = db.Column(
        db.String(16),
        CheckConstraint(
            "pdf_encryption_password_type IN ('Pattern', 'Password')",
            name="ck_email_configs_pdf_encryption_password_type",
        ),
        nullable=True,
    )

    # List of columns from Gsheet or Table
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
            "config_name",
            "form_uid",
            name="_email_configs_config_name_form_uid_uc",
        ),
        {"schema": "webapp"},
    )

    def __init__(
        self,
        config_name,
        form_uid,
        email_source,
        report_users=None,
        email_source_gsheet_link=None,
        email_source_gsheet_tab=None,
        email_source_gsheet_header_row=None,
        email_source_tablename=None,
        email_source_columns=None,
        cc_users=None,
        pdf_attachment=False,
        pdf_encryption=False,
        pdf_encryption_password_type=None,
    ):
        self.config_name = config_name
        self.form_uid = form_uid
        self.report_users = report_users
        self.email_source = email_source
        self.email_source_gsheet_link = email_source_gsheet_link
        self.email_source_gsheet_tab = email_source_gsheet_tab
        self.email_source_gsheet_header_row = email_source_gsheet_header_row
        self.email_source_tablename = email_source_tablename
        self.cc_users = cc_users
        self.pdf_attachment = pdf_attachment
        self.pdf_encryption = pdf_encryption
        self.pdf_encryption_password_type = pdf_encryption_password_type
        self.email_source_columns = email_source_columns

    def to_dict(self):
        return {
            "email_config_uid": self.email_config_uid,
            "config_name": self.config_name,
            "form_uid": self.form_uid,
            "report_users": self.report_users,
            "email_source": self.email_source,
            "email_source_gsheet_link": self.email_source_gsheet_link,
            "email_source_gsheet_tab": self.email_source_gsheet_tab,
            "email_source_gsheet_header_row": self.email_source_gsheet_header_row,
            "email_source_tablename": self.email_source_tablename,
            "email_source_columns": self.email_source_columns,
            "cc_users": self.cc_users,
            "pdf_attachment": self.pdf_attachment,
            "pdf_encryption": self.pdf_encryption,
            "pdf_encryption_password_type": self.pdf_encryption_password_type,
        }


class EmailSchedule(db.Model):
    __tablename__ = "email_schedules"
    __table_args__ = {
        "schema": "webapp",
    }

    email_schedule_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    email_config_uid = db.Column(
        db.Integer,
        db.ForeignKey(EmailConfig.email_config_uid, ondelete="CASCADE"),
        nullable=False,
    )
    email_schedule_name = db.Column(
        db.String(255), nullable=False
    )  # Morning, Evening, Daily, Weekly
    dates = db.Column(db.ARRAY(db.Date), nullable=False)
    time = db.Column(TIME, nullable=False)

    email_schedule_filters = db.relationship(
        "EmailScheduleFilter",
        backref="email_schedule",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

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
        db.Integer,
        db.ForeignKey(EmailConfig.email_config_uid, ondelete="CASCADE"),
        nullable=False,
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
        db.Integer,
        db.ForeignKey(EmailConfig.email_config_uid, ondelete="CASCADE"),
        nullable=False,
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

    email_template_tables = db.relationship(
        "EmailTemplateTable",
        backref="email_template",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    email_template_variables = db.relationship(
        "EmailTemplateVariable",
        backref="email_template",
        lazy="dynamic",
        cascade="all, delete-orphan",
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


class EmailTemplateTable(db.Model):
    __tablename__ = "email_template_tables"

    email_template_table_uid = db.Column(
        db.Integer(), primary_key=True, autoincrement=True
    )
    email_template_uid = db.Column(
        db.Integer(),
        db.ForeignKey(EmailTemplate.email_template_uid, ondelete="CASCADE"),
        nullable=False,
    )

    table_name = db.Column(db.String(255), nullable=False)
    column_mapping = db.Column(MutableDict.as_mutable(JSON), nullable=False)
    sort_list = db.Column(MutableDict.as_mutable(JSON), nullable=True)
    variable_name = db.Column(db.String(100), nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "email_template_uid",
            "table_name",
            "variable_name",
            name="email_template_table_uc",
        ),
        {"schema": "webapp"},
    )

    email_table_filters = db.relationship(
        "EmailTableFilter",
        backref="email_template_table",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __init__(
        self, email_template_uid, table_name, column_mapping, variable_name, sort_list
    ):
        self.email_template_uid = email_template_uid
        self.table_name = table_name
        self.column_mapping = column_mapping
        self.variable_name = variable_name
        self.sort_list = sort_list

    def to_dict(self):
        return {
            "email_template_table_uid": self.email_template_table_uid,
            "table_name": self.table_name,
            "column_mapping": self.column_mapping,
            "variable_name": self.variable_name,
            "sort_list": self.sort_list,
        }


class EmailTemplateVariable(db.Model):
    __tablename__ = "email_template_variables"

    email_template_variable_uid = db.Column(
        db.Integer(), primary_key=True, autoincrement=True
    )
    email_template_uid = db.Column(
        db.Integer(),
        db.ForeignKey(EmailTemplate.email_template_uid, ondelete="CASCADE"),
        nullable=False,
    )

    variable_name = db.Column(db.String(100), nullable=False)
    source_table = db.Column(db.String(255), nullable=True)
    variable_expression = db.Column(db.String(255), nullable=True)

    __table_args__ = (
        db.PrimaryKeyConstraint("email_template_variable_uid"),
        db.UniqueConstraint(
            "email_template_uid",
            "variable_name",
            "variable_expression",
            name="email_template_variable_uc",
        ),
        {"schema": "webapp"},
    )

    def __init__(
        self,
        email_template_uid,
        variable_name,
        variable_expression,
    ):
        self.email_template_uid = email_template_uid
        self.variable_name = variable_name
        self.variable_expression = variable_expression

    def to_dict(self):
        return {
            "variable_name": self.variable_name,
            "variable_expression": self.variable_expression,
        }


class EmailTableCatalog(db.Model):
    __tablename__ = "email_table_catalog"

    survey_uid = db.Column(db.Integer, db.ForeignKey(Survey.survey_uid), nullable=False)
    table_name = db.Column(db.String(255), nullable=False)
    column_name = db.Column(db.String(255), nullable=False)
    column_type = db.Column(db.String(255), nullable=False)
    column_description = db.Column(db.String(255), nullable=True)

    __table_args__ = (
        db.PrimaryKeyConstraint("survey_uid", "table_name", "column_name"),
        {"schema": "webapp"},
    )

    def __init__(
        self, survey_uid, table_name, column_name, column_type, column_description
    ):
        self.survey_uid = survey_uid
        self.table_name = table_name
        self.column_name = column_name
        self.column_type = column_type
        self.column_description = column_description

    def to_dict(self):
        return {
            "survey_uid": self.survey_uid,
            "table_name": self.table_name,
            "column_name": self.column_name,
            "column_type": self.column_type,
            "column_description": self.column_description,
        }


class EmailTableFilter(db.Model):
    __tablename__ = "email_table_filters"

    table_filter_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)

    email_template_table_uid = db.Column(
        db.Integer,
        db.ForeignKey(EmailTemplateTable.email_template_table_uid, ondelete="CASCADE"),
        nullable=False,
    )
    filter_group_id = db.Column(db.Integer, nullable=False)
    filter_variable = db.Column(db.String(255), nullable=False)
    filter_operator = db.Column(
        db.String(64),
        CheckConstraint(
            """filter_operator IN 
            (   'Is',
                'Is not',
                'Contains',
                'Does not contain',
                'Is Empty',
                'Is not empty',
                'Greather than',
                'Smaller than',
                'Date: Is Current Date',
                'Date: In last week',
                'Date: In last month',
                'Date: In Date Range')""",
            name="ck_email_table_filter_operator",
        ),
        nullable=False,
    )
    filter_value = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.PrimaryKeyConstraint(table_filter_uid),
        {"schema": "webapp"},
    )

    def __init__(
        self,
        email_template_table_uid,
        filter_group_id,
        filter_variable,
        filter_operator,
        filter_value,
    ):
        self.email_template_table_uid = email_template_table_uid
        self.filter_group_id = filter_group_id
        self.filter_variable = filter_variable
        self.filter_operator = filter_operator
        self.filter_value = filter_value

    def to_dict(self):
        return {
            "email_template_table_uid": self.email_template_table_uid,
            "filter_group_id": self.filter_group_id,
            "filter_variable": self.filter_variable,
            "filter_operator": self.filter_operator,
            "filter_value": self.filter_value,
        }


class EmailScheduleFilter(db.Model):
    __tablename__ = "email_schedule_filters"

    schedule_filter_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    email_schedule_uid = db.Column(
        db.Integer,
        db.ForeignKey(EmailSchedule.email_schedule_uid, ondelete="CASCADE"),
        nullable=False,
    )
    table_name = db.Column(db.String(255), nullable=False)
    filter_group_id = db.Column(db.Integer)
    filter_variable = db.Column(db.String(255), nullable=False)
    filter_operator = db.Column(
        db.String(64),
        CheckConstraint(
            """filter_operator IN 
            (   'Is',
                'Is not',
                'Contains',
                'Does not contain',
                'Is Empty',
                'Is not empty',
                'Greather than',
                'Smaller than',
                'Date: Is Current Date',
                'Date: In last week',
                'Date: In last month',
                'Date: In Date Range')""",
            name="ck_email_schedule_filter_operator",
        ),
        nullable=False,
    )
    filter_value = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.PrimaryKeyConstraint(schedule_filter_uid),
        {"schema": "webapp"},
    )

    def __init__(
        self,
        email_schedule_uid,
        filter_group_id,
        table_name,
        filter_variable,
        filter_operator,
        filter_value,
    ):
        self.email_schedule_uid = email_schedule_uid
        self.filter_group_id = filter_group_id
        self.table_name = table_name
        self.filter_variable = filter_variable
        self.filter_operator = filter_operator
        self.filter_value = filter_value

    def to_dict(self):
        return {
            "email_schedule_uid": self.email_schedule_uid,
            "table_name": self.table_name,
            "filter_group_id": self.filter_group_id,
            "filter_variable": self.filter_variable,
            "filter_operator": self.filter_operator,
            "filter_value": self.filter_value,
        }


class EmailDeliveryReport(db.Model):
    __tablename__ = "email_delivery_reports"

    email_delivery_report_uid = db.Column(
        db.Integer(), primary_key=True, autoincrement=True
    )
    email_schedule_uid = db.Column(
        db.Integer,
        db.ForeignKey(EmailSchedule.email_schedule_uid, ondelete="CASCADE"),
        nullable=True,
    )
    manual_email_trigger_uid = db.Column(
        db.Integer,
        db.ForeignKey(ManualEmailTrigger.manual_email_trigger_uid, ondelete="CASCADE"),
        nullable=True,
    )
    slot_date = db.Column(db.Date, nullable=False)
    slot_time = db.Column(TIME, nullable=False)
    delivery_time = db.Column(db.DateTime, nullable=False)
    slot_type = db.Column(
        db.String(100),
        CheckConstraint(
            "slot_type IN ('trigger', 'schedule')",
            name="ck_email_delivery_reports_slot_type",
        ),
        nullable=False,
    )

    __table_args__ = (
        db.PrimaryKeyConstraint(email_delivery_report_uid),
        db.UniqueConstraint(
            "manual_email_trigger_uid",
            "email_schedule_uid",
            "slot_type",
            "slot_date",
            "slot_time",
            name="email_delivery_reports_uc",
        ),
        {"schema": "webapp"},
    )

    def __init__(
        self,
        email_schedule_uid,
        manual_email_trigger_uid,
        slot_type,
        slot_date,
        slot_time,
        delivery_time,
    ):
        self.email_schedule_uid = email_schedule_uid
        self.manual_email_trigger_uid = manual_email_trigger_uid
        self.slot_type = slot_type
        self.slot_date = slot_date
        self.slot_time = slot_time
        self.delivery_time = delivery_time

    def to_dict(self):
        return {
            "email_delivery_report_uid": self.email_delivery_report_uid,
            "email_schedule_uid": self.email_schedule_uid,
            "manual_email_trigger_uid": self.manual_email_trigger_uid,
            "slot_date": self.slot_date,
            "slot_time": str(self.slot_time),
            "delivery_time": str(self.delivery_time),
            "slot_type": self.slot_type,
        }


class EmailEnumeratorDeliveryStatus(db.Model):
    __tablename__ = "email_enumerator_delivery_status"

    email_delivery_report_uid = db.Column(
        db.Integer(),
        db.ForeignKey(
            EmailDeliveryReport.email_delivery_report_uid, ondelete="CASCADE"
        ),
        nullable=False,
    )
    enumerator_uid = db.Column(
        db.Integer,
        db.ForeignKey(Enumerator.enumerator_uid, ondelete="CASCADE"),
        nullable=False,
    )
    status = db.Column(
        db.String(100),
        CheckConstraint(
            "status IN ( 'sent', 'failed')",
            name="ck_email_enumerator_status",
        ),
        nullable=False,
    )
    error_message = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.PrimaryKeyConstraint(email_delivery_report_uid, enumerator_uid),
        {"schema": "webapp"},
    )

    def __init__(
        self, email_delivery_report_uid, enumerator_uid, status, error_message
    ):
        self.email_delivery_report_uid = email_delivery_report_uid
        self.enumerator_uid = enumerator_uid
        self.status = status
        self.error_message = error_message

    def to_dict(self):
        return {
            "email_delivery_report_uid": self.email_delivery_report_uid,
            "enumerator_uid": self.enumerator_uid,
            "status": self.status,
            "error_message": self.error_message,
        }
