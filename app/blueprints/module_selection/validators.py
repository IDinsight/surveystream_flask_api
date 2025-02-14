from wtforms import StringField, FieldList, IntegerField
from flask_wtf import FlaskForm
from wtforms.validators import DataRequired


class AddModuleStatusValidator(FlaskForm):
    survey_uid = IntegerField(validators=[DataRequired()])
    modules = FieldList(IntegerField(), validators=[DataRequired()])

    def validate(self):
        if not super().validate():
            return False

        return True
