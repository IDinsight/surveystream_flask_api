from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    validators,
    BooleanField,
    FieldList,
    IntegerField,
)
from wtforms.validators import DataRequired, Email, Optional, ValidationError


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


class AddUserValidator(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    first_name = StringField("First Name", validators=[DataRequired()])
    last_name = StringField("Last Name", validators=[DataRequired()])
    roles = FieldList(StringField("Roles"), default=[], validators=[Optional()])
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
