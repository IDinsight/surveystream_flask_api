from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired


class RegisterValidator(FlaskForm):
    email = StringField(validators=[DataRequired()])
    password = PasswordField(validators=[DataRequired()])


class WelcomeUserValidator(FlaskForm):
    email = StringField(validators=[DataRequired()])
