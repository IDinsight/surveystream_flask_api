from flask_wtf import FlaskForm
from wtforms import BooleanField, FieldList, IntegerField, StringField
from wtforms.validators import InputRequired


class ModuleQuestionnaireForm(FlaskForm):
    survey_uid = IntegerField(validators=[InputRequired()])

    target_assignment_criteria = FieldList(StringField(validators=[]), validators=[])
    supervisor_assignment_criteria = FieldList(
        StringField(validators=[]), validators=[]
    )
    supervisor_hierarchy_exists = BooleanField()
    reassignment_required = BooleanField()
    assignment_process = StringField()
    supervisor_surveyor_relation = StringField()
    language_location_mapping = BooleanField()

    def validate(self):
        if not super().validate():
            return False

        if self.assignment_process.data not in ["Random", "Manual"]:
            self.errors[
                "assignment_process"
            ] = 'Assignment process not in ("Random", "Manual")'
            return False

        if self.supervisor_surveyor_relation.data not in [
            "1:1",
            "1:many",
            "many:1",
            "many:many",
        ]:
            self.errors[
                "supervisor_surveyor_relation"
            ] = 'Supervisor Surveyor relation not in ("1:1","1:many","many:1","many:many")'
            return False

        return True
