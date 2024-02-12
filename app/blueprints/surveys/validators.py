from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, DateField
from wtforms.validators import DataRequired, AnyOf
from wtforms import ValidationError


class CreateSurveyValidator(FlaskForm):
    survey_id = StringField(validators=[DataRequired()])
    survey_name = StringField(validators=[DataRequired()])
    project_name = StringField()
    survey_description = StringField()
    surveying_method = StringField(
        validators=[
            DataRequired(),
            AnyOf(
                ["in-person", "phone", "mixed-mode"],
                message="Value must be one of %(values)s",
            ),
        ]
    )
    irb_approval = StringField(
        validators=[
            DataRequired(),
            AnyOf(["Yes", "No", "Pending"], message="Value must be one of %(values)s"),
        ]
    )
    planned_start_date = DateField(validators=[DataRequired()], format="%Y-%m-%d")
    planned_end_date = DateField(validators=[DataRequired()], format="%Y-%m-%d")
    state = StringField(
        validators=[
            AnyOf(
                ["Draft", "Active", "Past"], message="Value must be one of %(values)s"
            )
        ]
    )
    prime_geo_level_uid = IntegerField()
    config_status = StringField(
        validators=[
            AnyOf(
                [
                    "In Progress - Configuration",
                    "In Progress - Backend Setup",
                    "Done",
                ],
                message="Value must be one of %(values)s",
            )
        ]
    )

    def validate_planned_end_date(form, planned_end_date):
        if planned_end_date.data < form.planned_start_date.data:
            raise ValidationError(
                "planned_end_date cannot be earlier than planned_start_date"
            )


class UpdateSurveyValidator(FlaskForm):
    survey_uid = IntegerField(validators=[DataRequired()])
    survey_id = StringField(validators=[DataRequired()])
    survey_name = StringField(validators=[DataRequired()])
    project_name = StringField()
    survey_description = StringField()
    surveying_method = StringField(
        validators=[
            DataRequired(),
            AnyOf(
                ["in-person", "phone", "mixed-mode"],
                message="Value must be one of %(values)s",
            ),
        ]
    )
    irb_approval = StringField(
        validators=[
            DataRequired(),
            AnyOf(["Yes", "No", "Pending"], message="Value must be one of %(values)s"),
        ]
    )
    planned_start_date = DateField(validators=[DataRequired()], format="%Y-%m-%d")
    planned_end_date = DateField(validators=[DataRequired()], format="%Y-%m-%d")
    state = StringField(
        validators=[
            AnyOf(
                ["Draft", "Active", "Past"], message="Value must be one of %(values)s"
            )
        ]
    )
    prime_geo_level_uid = IntegerField()
    config_status = StringField(
        validators=[
            AnyOf(
                [
                    "In Progress - Configuration",
                    "In Progress - Backend Setup",
                    "Done",
                ],
                message="Value must be one of %(values)s",
            )
        ]
    )

    def validate_planned_end_date(form, planned_end_date):
        if planned_end_date.data < form.planned_start_date.data:
            raise ValidationError(
                "planned_end_date cannot be earlier than planned_start_date"
            )
