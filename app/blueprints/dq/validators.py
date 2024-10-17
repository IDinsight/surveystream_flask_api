from flask_wtf import FlaskForm
from wtforms import FieldList, IntegerField
from wtforms.validators import DataRequired

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

    survey_uid = Form.query.filter_by(form_uid=form_uid).first().survey_uid
    surveying_method = (
        Survey.query.filter_by(survey_uid=survey_uid).first().surveying_method
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
        field.data = [field.data]

    for value in field.data:
        if value not in check_types:
            raise ValueError(f"Invalid check type {value}")


class UpdateDQConfigValidator(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    survey_status_filter = FieldList(
        IntegerField(), validators=[DataRequired(), validate_survey_status_filter]
    )

    paused_check_types = FieldList(IntegerField(), validators=[validate_check_type])
