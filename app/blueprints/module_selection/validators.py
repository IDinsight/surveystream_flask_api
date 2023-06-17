from wtforms import StringField, validators, FieldList
from flask_wtf import FlaskForm


class UpdateModuleStatusValidator(FlaskForm):
    config_status = StringField(validators=[validators.DataRequired()])

    def validate(self, status):
        if not super().validate():
            return False

        if status is None:
            self.errors["status"] = ["Module status not found."]
            return False

        return True


class AddModuleStatusValidator(FlaskForm):
    survey_uid = StringField(validators=[validators.DataRequired()])
    modules = FieldList(StringField(), validators=[validators.DataRequired()])

    def validate(self):
        if not super().validate():
            return False

        return True
