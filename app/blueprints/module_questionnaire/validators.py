from flask_wtf import FlaskForm
from wtforms import BooleanField, FieldList, IntegerField, StringField
from wtforms.validators import DataRequired


class ModuleQuestionnaireForm(FlaskForm):
    survey_uid = IntegerField(validators=[DataRequired()])

    target_assignment_criteria = FieldList(StringField(validators=[]), validators=[])
    target_mapping_criteria = FieldList(StringField(validators=[]), validators=[])
    surveyor_mapping_criteria = FieldList(StringField(validators=[]), validators=[])
    supervisor_hierarchy_exists = BooleanField()
    reassignment_required = BooleanField()
    assignment_process = StringField()
    supervisor_surveyor_relation = StringField()
    language_location_mapping = BooleanField()

    def validate(self):
        if not super().validate():
            return False
        return True
