from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, IntegerField, StringField
from wtforms.validators import DataRequired


class SurveyGeoLevelsQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    survey_uid = IntegerField(validators=[DataRequired()])


class SurveyGeoLevelValidator(FlaskForm):
    class Meta:
        csrf = False

    geo_level_uid = IntegerField()
    geo_level_name = StringField(validators=[DataRequired()])
    parent_geo_level_uid = IntegerField()


class SurveyGeoLevelsPayloadValidator(FlaskForm):
    geo_levels = FieldList(FormField(SurveyGeoLevelValidator))


class GeoLevelMappingValidator(FlaskForm):
    class Meta:
        csrf = False

    geo_level_uid = IntegerField(validators=[DataRequired()])
    location_name_column = StringField(validators=[DataRequired()])
    location_id_column = StringField(validators=[DataRequired()])


class LocationsFileUploadValidator(FlaskForm):
    geo_level_mapping = FieldList(FormField(GeoLevelMappingValidator))
    file = StringField(validators=[DataRequired()])


class LocationsQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    survey_uid = IntegerField(validators=[DataRequired()])


class SurveyPrimeGeoLevelValidator(FlaskForm):
    prime_geo_level_uid = IntegerField(validators=[DataRequired()])
