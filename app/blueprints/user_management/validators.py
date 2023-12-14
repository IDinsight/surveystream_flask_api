from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, validators, SelectMultipleField, BooleanField, FieldList, IntegerField
from wtforms.validators import DataRequired, Email, Optional


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
    roles = FieldList(IntegerField(default=[], validators=[Optional()]))
    is_super_admin = BooleanField("Is Super Admin", default=False, validators=[Optional()])


class CompleteRegistrationValidator(FlaskForm):
    invite_code = StringField("Invite Code", validators=[DataRequired()])
    new_password = PasswordField("New Password", [
        validators.DataRequired(),
        validators.Length(min=8)
    ])
    confirm_password = PasswordField("Confirm Password", [
        validators.DataRequired(),
        validators.EqualTo("new_password", message="Passwords must match")
    ])


class EditUserValidator(FlaskForm):
    email = StringField("Email", validators=[Email(), DataRequired()])
    first_name = StringField("First Name", validators=[DataRequired()])
    last_name = StringField("Last Name", validators=[DataRequired()])
    roles = FieldList(IntegerField("Roles",default=[], validators=[Optional()]))

    is_super_admin = BooleanField("Is Super Admin", default=False, validators=[Optional()])
    # Add fields for permissions if needed
    permissions = FieldList(IntegerField("Permissions",default=[], validators=[Optional()]))
