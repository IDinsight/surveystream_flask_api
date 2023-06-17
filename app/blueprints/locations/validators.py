from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, IntegerField, StringField
from wtforms.validators import InputRequired


class SurveyGeoLevelsQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    survey_uid = IntegerField(validators=[InputRequired()])


class SurveyGeoLevelValidator(FlaskForm):
    class Meta:
        csrf = False

    geo_level_uid = IntegerField()
    geo_level_name = StringField(validators=[InputRequired()])
    parent_geo_level_uid = IntegerField()


class SurveyGeoLevelsPayloadValidator(FlaskForm):
    geo_levels = FieldList(FormField(SurveyGeoLevelValidator))


class GeoLevelMappingValidator(FlaskForm):
    class Meta:
        csrf = False

    geo_level_uid = IntegerField(validators=[InputRequired()])
    location_name_column = StringField(validators=[InputRequired()])
    location_id_column = StringField(validators=[InputRequired()])


class LocationsFileUploadValidator(FlaskForm):
    geo_level_mapping = FieldList(FormField(GeoLevelMappingValidator))
    file = StringField(validators=[InputRequired()])


class LocationsQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    survey_uid = IntegerField(validators=[InputRequired()])
