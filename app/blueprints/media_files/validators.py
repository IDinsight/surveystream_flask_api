from flask_wtf import FlaskForm
from wtforms import IntegerField, FieldList, StringField
from wtforms.validators import DataRequired


class MediaFilesConfigQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    form_uid = IntegerField(validators=[DataRequired()])


class CreateMediaFilesConfigValidator(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    file_type = StringField(validators=[DataRequired()])
    source = StringField(validators=[DataRequired()])
    scto_fields = FieldList(StringField(), validators=[DataRequired()])
    mapping_criteria = StringField()


class MediaFilesConfigValidator(FlaskForm):
    file_type = StringField(validators=[DataRequired()])
    source = StringField(validators=[DataRequired()])
    scto_fields = FieldList(StringField(), validators=[DataRequired()])
    mapping_criteria = StringField()
