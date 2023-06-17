from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, IntegerField, StringField
from wtforms.validators import InputRequired


class SurveyRolesQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    survey_uid = IntegerField(validators=[InputRequired()])


class SurveyRoleValidator(FlaskForm):
    class Meta:
        csrf = False

    role_uid = IntegerField()
    role_name = StringField(validators=[InputRequired()])
    reporting_role_uid = IntegerField()


class SurveyRolesPayloadValidator(FlaskForm):
    roles = FieldList(FormField(SurveyRoleValidator))
