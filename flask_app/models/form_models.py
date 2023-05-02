from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import (
    IntegerField,
    PasswordField,
    StringField,
    FieldList,
    FormField,
    BooleanField,
)
from wtforms.validators import DataRequired, EqualTo


class LoginForm(FlaskForm):
    email = StringField(validators=[DataRequired()])
    password = PasswordField(validators=[DataRequired()])


class RegisterForm(FlaskForm):
    email = StringField(validators=[DataRequired()])
    password = PasswordField(validators=[DataRequired()])


class ChangePasswordForm(FlaskForm):
    cur_password = PasswordField()
    new_password = PasswordField(
        validators=[
            DataRequired(),
            EqualTo("confirm", message="New passwords must match!"),
        ],
    )
    confirm = PasswordField()


class ForgotPasswordForm(FlaskForm):
    email = StringField(validators=[DataRequired()])


class WelcomeUserForm(FlaskForm):
    email = StringField(validators=[DataRequired()])


class ResetPasswordForm(FlaskForm):
    rpt_id = IntegerField(validators=[DataRequired()])
    rpt_token = StringField(validators=[DataRequired()])

    new_password = PasswordField(
        validators=[
            DataRequired(),
            EqualTo("confirm", message="New passwords must match!"),
        ],
    )
    confirm = PasswordField()


class UpdateSurveyorFormStatusForm(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    status = StringField(validators=[DataRequired()])


class SurveyorAssignmentForm(FlaskForm):
    class Meta:
        csrf = False

    target_uid = IntegerField(validators=[DataRequired()])
    enumerator_uid = IntegerField()


class UpdateSurveyorAssignmentsForm(FlaskForm):
    assignments = FieldList(FormField(SurveyorAssignmentForm))


class UpdateUserProfileForm(FlaskForm):
    new_email = StringField(validators=[DataRequired()])


class UploadUserAvatarForm(FlaskForm):
    image = FileField(
        validators=[FileRequired(), FileAllowed(["jpg", "png"], "Images only!")]
    )


class RemoveUserAvatarForm(FlaskForm):
    pass

