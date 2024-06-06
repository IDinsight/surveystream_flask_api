import re
from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, IntegerField, StringField
from wtforms.validators import AnyOf, DataRequired, ValidationError


class EmailConfigValidator(FlaskForm):
    config_type = StringField(validators=[DataRequired()])
    form_uid = IntegerField(validators=[DataRequired()])


class EmailScheduleValidator(FlaskForm):
    dates = FieldList(StringField(validators=[DataRequired()]))
    time = StringField(validators=[DataRequired()])
    email_config_uid = IntegerField(validators=[DataRequired()])
    email_schedule_name = StringField(validators=[DataRequired()])

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


class EmailTemplateValidator(FlaskForm):
    subject = StringField(validators=[DataRequired()])
    language = StringField(validators=[DataRequired()])
    email_config_uid = IntegerField(validators=[DataRequired()])
    content = StringField(validators=[DataRequired()])


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
