from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField
from wtforms.validators import DataRequired, Email


class UpdateUserProfileValidator(FlaskForm):
    new_email = StringField(validators=[DataRequired(), Email()])


class UploadUserAvatarValidator(FlaskForm):
    image = FileField(
        validators=[FileRequired(), FileAllowed(["jpg", "png"], "Images only!")]
    )
