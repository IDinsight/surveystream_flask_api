from flask_wtf import FlaskForm
from wtforms import IntegerField, FieldList, FormField
from wtforms.validators import InputRequired


class SurveyorAssignmentValidator(FlaskForm):
    class Meta:
        csrf = False

    target_uid = IntegerField(validators=[InputRequired()])
    enumerator_uid = IntegerField()


class UpdateSurveyorAssignmentsValidator(FlaskForm):
    assignments = FieldList(FormField(SurveyorAssignmentValidator))
