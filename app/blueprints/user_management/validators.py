from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    FieldList,
    IntegerField,
    PasswordField,
    StringField,
    validators,
)
from wtforms.validators import DataRequired, Email, Optional, ValidationError

from app.blueprints.auth.models import User
from app.blueprints.locations.models import Location
from app.blueprints.surveys.models import Survey


class GetUsersQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    survey_uid = IntegerField()


class RegisterValidator(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])


class WelcomeUserValidator(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])


class CheckUserValidator(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    survey_uid = IntegerField("survey_uid", validators=[Optional()], default=None)


def validate_locations(form, field):
    """
    Custom validator to validate that the locations provided are prime geo level locations.
    """
    # Get the prime geo level from the survey configuration
    prime_geo_level_uid = (
        Survey.query.filter_by(survey_uid=form.survey_uid.data)
        .first()
        .prime_geo_level_uid
    )
    if not prime_geo_level_uid:
        raise ValidationError(
            "A prime geo level must be defined for the survey for user location mapping."
        )

    for location_uid in field.data:
        location = Location.query.get(location_uid)
        if not location:
            raise ValidationError(f"Location with UID {location_uid} does not exist.")

        if location.geo_level_uid != prime_geo_level_uid:
            raise ValidationError(
                f"Location with UID {location_uid} is not a prime geo level location."
            )


class AddUserValidator(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    first_name = StringField("First Name", validators=[DataRequired()])
    last_name = StringField("Last Name", validators=[DataRequired()])
    roles = FieldList(StringField("Roles"), default=[], validators=[Optional()])

    gender = StringField("Gender", validators=[Optional()])
    languages = FieldList(StringField("Language"), default=[], validators=[Optional()])
    location_uids = FieldList(
        IntegerField("Location"),
        default=[],
        validators=[Optional(), validate_locations],
    )

    is_super_admin = BooleanField(
        "is_super_admin", default=False, validators=[Optional()]
    )
    can_create_survey = BooleanField(
        "can_create_survey", default=False, validators=[Optional()]
    )

    is_survey_admin = BooleanField(
        "is_survey_admin", default=False, validators=[Optional()]
    )
    survey_uid = IntegerField("survey_uid", validators=[Optional()], default=None)

    def validate_survey_uid(self, field):
        if self.is_survey_admin.data and not field.data:
            raise ValidationError("Survey UID is required if user is a survey admin.")


class EditUserValidator(FlaskForm):
    email = StringField("Email", validators=[Email(), DataRequired()])
    first_name = StringField("First Name", validators=[DataRequired()])
    last_name = StringField("Last Name", validators=[DataRequired()])
    roles = FieldList(StringField("Roles"), default=[], validators=[Optional()])
    gender = StringField("Gender", validators=[Optional()])
    languages = FieldList(StringField("Language"), default=[], validators=[Optional()])
    location_uids = FieldList(
        IntegerField("Location"),
        default=[],
        validators=[Optional(), validate_locations],
    )
    is_super_admin = BooleanField(
        "Is Super Admin", default=False, validators=[Optional()]
    )
    can_create_survey = BooleanField(
        "Can Create Survey", default=False, validators=[Optional()]
    )

    is_survey_admin = BooleanField(
        "is_survey_admin", default=False, validators=[Optional()]
    )
    survey_uid = IntegerField("survey_uid", validators=[Optional()], default=None)
    active = BooleanField()

    def validate_survey_uid(self, field):
        if self.is_survey_admin.data and not field.data:
            raise ValidationError("Survey UID is required if user is a survey admin.")


class CompleteRegistrationValidator(FlaskForm):
    invite_code = StringField("Invite Code", validators=[DataRequired()])
    new_password = PasswordField(
        "New Password", [validators.DataRequired(), validators.Length(min=8)]
    )
    confirm_password = PasswordField(
        "Confirm Password",
        [
            validators.DataRequired(),
            validators.EqualTo("new_password", message="Passwords must match"),
        ],
    )


class UserLocationsParamValidator(FlaskForm):
    class Meta:
        csrf = False

    survey_uid = IntegerField(validators=[DataRequired()])
    user_uid = IntegerField(validators=[DataRequired()])


class UserLocationsPayloadValidator(FlaskForm):
    survey_uid = IntegerField(validators=[DataRequired()])
    user_uid = IntegerField(validators=[DataRequired()])
    location_uids = FieldList(
        IntegerField(), validators=[DataRequired(), validate_locations]
    )

    def validate_survey_uid(form, field):
        survey = Survey.query.get(field.data)
        if not survey:
            raise ValidationError(f"Survey with UID {field.data} does not exist.")

    def validate_user_uid(form, field):
        user = User.query.get(field.data)
        if not user:
            raise ValidationError(f"User with UID {field.data} does not exist.")
