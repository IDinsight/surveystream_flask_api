from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField
from wtforms.validators import DataRequired


class UpdateSurveyorFormStatusValidator(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    status = StringField(validators=[DataRequired()])
