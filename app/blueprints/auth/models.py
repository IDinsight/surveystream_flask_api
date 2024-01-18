from datetime import datetime, timedelta
from app import db
from passlib.hash import pbkdf2_sha256
from flask_security import UserMixin

<<<<<<< HEAD

class User(db.Model, UserMixin):
=======
class User(db.Model):
>>>>>>> dev
    """
    SQLAlchemy data model for User
    """

    __tablename__ = "users"

    __table_args__ = {"schema": "webapp"}

    user_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    email = db.Column(db.String(), unique=True, nullable=False)
    password_secure = db.Column(db.String(), nullable=True)
    first_name = db.Column(db.String())
    middle_name = db.Column(db.String())
    last_name = db.Column(db.String())
    home_state = db.Column(db.String())
    home_district = db.Column(db.String())
    phone_primary = db.Column(db.String())
    phone_secondary = db.Column(db.String())
    avatar_s3_filekey = db.Column(db.String())
    active = db.Column(db.Boolean(), nullable=False, server_default="t")

    ## rbac fields
    roles = db.Column(db.ARRAY(db.Integer), default=[], nullable=True)
    is_super_admin = db.Column(db.Boolean, default=False, nullable=True)
<<<<<<< HEAD
    
    to_delete = db.Column(db.Boolean(), default=False, nullable=True)
=======

    to_delete = db.Column(db.Boolean(), default=False, nullable=True)

    def __init__(
        self,
        email,
        first_name,
        last_name,
        active=True,
        password=None,
        is_super_admin=False,
        roles=None,
        to_delete=False,
    ):
        if roles is None:
            roles = []

        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        if password is not None:
            self.password_secure = pbkdf2_sha256.hash(password)
        else:
            self.password_secure = None
        self.roles = roles
        self.is_super_admin = is_super_admin
        self.active = active
        self.to_delete = to_delete if to_delete is not None else False

    def to_dict(self):
        return {
            "user_uid": self.user_uid,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "roles": self.roles,
            "is_super_admin": self.is_super_admin,
            "active": self.active,
        }
>>>>>>> dev


    def __init__(self, email, first_name, last_name, active=True, password=None, is_super_admin=False, roles=None, to_delete=False):
        if roles is None:
            roles = []
        
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        if password is not None:
            self.password_secure = pbkdf2_sha256.hash(password)
        else:
            self.password_secure = None
        self.roles = roles
        self.is_super_admin = is_super_admin
        self.active = active
        self.to_delete = to_delete if to_delete is not None else False


    def to_dict(self):
        return {
            'user_uid': self.user_uid,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'roles': self.roles,
            'is_super_admin': self.is_super_admin,
            'active': self.active
        }
    def verify_password(self, password):
        return pbkdf2_sha256.verify(password, self.password_secure)

    def change_password(self, new_password):
        self.password_secure = pbkdf2_sha256.hash(new_password)
        db.session.add(self)
        db.session.commit()

    ##############################################################################
    # NECESSARY CALLABLES FOR FLASK-LOGIN
    ##############################################################################

    def is_active(self):
        """
        Return True if the user is active
        """
        return self.active

    def get_id(self):
        """
        Return the uid to satisfy Flask-Login's requirements.
        """
        return self.user_uid

    def is_authenticated(self):
        """
        Return True if the user is authenticated.
        """
        return True

    def is_anonymous(self):
        """
        False, as anonymous users aren't supported.
        """
        return False


class ResetPasswordToken(db.Model):
    """
    SQLAlchemy data model for Reset Password Token
    """

    __tablename__ = "reset_password_tokens"
    __table_args__ = {"schema": "webapp"}

    reset_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    user_uid = db.Column(
        db.Integer(), db.ForeignKey(User.user_uid), nullable=False, unique=True
    )
    secret_token = db.Column(db.String(), nullable=False)
    generated_utc = db.Column(db.DateTime(), nullable=False)

    def __init__(self, user_uid, email_token):
        self.user_uid = user_uid
        self.secret_token = pbkdf2_sha256.hash(email_token)
        self.generated_utc = datetime.utcnow()

    def use_token(self, email_token):
        if datetime.utcnow() - self.generated_utc >= timedelta(hours=24):
            return False

        return pbkdf2_sha256.verify(email_token, self.secret_token)
