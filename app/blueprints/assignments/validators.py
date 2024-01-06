from flask_wtf import FlaskForm
from wtforms import IntegerField, FieldList, FormField
from wtforms.validators import DataRequired


class SurveyorAssignmentValidator(FlaskForm):
    class Meta:
        csrf = False

    target_uid = IntegerField(validators=[DataRequired()])
    enumerator_uid = IntegerField()


class UpdateSurveyorAssignmentsValidator(FlaskForm):
    assignments = FieldList(FormField(SurveyorAssignmentValidator))


class AssignmentsQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])
