from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, IntegerField, StringField
from wtforms.validators import DataRequired, ValidationError, AnyOf
from datetime import datetime


class EmailConfigValidator(FlaskForm):
    config_type = StringField(validators=[DataRequired()])
    form_uid = IntegerField(validators=[DataRequired()])


class EmailScheduleValidator(FlaskForm):
    dates = FieldList(StringField(validators=[DataRequired()]))
    time = StringField(validators=[DataRequired()])
    email_config_uid = IntegerField(validators=[DataRequired()])

    def validate_dates(self, field):
        """
        Validate that the given date is in the future.
        """
        for date_str in field.data:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            if date_obj < datetime.now().date():
                raise ValidationError("Date must be in the future.")


class ManualEmailTriggerValidator(FlaskForm):
    date = StringField(validators=[DataRequired()])
    time = StringField(validators=[DataRequired()])
    recipients = FieldList(IntegerField(validators=[DataRequired()]))
    email_config_uid = IntegerField(validators=[DataRequired()])
    status = StringField(
        validators=[
            DataRequired(),
            AnyOf(
                ["queued", "sent", "failed"],
                message="Invalid status. Must be 'queued', 'sent', or 'failed'",
            ),
        ],
        default="queued",
    )

    def validate_date(self, field):
        """
        Validate that the given date is in the future.
        """
        date_obj = datetime.strptime(field.data, "%Y-%m-%d").date()
        if date_obj < datetime.now().date():
            raise ValidationError("Date must be in the future.")


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
