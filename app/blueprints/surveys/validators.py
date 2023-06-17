from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, DateField
from wtforms.validators import InputRequired, AnyOf
from wtforms import ValidationError


class GetSurveyQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    user_uid = IntegerField(validators=[InputRequired()])


class CreateSurveyValidator(FlaskForm):
    survey_id = StringField(validators=[InputRequired()])
    survey_name = StringField(validators=[InputRequired()])
    project_name = StringField()
    survey_description = StringField()
    surveying_method = StringField(
        validators=[
            InputRequired(),
            AnyOf(["in-person", "phone"], message="Value must be one of %(values)s"),
        ]
    )
    irb_approval = StringField(
        validators=[
            InputRequired(),
            AnyOf(["Yes", "No", "Pending"], message="Value must be one of %(values)s"),
        ]
    )
    planned_start_date = DateField(validators=[InputRequired()], format="%Y-%m-%d")
    planned_end_date = DateField(validators=[InputRequired()], format="%Y-%m-%d")
    state = StringField(
        validators=[
            AnyOf(
                ["Draft", "Active", "Past"], message="Value must be one of %(values)s"
            )
        ]
    )
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
    created_by_user_uid = IntegerField(validators=[InputRequired()])

    def validate_planned_end_date(form, planned_end_date):
        if planned_end_date.data < form.planned_start_date.data:
            raise ValidationError(
                "planned_end_date cannot be earlier than planned_start_date"
            )


class UpdateSurveyValidator(FlaskForm):
    survey_uid = IntegerField(validators=[InputRequired()])
    survey_id = StringField(validators=[InputRequired()])
    survey_name = StringField(validators=[InputRequired()])
    project_name = StringField()
    survey_description = StringField()
    surveying_method = StringField(
        validators=[
            InputRequired(),
            AnyOf(["in-person", "phone"], message="Value must be one of %(values)s"),
        ]
    )
    irb_approval = StringField(
        validators=[
            InputRequired(),
            AnyOf(["Yes", "No", "Pending"], message="Value must be one of %(values)s"),
        ]
    )
    planned_start_date = DateField(validators=[InputRequired()], format="%Y-%m-%d")
    planned_end_date = DateField(validators=[InputRequired()], format="%Y-%m-%d")
    state = StringField(
        validators=[
            AnyOf(
                ["Draft", "Active", "Past"], message="Value must be one of %(values)s"
            )
        ]
    )
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
