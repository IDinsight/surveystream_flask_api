from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    FieldList,
    FormField,
    IntegerField,
    StringField,
)
from wtforms.validators import AnyOf, DataRequired, Optional

from app.blueprints.forms.models import Form
from app.blueprints.surveys.models import Survey
from app.blueprints.target_status_mapping.models import (
    DefaultTargetStatusMapping,
    TargetStatusMapping,
)

from .models import DQCheckTypes


class DQConfigQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])


def validate_survey_status_filter(form, field):
    """
    Custom validator to validate that the survey status filter values are valid

    """

    form_uid = form.form_uid.data

    form_data = Form.query.filter_by(form_uid=form_uid).first()
    if form_data is None:
        raise ValueError(f"Form with form_uid {form_uid} not found")

    surveying_method = (
        Survey.query.filter_by(survey_uid=form_data.survey_uid).first().surveying_method
    )

    # Fetch allowed survey status values
    survey_status_values = [
        status.survey_status
        for status in TargetStatusMapping.query.filter_by(
            form_uid=form.form_uid.data
        ).all()
    ]
    if len(survey_status_values) == 0:
        survey_status_values = [
            status.survey_status
            for status in DefaultTargetStatusMapping.query.filter_by(
                surveying_method=surveying_method
            ).all()
        ]

    for value in field.data:
        if value not in survey_status_values:
            raise ValueError(f"Invalid survey status value {value}")


def validate_check_type(form, field):
    """
    Custom validator to validate that the check types provided are valid

    """

    check_types = [check_type.type_id for check_type in DQCheckTypes.query.all()]

    if isinstance(field.data, int):
        if field.data not in check_types:
            raise ValueError(f"Invalid check type {value}")
    else:
        for value in field.data:
            if value not in check_types:
                raise ValueError(f"Invalid check type {value}")


class UpdateDQConfigValidator(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    survey_status_filter = FieldList(
        IntegerField(), validators=[DataRequired(), validate_survey_status_filter]
    )
    group_by_module_name = BooleanField(default=False)
    drop_duplicates = BooleanField(default=False)


class DQChecksQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])
    type_id = IntegerField(validators=[DataRequired(), validate_check_type])


class DQCheckFilterValidator(FlaskForm):
    question_name = StringField(validators=[DataRequired()])
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
                    "Greater than",
                    "Smaller than",
                ],
                message="Invalid operator. Must be 'Is', 'Is not', 'Contains', 'Does not contain', 'Is empty', or 'Is not empty', 'Greater than', 'Smaller than'",
            ),
        ]
    )
    filter_value = StringField()


class DQCheckLogicAssertGroupValidator(FlaskForm):
    assertion = StringField(validators=[DataRequired()])


class DQCheckFilterGroupValidator(FlaskForm):
    filter_group = FieldList(FormField(DQCheckFilterValidator), default=[])


class DQCheckLogicAssertionValidator(FlaskForm):
    assert_group = FieldList(FormField(DQCheckLogicAssertGroupValidator), default=[])


class DQCheckLogicQuestionValidator(FlaskForm):
    question_name = StringField(validators=[DataRequired()])
    alias = StringField(validators=[DataRequired()])


class CustomCheckComponentValidator(FlaskForm):
    class Meta:
        csrf = False

    value = FieldList(StringField(), validators=[Optional()])
    hard_min = StringField(validators=[Optional()])
    hard_max = StringField(validators=[Optional()])
    soft_min = StringField(validators=[Optional()])
    soft_max = StringField(validators=[Optional()])
    outlier_metric = StringField(
        AnyOf(
            ["interquartile_range", "standard_deviation", "percentile"],
            message="Value must be one of %(values)s",
        ),
        validators=[Optional()],
    )
    outlier_value = StringField(validators=[Optional()])
    spotcheck_score_name = StringField(validators=[Optional()])
    gps_type = StringField(
        AnyOf(
            ["point2point", "point2shape"],
            message="Value must be one of %(values)s",
        ),
        validators=[Optional()],
    )
    threshold = StringField(validators=[Optional()])
    gps_variable = StringField(validators=[Optional()])
    grid_id = StringField(validators=[Optional()])
    logic_check_questions = FieldList(FormField(DQCheckLogicQuestionValidator))
    logic_check_assertions = FieldList(FormField(DQCheckLogicAssertionValidator))


class DQCheckValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])
    type_id = IntegerField(validators=[DataRequired(), validate_check_type])
    all_questions = BooleanField(default=False)
    question_name = StringField()
    dq_scto_form_uid = IntegerField()
    module_name = StringField()
    flag_description = StringField()
    check_components = FormField(CustomCheckComponentValidator, default={})
    active = BooleanField(default=True)

    filters = FieldList(FormField(DQCheckFilterGroupValidator), default=[])


class UpdateDQChecksStateValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])
    type_id = IntegerField(validators=[DataRequired(), validate_check_type])

    check_uids = FieldList(IntegerField(), validators=[DataRequired()])


class DQModuleNamesQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])
