from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, StringField
from wtforms.validators import DataRequired


class CreateParentFormValidator(FlaskForm):
    survey_uid = IntegerField(validators=[DataRequired()])
    scto_form_id = StringField(validators=[DataRequired()])
    form_name = StringField(validators=[DataRequired()])
    tz_name = StringField()
    scto_server_name = StringField()
    encryption_key_shared = BooleanField()
    server_access_role_granted = BooleanField()
    server_access_allowed = BooleanField()
    scto_variable_mapping = StringField()


class UpdateParentFormValidator(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    scto_form_id = StringField(validators=[DataRequired()])
    form_name = StringField(validators=[DataRequired()])
    tz_name = StringField()
    scto_server_name = StringField()
    encryption_key_shared = BooleanField()
    server_access_role_granted = BooleanField()
    server_access_allowed = BooleanField()
    scto_variable_mapping = StringField()


class ParentFormVarableMapping(FlaskForm):
    def validate(self):
        if not super().validate():
            return False

        if "target_id" not in self.scto_variable_mapping.data.keys():
            self.errors["target_id"] = "Target ID mapping is required"
            return False

        if "enumerator_id" not in self.scto_variable_mapping.data.keys():
            self.errors["enumerator_id"] = "Enumerator ID mapping is required"
            return False

        return True
