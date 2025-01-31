from wtforms import StringField, FieldList, IntegerField
from flask_wtf import FlaskForm
from wtforms.validators import DataRequired


class UpdateModuleStatusValidator(FlaskForm):
    survey_uid = IntegerField(validators=[DataRequired()])
    module_id = IntegerField(validators=[DataRequired()])
    config_status = StringField(validators=[DataRequired()])

    def validate(self, status):
        if not super().validate():
            return False

        if status is None:
            self.errors["status"] = ["Module status not found."]
            return False

        if self.config_status.data not in [
            "Done",
            "In Progress",
            "Not Started",
            "Error",
            "Live",
        ]:
            self.errors["config_status"] = ["Invalid module status."]
            return False

        return True


class AddModuleStatusValidator(FlaskForm):
    survey_uid = IntegerField(validators=[DataRequired()])
    modules = FieldList(IntegerField(), validators=[DataRequired()])

    def validate(self):
        if not super().validate():
            return False

        return True
