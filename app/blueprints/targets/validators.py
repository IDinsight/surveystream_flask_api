from flask_wtf import FlaskForm
from wtforms import BooleanField, FieldList, FormField, IntegerField, StringField
from wtforms.validators import AnyOf, DataRequired, Optional


class CustomColumnsValidator(FlaskForm):
    class Meta:
        csrf = False

    field_label = StringField(validators=[DataRequired()])
    column_name = StringField(validators=[DataRequired()])


class ColumnMappingValidator(FlaskForm):
    class Meta:
        csrf = False

    target_id = StringField(validators=[DataRequired()])
    language = StringField()
    gender = StringField()
    location_id_column = StringField()
    custom_fields = FieldList(FormField(CustomColumnsValidator))


class TargetsFileUploadValidator(FlaskForm):
    column_mapping = FormField(ColumnMappingValidator)
    file = StringField()
    mode = StringField(
        validators=[
            AnyOf(
                ["overwrite", "merge"],
                message="Value must be one of %(values)s",
            ),
            DataRequired(),
        ]
    )
    load_successful = BooleanField(validators=[Optional()], default=False)
    load_from_scto = BooleanField(validators=[Optional()], default=False)


class TargetsQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])


class BulkUpdateTargetsValidator(FlaskForm):
    target_uids = FieldList(IntegerField(), validators=[DataRequired()])
    form_uid = IntegerField(validators=[DataRequired()])
    language = StringField()
    location_uid = IntegerField()


class UpdateTarget(FlaskForm):
    target_id = StringField(validators=[DataRequired()])
    language = StringField()
    gender = StringField()
    location_uid = IntegerField()


class ColumnConfigValidator(FlaskForm):
    class Meta:
        csrf = False

    column_name = StringField(validators=[DataRequired()])
    column_type = StringField(
        AnyOf(
            ["basic_details", "location", "custom_fields"],
            message="Value must be one of %(values)s",
        ),
        validators=[DataRequired()],
    )
    column_source = StringField(validators=[DataRequired()])


class TargetSCTOFilterValidator(FlaskForm):
    variable_name = StringField(validators=[DataRequired()])
    filter_operator = StringField(
        validators=[
            DataRequired(),
            AnyOf(
                [
                    "Is",
                    "Is not",
                    "Contains",
                    "Does not contain",
                    "Is empty",
                    "Is not empty",
                    "Greather than",
                    "Smaller than",
                ],
                message="Invalid operator. Must be 'Is', 'Is not', 'Contains', 'Does not contain', 'Is empty', or 'Is not empty', 'Greather than', 'Smaller than'",
            ),
        ]
    )
    filter_value = StringField()


class TargetSCTOFilterGroupValidator(FlaskForm):
    filter_group = FieldList(FormField(TargetSCTOFilterValidator), default=[])


class UpdateTargetsColumnConfig(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    column_config = FieldList(FormField(ColumnConfigValidator))
    filters = FieldList(FormField(TargetSCTOFilterGroupValidator), default=[])


class SctoFieldsValidator(FlaskForm):
    class Meta:
        csrf = False


class TargetStatusValidator(FlaskForm):
    class Meta:
        csrf = False

    target_id = StringField(validators=[DataRequired()])
    completed_flag = BooleanField()
    refusal_flag = BooleanField()
    num_attempts = IntegerField()
    last_attempt_survey_status = IntegerField()
    last_attempt_survey_status_label = StringField()
    final_survey_status = IntegerField()
    final_survey_status_label = StringField()
    target_assignable = BooleanField()
    webapp_tag_color = StringField()
    revisit_sections = FieldList(StringField())
    scto_fields = FormField(SctoFieldsValidator)


class UpdateTargetStatus(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    target_status = FieldList(FormField(TargetStatusValidator))


class TargetConfigValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])
    target_source = StringField(
        validators=[
            AnyOf(
                ["csv", "scto"],
                message="Value must be one of %(values)s",
            ),
            DataRequired(),
        ]
    )
    scto_input_type = StringField(
        validators=[
            AnyOf(
                ["form", "dataset"],
                message="Value must be one of %(values)s",
            ),
            DataRequired(),
        ]
    )
    scto_input_id = StringField(DataRequired())
    scto_encryption_flag = BooleanField(default=False)


class TargetConfigQueryValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])


class TargetConfigSCTOColumnQueryValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])
