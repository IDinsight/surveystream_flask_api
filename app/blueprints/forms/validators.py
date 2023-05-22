from flask_wtf import FlaskForm
from wtforms import BooleanField, FieldList, IntegerField, StringField
from wtforms.validators import DataRequired
from flask import jsonify, request

class ParentFlaskForm(FlaskForm):
    survey_uid = IntegerField(validators=[DataRequired()])

    scto_form_id = StringField(validators=[DataRequired()])
    form_name = StringField(validators=[DataRequired()])


    tz_name = StringField()
    scto_server_name = StringField()
    encryption_key_shared = BooleanField()

    server_access_role_granted = BooleanField()
    server_access_allowed = BooleanField()
    scto_variables_fetched = BooleanField()

    def validate(self):
        if not super().validate():
            return False

        return True
    
class ParentFormVarableMapping(FlaskForm):

    def validate(self):
        if not super().validate():
            return False

        if 'target_id' not in self.scto_variable_mapping.data.keys():
            self.errors[
                "target_id"
            ] = 'Target ID mapping is required'
            return False


        if 'enumerator_id' not in self.scto_variable_mapping.data.keys():
            self.errors[
                "enumerator_id"
            ] = 'Enumerator ID mapping is required'
            return False

        return True
