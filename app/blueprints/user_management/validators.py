from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, Form, validators,SelectMultipleField
from wtforms.validators import DataRequired, Email, Optional

class RegisterValidator(FlaskForm):
    email = StringField(validators=[DataRequired()])
    password = PasswordField(validators=[DataRequired()])


class WelcomeUserValidator(FlaskForm):
    email = StringField(validators=[DataRequired()])

class AddUserValidator(FlaskForm):
    email = StringField(validators=[DataRequired()])
    first_name = StringField(validators=[DataRequired()])
    last_name = StringField(validators=[DataRequired()])
    role = StringField(validators=[DataRequired()])

class CompleteRegistrationValidator(Form):
    invite_code = StringField("Invite Code", [validators.InputRequired()])
    new_password = PasswordField("New Password", [validators.InputRequired(), validators.Length(min=8)])
    confirm_password = PasswordField("Confirm Password", [validators.EqualTo("new_password", message="Passwords must match")])


class EditUserValidator(FlaskForm):
    email = StringField("Email", validators=[Email(), DataRequired()])
    first_name = StringField("First Name", validators=[DataRequired()])
    last_name = StringField("Last Name", validators=[DataRequired()])
    roles = SelectMultipleField("Roles", validators=[Optional()])
    is_super_admin = Boolean()
    # Add fields for permissions if needed
    permissions = SelectMultipleField("Permissions", validators=[Optional()])
