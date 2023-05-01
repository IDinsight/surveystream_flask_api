from flask_wtf import FlaskForm
from wtforms import IntegerField, PasswordField, StringField
from wtforms.validators import DataRequired, EqualTo


class LoginValidator(FlaskForm):
    email = StringField(validators=[DataRequired()])
    password = PasswordField(validators=[DataRequired()])


class ChangePasswordValidator(FlaskForm):
    cur_password = PasswordField()
    new_password = PasswordField(
        validators=[
            DataRequired(),
            EqualTo("confirm", message="New passwords must match!"),
        ],
    )
    confirm = PasswordField()


class ForgotPasswordValidator(FlaskForm):
    email = StringField(validators=[DataRequired()])


class ResetPasswordValidator(FlaskForm):
    rpt_id = IntegerField(validators=[DataRequired()])
    rpt_token = StringField(validators=[DataRequired()])

    new_password = PasswordField(
        validators=[
            DataRequired(),
            EqualTo("confirm", message="New passwords must match!"),
        ],
    )
    confirm = PasswordField()
