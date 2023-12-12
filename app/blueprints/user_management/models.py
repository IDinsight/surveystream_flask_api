from app import db
from app.blueprints.auth.models import User

class Invite(db.Model):
    __tablename__ = "invites"
    __table_args__ = {"schema": "webapp"}

    invite_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    invite_code = db.Column(db.String(8), unique=True, nullable=False)
    email = db.Column(db.String(255), nullable=False)
    user_uid = db.Column(db.Integer(), db.ForeignKey(User.user_uid), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def __init__(self, invite_code, email, user_uid, is_active):
        self.invite_code = invite_code
        self.email = email
        self.user_uid = user_uid
        self.is_active = is_active

    def to_dict(self):
        return {
            'invite_code': self.invite_code,
            'email': self.email,
            'user_uid': self.user_uid,
            'is_active': self.is_active,
        }