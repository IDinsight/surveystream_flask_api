from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, IntegerField, StringField
from wtforms.validators import DataRequired, ValidationError, AnyOf
from datetime import datetime


class EmailScheduleValidator(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    dates = FieldList(StringField(validators=[DataRequired()]))
    time = StringField(validators=[DataRequired()])
    template_uid = IntegerField(validators=[DataRequired()])

    def validate_dates(self, field):
        """
        Validate that the given date is in the future.
        """
        for date_str in field.data:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            if date_obj < datetime.now().date():
                raise ValidationError("Date must be in the future.")

class ManualEmailTriggerValidator(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    date = StringField(validators=[DataRequired()])
    time = StringField(validators=[DataRequired()])
    recipients = FieldList(IntegerField(validators=[DataRequired()]))
    template_uid = IntegerField(validators=[DataRequired()])
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

    template_name = StringField(validators=[DataRequired()])
    subject = StringField(validators=[DataRequired()])
    sender_email = StringField(validators=[DataRequired()])
    content = StringField(validators=[DataRequired()])


class EmailScheduleQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])


class ManualEmailTriggerQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])
