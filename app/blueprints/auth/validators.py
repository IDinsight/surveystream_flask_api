from flask_wtf import FlaskForm
from wtforms import IntegerField, PasswordField, StringField
from wtforms.validators import InputRequired, EqualTo


class LoginValidator(FlaskForm):
    email = StringField(validators=[InputRequired()])
    password = PasswordField(validators=[InputRequired()])


class ChangePasswordValidator(FlaskForm):
    cur_password = PasswordField()
    new_password = PasswordField(
        validators=[
            InputRequired(),
            EqualTo("confirm", message="New passwords must match!"),
        ],
    )
    confirm = PasswordField()


class ForgotPasswordValidator(FlaskForm):
    email = StringField(validators=[InputRequired()])


class ResetPasswordValidator(FlaskForm):
    rpt_id = IntegerField(validators=[InputRequired()])
    rpt_token = StringField(validators=[InputRequired()])

    new_password = PasswordField(
        validators=[
            InputRequired(),
            EqualTo("confirm", message="New passwords must match!"),
        ],
    )
    confirm = PasswordField()
