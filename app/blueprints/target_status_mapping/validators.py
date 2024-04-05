from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, IntegerField, StringField, BooleanField
from wtforms.validators import DataRequired, Optional

class TargetStatusMappingQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])
    surveying_method = StringField(validators=[DataRequired()])


class TargetStatusMappingValidator(FlaskForm):
    class Meta:
        csrf = False

    survey_status = IntegerField(validators=[DataRequired()])
    survey_status_label = StringField(validators=[DataRequired()])
    completed_flag = BooleanField(default=False, validators=[Optional()])
    refusal_flag = BooleanField(default=False, validators=[Optional()])
    target_assignable = BooleanField(default=True, validators=[Optional()])
    webapp_tag_color = StringField(validators=[DataRequired()])

class UpdateTargetStatusMapping(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    target_status_mapping = FieldList(FormField(TargetStatusMappingValidator))

