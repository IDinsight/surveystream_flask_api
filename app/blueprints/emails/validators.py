import re
from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import BooleanField, FieldList, FormField, IntegerField, StringField
from wtforms.validators import AnyOf, DataRequired, ValidationError

from app.utils.utils import JSONField


class EmailConfigValidator(FlaskForm):
    config_name = StringField(validators=[DataRequired()])
    form_uid = IntegerField(validators=[DataRequired()])
    report_users = FieldList(IntegerField(), default=[])
    email_source = StringField(
        validators=[
            DataRequired(),
            AnyOf(
                ["Google Sheet", "SurveyStream Data"],
                message="Invalid email source. Must be 'Google Sheet' or 'SurveyStream Data'",
            ),
        ],
        default="SurveyStream Data",
    )
    email_source_gsheet_link = StringField(default=None)
    email_source_gsheet_tab = StringField(default=None)
    email_source_gsheet_header_row = IntegerField(default=None)
    email_source_tablename = StringField(default=None)
    email_source_columns = FieldList(StringField(), default=[])
    cc_users = FieldList(IntegerField(), default=[])
    pdf_attachment = BooleanField(default=False)
    pdf_encryption = BooleanField(default=False)
    pdf_encryption_password_type = StringField(
        AnyOf(
            ["Pattern", "Password", None],
            message="Invalid pdf encryption password type . Must be 'Pattern' or 'Password'",
        ),
        default=None,
    )


class EmailFilterValidator(FlaskForm):

    filter_variable = StringField(validators=[DataRequired()])
    filter_operator = StringField(
        validators=[
            DataRequired(),
            AnyOf(
                [
                    "Is",
                    "Is not",
                    "Contains",
                    "Does not contain",
                    "Is empty",
                    "Is not empty",
                ],
                message="Invalid operator. Must be 'Is', 'Is Not', 'Contains', 'Does Not Contain', 'Is Empty', or 'Is Not Empty'",
            ),
        ]
    )
    filter_value = StringField()


class EmailScheduleFilterValidator(FlaskForm):
    table_name = StringField(validators=[DataRequired()])
    filter_variable = StringField(validators=[DataRequired()])
    filter_operator = StringField(
        validators=[
            DataRequired(),
            AnyOf(
                [
                    "Is",
                    "Is not",
                    "Contains",
                    "Does not contain",
                    "Is empty",
                    "Is not empty",
                ],
                message="Invalid operator. Must be 'Is', 'Is not', 'Contains', 'Does not contain', 'Is empty', or 'Is not empty'",
            ),
        ]
    )
    filter_value = StringField()


class EmailFilterGroupValidator(FlaskForm):
    filter_group = FieldList(FormField(EmailFilterValidator), default=[])


class EmailScheduleFilterGroupValidator(FlaskForm):
    filter_group = FieldList(FormField(EmailScheduleFilterValidator), default=[])


class EmailScheduleValidator(FlaskForm):
    dates = FieldList(StringField(validators=[DataRequired()]))
    time = StringField(validators=[DataRequired()])
    email_config_uid = IntegerField(validators=[DataRequired()])
    email_schedule_name = StringField(validators=[DataRequired()])
    filter_list = FieldList(FormField(EmailScheduleFilterGroupValidator), default=[])

    def validate_time(self, field):
        """
        Validate that the given time is in the future.
        """
        time_pattern = r"^\d{2}:\d{2}$"

        if not re.match(time_pattern, field.data):
            raise ValidationError("Invalid time format. Please use HH:MM format.")

    def validate_dates(self, field):
        """
        Validate that the given date is in the future.
        """
        for date_str in field.data:
            date_pattern = r"^\d{4}-\d{2}-\d{2}$"

            if not re.match(date_pattern, date_str):
                raise ValidationError(
                    "Invalid date format. Please use YYYY-MM-DD format."
                )

            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                raise ValidationError("Invalid date.")

            if date_obj < datetime.now().date():
                raise ValidationError("Date must be in the future.")


class ManualEmailTriggerValidator(FlaskForm):
    date = StringField(validators=[DataRequired()])
    time = StringField(validators=[DataRequired()])
    recipients = FieldList(IntegerField(), default=[])
    email_config_uid = IntegerField(validators=[DataRequired()])
    status = StringField(
        validators=[
            DataRequired(),
            AnyOf(
                ["queued", "sent", "failed", "running", "progress"],
                message="Invalid status. Must be 'queued', 'sent', 'progress', 'running', or 'failed'",
            ),
        ],
        default="queued",
    )

    def validate_time(self, field):
        """
        Validate that the given time is in the future.
        """
        time_pattern = r"^\d{2}:\d{2}$"

        if not re.match(time_pattern, field.data):
            raise ValidationError("Invalid time format. Please use HH:MM format.")

    def validate_date(self, field):
        """
        Validate that the given date is in the future.
        """
        date_pattern = r"^\d{4}-\d{2}-\d{2}$"

        if not re.match(date_pattern, field.data):
            raise ValidationError("Invalid date format. Please use YYYY-MM-DD format.")

        try:
            date_obj = datetime.strptime(field.data, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError("Invalid date.")

        if date_obj < datetime.now().date():
            raise ValidationError("Date must be in the future.")


class ManualEmailTriggerPatchValidator(FlaskForm):
    email_config_uid = IntegerField(validators=[DataRequired()])

    status = StringField(
        validators=[
            DataRequired(),
            AnyOf(
                ["queued", "sent", "failed", "running", "progress"],
                message="Invalid status. Must be 'queued', 'sent', 'progress', 'running', or 'failed'",
            ),
        ],
        default="queued",
    )


class EmailVariableTableColumnMappingValidator(FlaskForm):
    class Meta:
        csrf = False


class EmailVariableValidator(FlaskForm):
    class meta:
        csrf = False

    variable_name = StringField(validators=[DataRequired()])
    variable_expression = StringField(default=None)
    source_table = StringField(validators=[DataRequired()])


class EmailTemplateTableValidator(FlaskForm):

    table_name = StringField(validators=[DataRequired()])
    column_mapping = JSONField(validators=[DataRequired()])
    sort_list = JSONField()
    variable_name = StringField(validators=[DataRequired()])
    filter_list = FieldList(FormField(EmailFilterGroupValidator), default=[])


class EmailTemplateValidator(FlaskForm):
    subject = StringField(validators=[DataRequired()])
    language = StringField(validators=[DataRequired()])
    email_config_uid = IntegerField(validators=[DataRequired()])
    content = StringField(validators=[DataRequired()])
    variable_list = FieldList(FormField(EmailVariableValidator), default=[])
    table_list = FieldList(FormField(EmailTemplateTableValidator), default=[])


class EmailConfigQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])


class EmailScheduleQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    email_config_uid = IntegerField(validators=[DataRequired()])


class ManualEmailTriggerQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    email_config_uid = IntegerField(validators=[DataRequired()])


class EmailTemplateQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    email_config_uid = IntegerField(validators=[DataRequired()])


class EmailGsheetSourceParamValidator(FlaskForm):
    class Meta:
        csrf = False

    email_source_gsheet_link = StringField(validators=[DataRequired()])
    email_source_gsheet_tab = StringField(validators=[DataRequired()])
    email_source_gsheet_header_row = IntegerField(validators=[DataRequired()])


class EmailGsheetSourcePatchParamValidator(FlaskForm):
    class Meta:
        csrf = False

    email_config_uid = IntegerField(validators=[DataRequired()])


class EmailTableCatalogQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    email_config_uid = IntegerField(validators=[DataRequired()])


class EmailTableCatalogJSONValidator(FlaskForm):
    table_name = StringField(validators=[DataRequired()])
    column_name = StringField(validators=[DataRequired()])
    column_type = StringField(validators=[DataRequired()])
    column_description = StringField(default=None)


class EmailTableCatalogValidator(FlaskForm):
    survey_uid = IntegerField(validators=[DataRequired()])
    table_catalog = FieldList(FormField(EmailTableCatalogJSONValidator), default=[])
