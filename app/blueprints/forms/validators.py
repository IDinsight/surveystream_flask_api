from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, StringField, FormField
from wtforms.validators import DataRequired, AnyOf


class GetFormQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    survey_uid = IntegerField()
    form_type = StringField(
        AnyOf(
            ["parent", "dq"],
            message="Value must be one of %(values)s",
        )
    )


class CreateFormValidator(FlaskForm):
    survey_uid = IntegerField(validators=[DataRequired()])
    scto_form_id = StringField(validators=[DataRequired()])
    form_name = StringField(validators=[DataRequired()])
    tz_name = StringField()
    scto_server_name = StringField()
    encryption_key_shared = BooleanField()
    server_access_role_granted = BooleanField()
    server_access_allowed = BooleanField()
    form_type = StringField(
        AnyOf(
            ["parent", "dq", "admin"],
            message="Value must be one of %(values)s",
        ),
        validators=[DataRequired()],
    )
    parent_form_uid = IntegerField()
    dq_form_type = StringField()
    admin_form_type = StringField()


class UpdateFormValidator(FlaskForm):
    scto_form_id = StringField(validators=[DataRequired()])
    form_name = StringField(validators=[DataRequired()])
    tz_name = StringField()
    scto_server_name = StringField()
    encryption_key_shared = BooleanField()
    server_access_role_granted = BooleanField()
    server_access_allowed = BooleanField()
    form_type = StringField(
        AnyOf(
            ["parent", "dq", "admin"],
            message="Value must be one of %(values)s",
        ),
        validators=[DataRequired()],
    )
    parent_form_uid = IntegerField()
    dq_form_type = StringField()
    admin_form_type = StringField()


class LocationQuestionMappingValidator(FlaskForm):
    class Meta:
        csrf = False


class CreateSCTOQuestionMappingValidator(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    survey_status = StringField()
    revisit_section = StringField()
    target_id = StringField()
    enumerator_id = StringField(validators=[DataRequired()])
    dq_enumerator_id = StringField()
    locations = FormField(LocationQuestionMappingValidator)


class UpdateSCTOQuestionMappingValidator(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    survey_status = StringField()
    revisit_section = StringField()
    target_id = StringField()
    enumerator_id = StringField(validators=[DataRequired()])
    dq_enumerator_id = StringField()
    locations = FormField(LocationQuestionMappingValidator)
