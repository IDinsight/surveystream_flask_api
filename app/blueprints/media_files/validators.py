from flask_wtf import FlaskForm
from wtforms import FieldList, IntegerField, StringField
from wtforms.validators import DataRequired


class MediaFilesConfigQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    survey_uid = IntegerField(validators=[DataRequired()])


class CreateMediaFilesConfigValidator(FlaskForm):
    form_uid = IntegerField(validators=[DataRequired()])
    file_type = StringField(validators=[DataRequired()])
    source = StringField(validators=[DataRequired()])
    format = StringField(
        validators=[
            lambda form, field: (
                DataRequired()(form, field) if form.source.data == "SurveyCTO" else None
            )
        ],
    )
    scto_fields = FieldList(StringField(), validators=[DataRequired()])
    media_fields = FieldList(
        StringField(),
        default=[],
        validators=[
            lambda form, field: (
                DataRequired()(form, field) if form.format.data == "wide" else None
            )
        ],
    )
    mapping_criteria = StringField()


class MediaFilesConfigValidator(FlaskForm):
    file_type = StringField(validators=[DataRequired()])
    source = StringField(validators=[DataRequired()])
    format = StringField(
        default="long",
        validators=[
            lambda form, field: (
                DataRequired()(form, field) if form.source.data == "surveycto" else None
            )
        ],
    )
    scto_fields = FieldList(StringField(), validators=[DataRequired()])
    media_fields = FieldList(
        StringField(),
        default=[],
        validators=[
            lambda form, field: (
                DataRequired()(form, field) if form.format.data == "wide" else None
            )
        ],
    )
    mapping_criteria = StringField()
