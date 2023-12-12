from app import db
from app.blueprints.auth.models import User
from app.blueprints.surveys.models import Survey
from flask_security import RoleMixin


class Role(db.Model, RoleMixin):
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

    ## rbac fields
    permissions = db.Column(db.ARRAY(db.Integer), default=[], nullable=True)

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

class UserHierarchy(db.Model):
    __tablename__ = "user_hierarchy"

    survey_uid = db.Column(
        db.Integer,
        db.ForeignKey(Survey.survey_uid),
    )
    role_uid = db.Column(db.Integer, db.ForeignKey(Role.role_uid, ondelete='CASCADE'))
    user_uid = db.Column(db.Integer, db.ForeignKey(User.user_uid, ondelete='CASCADE'))
    parent_user_uid = db.Column(db.Integer, db.ForeignKey(User.user_uid, ondelete='CASCADE'))

    __table_args__ = (
        db.PrimaryKeyConstraint("survey_uid", "user_uid", name="user_hierarchy_pk"),
        {"schema": "webapp"},
    )


class Permission(db.Model):
    __tablename__ = "permissions"
    __table_args__ = {"schema": "webapp"}

    permission_uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))


class RolePermissions(db.Model):
    __tablename__ = "role_permissions"
    __table_args__ = {"schema": "webapp"}

    role_permissions_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    role_uid = db.Column(db.Integer, db.ForeignKey(Role.role_uid, ondelete='CASCADE'))
    permission_uid = db.Column(db.Integer, db.ForeignKey(Permission.permission_uid, ondelete='CASCADE'))
