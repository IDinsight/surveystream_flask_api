from flask_wtf import FlaskForm
from wtforms import BooleanField, FieldList, FormField, IntegerField, StringField
from wtforms.validators import DataRequired


class TableConfigValidator(FlaskForm):
    class Meta:
        csrf = False

    group_label = StringField()
    column_label = StringField(validators=[DataRequired()])
    column_key = StringField(validators=[DataRequired()])


class UpdateTableConfigValidator(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    table_name = StringField(validators=[DataRequired()])
    table_config = FieldList(FormField(TableConfigValidator))


class TableConfigQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])
    filter_supervisors = BooleanField(default=False)
