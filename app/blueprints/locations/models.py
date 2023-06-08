from app import db
from app.blueprints.surveys.models import Survey


class GeoLevel(db.Model):
    """
    SQLAlchemy data model for Role
    This tables defines the supervisor roles for a given survey
    """
    __tablename__ = "geo_levels"

    geo_level_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    survey_uid = db.Column(db.Integer, db.ForeignKey(Survey.survey_uid))
    geo_level_name = db.Column(db.String(), nullable=False)
    parent_geo_level_uid = db.Column(db.Integer(), db.ForeignKey(geo_level_uid))
    user_uid = db.Column(db.Integer(), default=-1)
    to_delete = db.Column(db.Integer(), default=0, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("survey_uid", "geo_level_name", name="_survey_uid_geo_level_name_uc", deferrable=True),
        {
            "extend_existing": True,
            "schema": "config_sandbox"
        }
    )

    def __init__(
        self,
        geo_level_uid,
        survey_uid,
        geo_level_name,
        parent_geo_level_uid,
        user_uid,
        to_delete
    ):
        self.geo_level_uid = geo_level_uid
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
            "parent_geo_level_uid": self.parent_geo_level_uid
        }

