from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import InputRequired


class RegisterValidator(FlaskForm):
    email = StringField(validators=[InputRequired()])
    password = PasswordField(validators=[InputRequired()])


class WelcomeUserValidator(FlaskForm):
    email = StringField(validators=[InputRequired()])
