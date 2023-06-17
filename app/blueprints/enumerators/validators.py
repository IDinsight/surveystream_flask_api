from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField
from wtforms.validators import InputRequired


class UpdateSurveyorFormStatusValidator(FlaskForm):
    form_uid = IntegerField(validators=[InputRequired()])
    status = StringField(validators=[InputRequired()])
