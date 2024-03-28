from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, IntegerField, StringField
from wtforms.validators import DataRequired, ValidationError
from datetime import datetime


class EmailScheduleValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])
    date = FieldList(StringField(validators=[DataRequired()]))
    time = StringField(validators=[DataRequired()])
    template_uid = IntegerField(validators=[DataRequired()])

    def validate_date(self, field):
        """
        Validate that the given date is in the future.
        """
        for date_str in field.data:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            if date_obj < datetime.now().date():
                raise ValidationError("Date must be in the future.")


class ManualEmailTriggerValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])
    date = StringField(validators=[DataRequired()])
    time = StringField(validators=[DataRequired()])
    recipients = FieldList(IntegerField(validators=[DataRequired()]))
    template_uid = IntegerField(validators=[DataRequired()])
    status = StringField(validators=[DataRequired()])

    def validate_date(self, field):
        """
        Validate that the given date is in the future.
        """
        for date_str in field.data:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            if date_obj < datetime.now().date():
                raise ValidationError("Date must be in the future.")


class EmailTemplateValidator(FlaskForm):
    class Meta:
        csrf = False

    template_name = StringField(validators=[DataRequired()])
    subject = StringField(validators=[DataRequired()])
    sender_email = StringField(validators=[DataRequired()])
    content = StringField(validators=[DataRequired()])
