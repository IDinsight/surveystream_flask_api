from flask_wtf import FlaskForm
from wtforms import BooleanField, FieldList, FormField, IntegerField, StringField
from wtforms.validators import AnyOf, DataRequired


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


class CustomColumnBulkUpdateValidator(FlaskForm):
    class Meta:
        csrf = False

    field_label = StringField(validators=[DataRequired()])
    value = StringField()


class ColumnMappingValidator(FlaskForm):
    class Meta:
        csrf = False

    enumerator_id = StringField(validators=[DataRequired()])
    name = StringField(validators=[DataRequired()])
    email = StringField(validators=[DataRequired()])
    mobile_primary = StringField(validators=[DataRequired()])
    language = StringField(validators=[DataRequired()])
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
            AnyOf(["overwrite", "merge"], message="Value must be one of %(values)s"),
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


class BulkUpdateEnumeratorsValidator(FlaskForm):
    enumerator_uids = FieldList(IntegerField(), validators=[DataRequired()])
    form_uid = IntegerField(validators=[DataRequired()])


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


class BulkUpdateEnumeratorsRoleLocationValidator(FlaskForm):
    enumerator_uids = FieldList(IntegerField(), validators=[DataRequired()])
    form_uid = IntegerField(validators=[DataRequired()])
    enumerator_type = StringField(
        validators=[
            AnyOf(
                ["surveyor", "monitor", None], message="Value must be one of %(values)s"
            ),
            DataRequired(),
        ]
    )
    location_uids = FieldList(IntegerField())


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


class ColumnConfigValidator(FlaskForm):
    class Meta:
        csrf = False

    column_name = StringField(validators=[DataRequired()])
    column_type = StringField(
        AnyOf(
            ["personal_details", "location", "custom_fields"],
            message="Value must be one of %(values)s",
        ),
        validators=[DataRequired()],
    )


class UpdateEnumeratorsColumnConfig(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    column_config = FieldList(FormField(ColumnConfigValidator))


class EnumeratorColumnConfigQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])


class SurveyorStatsValidator(FlaskForm):
    class Meta:
        csrf = False

    enumerator_id = StringField(validators=[DataRequired()])
    avg_num_submissions_per_day = IntegerField()
    avg_num_completed_per_day = IntegerField()


class UpdateSurveyorStats(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    surveyor_stats = FieldList(FormField(SurveyorStatsValidator))


class SurveyorStatsQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])


class EnumeratorLanguageQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])
