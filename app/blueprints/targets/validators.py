from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, IntegerField, StringField
from wtforms.validators import DataRequired, AnyOf


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
    file = StringField(validators=[DataRequired()])
    mode = StringField(
        validators=[
            AnyOf(
                ["overwrite", "merge"],
                message="Value must be one of %(values)s",
            ),
            DataRequired(),
        ]
    )


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


class UpdateTargetsColumnConfig(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    column_config = FieldList(FormField(ColumnConfigValidator))
