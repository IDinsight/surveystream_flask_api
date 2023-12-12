from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, Form, validators, SelectMultipleField, BooleanField
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
    roles = StringField(default=[], validators=[Optional()])
    is_super_admin = BooleanField(default=False, validators=[Optional()])



class CompleteRegistrationValidator(Form):
    invite_code = StringField([validators.InputRequired()])
    new_password = PasswordField([validators.InputRequired(), validators.Length(min=8)])
    confirm_password = PasswordField([validators.EqualTo(
        "new_password", message="Passwords must match")])


class EditUserValidator(FlaskForm):
    email = StringField(validators=[Email(), DataRequired()])
    first_name = StringField( validators=[DataRequired()])
    last_name = StringField(validators=[DataRequired()])
    roles = SelectMultipleField(default=[], choices=[], validators=[Optional()])
    is_super_admin = BooleanField(default=False, validators=[Optional()])
    # Add fields for permissions if needed
    permissions = SelectMultipleField(default=[], choices=[], validators=[Optional()])
