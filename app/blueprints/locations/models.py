from app import db
from app.blueprints.surveys.models import Survey
from sqlalchemy.orm import backref


class GeoLevel(db.Model):
    """
    SQLAlchemy data model for Role
    This tables defines the supervisor roles for a given survey
    """

    __tablename__ = "geo_levels"

    geo_level_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    survey_uid = db.Column(
        db.Integer,
        db.ForeignKey(Survey.survey_uid, ondelete="CASCADE"),
        nullable=False,
    )
    geo_level_name = db.Column(db.String(), nullable=False)
    parent_geo_level_uid = db.Column(db.Integer(), db.ForeignKey(geo_level_uid))
    user_uid = db.Column(db.Integer(), default=-1)
    to_delete = db.Column(db.Integer(), default=0, nullable=False)
    surveys = db.relationship(
        Survey, backref=backref("geo_levels_parent_forms", passive_deletes=True)
    )

    __table_args__ = (
        db.UniqueConstraint(
            "survey_uid",
            "geo_level_name",
            name="_survey_uid_geo_level_name_uc",
            deferrable=True,
        ),
        {"extend_existing": True, "schema": "config_sandbox"},
    )

    def __init__(
        self, survey_uid, geo_level_name, parent_geo_level_uid, user_uid, to_delete
    ):
        self.survey_uid = survey_uid
        self.geo_level_name = geo_level_name
        self.parent_geo_level_uid = parent_geo_level_uid
        self.user_uid = user_uid
        self.to_delete = to_delete

    def to_dict(self):
        return {
            "geo_level_uid": self.geo_level_uid,
            "survey_uid": self.survey_uid,
            "geo_level_name": self.geo_level_name,
            "parent_geo_level_uid": self.parent_geo_level_uid,
        }


class Location(db.Model):
    """
    SQLAlchemy data model for Location
    This tables defines the geographical locations for a given survey
    """

    __tablename__ = "locations"

    location_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    survey_uid = db.Column(
        db.Integer,
        db.ForeignKey(Survey.survey_uid, ondelete="CASCADE"),
        nullable=False,
    )
    location_id = db.Column(db.String(), nullable=False)
    location_name = db.Column(db.String(), nullable=False)
    geo_level_uid = db.Column(db.Integer(), db.ForeignKey(GeoLevel.geo_level_uid))
    parent_location_uid = db.Column(db.Integer(), db.ForeignKey(location_uid))
    surveys = db.relationship(
        Survey, backref=backref("locations", passive_deletes=True)
    )
    geo_levels = db.relationship(
        GeoLevel, backref=backref("locations", passive_deletes=True)
    )

    __table_args__ = (
        db.UniqueConstraint(
            "survey_uid",
            "location_id",
            name="_survey_uid_location_id_uc",
            deferrable=True,
        ),
        db.Index(
            "ix_locations_survey_uid_geo_level_uid",
            "survey_uid",
            "geo_level_uid",
        ),
        {"extend_existing": True, "schema": "config_sandbox"},
    )

    def __init__(
        self,
        survey_uid,
        location_id,
        location_name,
        geo_level_uid,
        parent_location_uid,
    ):
        self.survey_uid = survey_uid
        self.location_id = location_id
        self.location_name = location_name
        self.geo_level_uid = geo_level_uid
        self.parent_location_uid = parent_location_uid

    def to_dict(self):
        return {
            "location_uid": self.location_uid,
            "survey_uid": self.survey_uid,
            "location_name": self.location_name,
            "location_id": self.location_id,
            "geo_level_uid": self.geo_level_uid,
            "parent_location_uid": self.parent_location_uid,
        }
