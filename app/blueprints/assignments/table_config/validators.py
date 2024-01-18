from flask_wtf import FlaskForm
from wtforms import IntegerField, FieldList, FormField, StringField
from wtforms.validators import DataRequired


class TableConfigValidator(FlaskForm):
    class Meta:
        csrf = False

    group_label = StringField()
    column_label = StringField(validators=[DataRequired()])
    column_key = StringField(validators=[DataRequired()])
    column_order = StringField(validators=[DataRequired()])


class UpdateTableConfigValidator(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    table_name = StringField(validators=[DataRequired()])
    table_config = FieldList(FormField(TableConfigValidator))
