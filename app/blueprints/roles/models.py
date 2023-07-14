from app import db
from app.blueprints.surveys.models import Survey


class Role(db.Model):
    """
    SQLAlchemy data model for Role
    This tables defines the supervisor roles for a given survey
    """

    __tablename__ = "roles"

    role_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    survey_uid = db.Column(db.Integer, db.ForeignKey(Survey.survey_uid))
    role_name = db.Column(db.String(), nullable=False)
    reporting_role_uid = db.Column(db.Integer(), db.ForeignKey(role_uid))
    user_uid = db.Column(db.Integer(), default=-1)
    to_delete = db.Column(db.Integer(), default=0, nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "survey_uid", "role_name", name="_survey_uid_role_name_uc", deferrable=True
        ),
        {"schema": "webapp"},
    )

    def __init__(
        self, role_uid, survey_uid, role_name, reporting_role_uid, user_uid, to_delete
    ):
        self.role_uid = role_uid
        self.survey_uid = survey_uid
        self.role_name = role_name
        self.reporting_role_uid = reporting_role_uid
        self.user_uid = user_uid
        self.to_delete = to_delete

    def to_dict(self):
        return {
            "role_uid": self.role_uid,
            "survey_uid": self.survey_uid,
            "role_name": self.role_name,
            "reporting_role_uid": self.reporting_role_uid,
        }
