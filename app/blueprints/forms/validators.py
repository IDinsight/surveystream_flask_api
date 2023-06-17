from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, StringField, FormField
from wtforms.validators import InputRequired


class GetParentFormQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    survey_uid = IntegerField(validators=[InputRequired()])


class CreateParentFormValidator(FlaskForm):
    survey_uid = IntegerField(validators=[InputRequired()])
    scto_form_id = StringField(validators=[InputRequired()])
    form_name = StringField(validators=[InputRequired()])
    tz_name = StringField()
    scto_server_name = StringField()
    encryption_key_shared = BooleanField()
    server_access_role_granted = BooleanField()
    server_access_allowed = BooleanField()


class UpdateParentFormValidator(FlaskForm):
    scto_form_id = StringField(validators=[InputRequired()])
    form_name = StringField(validators=[InputRequired()])
    tz_name = StringField()
    scto_server_name = StringField()
    encryption_key_shared = BooleanField()
    server_access_role_granted = BooleanField()
    server_access_allowed = BooleanField()


class DeleteParentFormValidator(FlaskForm):
    pass


class LocationQuestionMappingValidator(FlaskForm):
    class Meta:
        csrf = False


class CreateSCTOQuestionMappingValidator(FlaskForm):
    form_uid = IntegerField(validators=[InputRequired()])
    survey_status = StringField(validators=[InputRequired()])
    revisit_section = StringField(validators=[InputRequired()])
    target_id = StringField(validators=[InputRequired()])
    enumerator_id = StringField(validators=[InputRequired()])
    locations = FormField(LocationQuestionMappingValidator)


class UpdateSCTOQuestionMappingValidator(FlaskForm):
    form_uid = IntegerField(validators=[InputRequired()])
    survey_status = StringField(validators=[InputRequired()])
    revisit_section = StringField(validators=[InputRequired()])
    target_id = StringField(validators=[InputRequired()])
    enumerator_id = StringField(validators=[InputRequired()])
    locations = FormField(LocationQuestionMappingValidator)


class DeleteSCTOQuestionMappingValidator(FlaskForm):
    pass


class IngestSCTOFormDefinitionValidator(FlaskForm):
    pass


class DeleteSCTOFormDefinitionValidator(FlaskForm):
    pass
