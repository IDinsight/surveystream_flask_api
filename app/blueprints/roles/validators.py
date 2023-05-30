from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, IntegerField, StringField
from wtforms.validators import DataRequired


class SurveyRolesQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False
    
    survey_uid = IntegerField(validators=[DataRequired()])

    def validate(self):
        if not super().validate():
            return False

        return True


class SurveyRoleValidator(FlaskForm):
    class Meta:
        csrf = False

    role_uid = IntegerField()
    role_name = StringField(validators=[DataRequired()])
    reporting_role_uid = IntegerField()



class SurveyRolesPayloadValidator(FlaskForm):
    roles = FieldList(FormField(SurveyRoleValidator))
