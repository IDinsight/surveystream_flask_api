from flask_wtf import FlaskForm
from wtforms import BooleanField, FieldList, FormField, IntegerField, StringField
from wtforms.validators import AnyOf, DataRequired, Optional


class MappingCriteriaValuesValidator(FlaskForm):
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


class MappingConfigValidator(FlaskForm):
    class Meta:
        csrf = False

    mapping_values = FieldList(FormField(MappingCriteriaValuesValidator))
    mapped_to = FieldList(FormField(MappingCriteriaValuesValidator))


class UpdateMappingConfigValidator(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    mapping_config = FieldList(FormField(MappingConfigValidator))


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
