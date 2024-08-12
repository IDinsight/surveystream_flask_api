from flask_wtf import FlaskForm
from wtforms import BooleanField, FieldList, FormField, IntegerField, StringField
from wtforms.validators import AnyOf, DataRequired, Optional


class MappingConfigValidator(FlaskForm):
    class Meta:
        csrf = False

    criteria = StringField(
        validators=[
            AnyOf(
                ["Location", "Gender", "Language"],
                message="Value must be one of %(values)s",
            ),
            DataRequired(),
        ]
    )
    value = StringField(validators=[DataRequired()])


class MappingConfigQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])


class GetMappingParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])


class TargetMappingConfigValidator(FlaskForm):
    class Meta:
        csrf = False

    mapping_values = FieldList(FormField(MappingConfigValidator))
    mapped_to = FieldList(FormField(MappingConfigValidator))


class UpdateTargetMappingConfigValidator(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    target_mapping_config = FieldList(FormField(TargetMappingConfigValidator))


class GetMappingQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])


class TargetMappingValidator(FlaskForm):
    class Meta:
        csrf = False

    target_uid = IntegerField(validators=[DataRequired()])
    supervisor_uid = IntegerField()


class UpdateTargetMappingValidator(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    mappings = FieldList(FormField(TargetMappingValidator))
