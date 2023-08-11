from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, IntegerField, StringField
from wtforms.validators import DataRequired, AnyOf


class SurveyGeoLevelsQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    survey_uid = IntegerField(validators=[DataRequired()])


class SurveyGeoLevelValidator(FlaskForm):
    class Meta:
        csrf = False

    geo_level_uid = IntegerField()
    geo_level_name = StringField(validators=[DataRequired()])
    parent_geo_level_uid = IntegerField()


class SurveyGeoLevelsPayloadValidator(FlaskForm):
    geo_levels = FieldList(FormField(SurveyGeoLevelValidator))


class CustomColumnsValidator(FlaskForm):
    class Meta:
        csrf = False

    field_label = StringField(validators=[DataRequired()])
    column_name = StringField(validators=[DataRequired()])


class ColumnMappingValidator(FlaskForm):
    class Meta:
        csrf = False

    enumerator_id = StringField(validators=[DataRequired()])
    name = StringField(validators=[DataRequired()])
    email = StringField(validators=[DataRequired()])
    mobile_primary = StringField(validators=[DataRequired()])
    language = StringField()
    home_address = StringField()
    gender = StringField(validators=[DataRequired()])
    enumerator_type = StringField(validators=[DataRequired()])
    location_id_column = StringField()
    custom_fields = FieldList(FormField(CustomColumnsValidator))


class EnumeratorsFileUploadValidator(FlaskForm):
    column_mapping = FormField(ColumnMappingValidator)
    file = StringField(validators=[DataRequired()])
    mode = StringField(
        validators=[
            AnyOf(["append", "overwrite"], message="Value must be one of %(values)s"),
            DataRequired(),
        ]
    )


class EnumeratorsQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])


class GetEnumeratorsQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])
    enumerator_type = StringField(
        validators=[
            AnyOf(
                ["surveyor", "monitor", None], message="Value must be one of %(values)s"
            ),
        ]
    )


class GetEnumeratorRolesQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])
    enumerator_type = StringField(
        validators=[
            AnyOf(
                ["surveyor", "monitor", None], message="Value must be one of %(values)s"
            ),
        ]
    )


class UpdateEnumerator(FlaskForm):
    enumerator_id = StringField(validators=[DataRequired()])
    name = StringField(validators=[DataRequired()])
    email = StringField(validators=[DataRequired()])
    mobile_primary = StringField(validators=[DataRequired()])
    language = StringField()
    home_address = StringField()
    gender = StringField(validators=[DataRequired()])


class UpdateSurveyorForm(FlaskForm):
    enumerator_uid = IntegerField(validators=[DataRequired()])
    form_uid = IntegerField(validators=[DataRequired()])
    surveyor_status = StringField(validators=[DataRequired()])


class UpdateSurveyorLocation(FlaskForm):
    enumerator_uid = IntegerField(validators=[DataRequired()])
    form_uid = IntegerField(validators=[DataRequired()])
    location_uid = StringField(validators=[DataRequired()])


class UpdateMonitorForm(FlaskForm):
    enumerator_uid = IntegerField(validators=[DataRequired()])
    form_uid = IntegerField(validators=[DataRequired()])
    surveyor_status = StringField(validators=[DataRequired()])


class UpdateMonitorLocation(FlaskForm):
    enumerator_uid = IntegerField(validators=[DataRequired()])
    form_uid = IntegerField(validators=[DataRequired()])
    location_uid = StringField(validators=[DataRequired()])


class CreateEnumeratorRole(FlaskForm):
    enumerator_type = StringField(
        validators=[
            AnyOf(["surveyor", "monitor"], message="Value must be one of %(values)s"),
            DataRequired(),
        ]
    )
    form_uid = IntegerField(validators=[DataRequired()])
    location_uid = StringField()


class UpdateEnumeratorRole(FlaskForm):
    enumerator_type = StringField(
        validators=[
            AnyOf(["surveyor", "monitor"], message="Value must be one of %(values)s"),
            DataRequired(),
        ]
    )
    form_uid = IntegerField(validators=[DataRequired()])
    location_uid = StringField()


class DeleteEnumeratorRole(FlaskForm):
    enumerator_type = StringField(
        validators=[
            AnyOf(["surveyor", "monitor"], message="Value must be one of %(values)s"),
            DataRequired(),
        ]
    )
    form_uid = IntegerField(validators=[DataRequired()])


class UpdateEnumeratorRoleStatus(FlaskForm):
    enumerator_type = StringField(
        validators=[
            AnyOf(["surveyor", "monitor"], message="Value must be one of %(values)s"),
            DataRequired(),
        ]
    )
    form_uid = IntegerField(validators=[DataRequired()])
    status = StringField(
        validators=[
            AnyOf(
                ["Active", "Dropout", "Temp. Inactive"],
                message="Value must be one of %(values)s",
            ),
            DataRequired(),
        ]
    )
