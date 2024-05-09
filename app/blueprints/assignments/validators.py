from flask_wtf import FlaskForm
from wtforms import IntegerField, FieldList, FormField, StringField
from wtforms.validators import DataRequired, ValidationError, AnyOf
from datetime import datetime

class SurveyorAssignmentValidator(FlaskForm):
    class Meta:
        csrf = False

    target_uid = IntegerField(validators=[DataRequired()])
    enumerator_uid = IntegerField()


class UpdateSurveyorAssignmentsValidator(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    assignments = FieldList(FormField(SurveyorAssignmentValidator))


class AssignmentsQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])


class AssignmentsEmailValidator(FlaskForm):
    date = StringField(validators=[DataRequired()])
    time = StringField(validators=[DataRequired()])
    recipients = FieldList(IntegerField(validators=[DataRequired()]))
    form_uid = IntegerField(validators=[DataRequired()])
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
