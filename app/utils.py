from flask import jsonify, session
from flask_login import login_required
from functools import wraps
from app.queries.helper_queries import build_user_level_query
from app import db
from app.models.data_models import User


def concat_names(name_tuple):
    """
    Function to concatenate first, middle, last name parts,
    ignoring missing name parts
    """

    name = ""
    for name_part in name_tuple:
        if name_part is not None:
            name += name_part
            name += " "

    name = name.strip()

    return name


def safe_isoformat(value):
    """
    Assert that a value is not None before converting to isoformat()
    """

    if value is not None:
        return value.isoformat()
    else:
        return ""


def get_core_user_status(user_uid, survey_query):
    """
    Return a boolean indicating whether the given user
    is a core team user on the given survey
    """

    result = build_user_level_query(user_uid, survey_query).first()

    level = result.level

    if level == 0:
        return True
    else:
        return False


def safe_get_dict_value(dict, key):
    """
    Assert that an object is not NoneType before trying to get its key
    """

    if dict is not None:
        return dict.get(key, None)
    else:
        return None


def logged_in_active_user_required(f):
    """
    Login required middleware
    Checks additional active user logic. Otherwise pass flow to built-in login_required (Flask-Login) decorator
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "_user_id" in session:
            user_uid = session.get("_user_id")

            if user_uid is not None:
                user = (
                    db.session.query(User)
                    .filter(User.user_uid == user_uid)
                    .one_or_none()
                )
                if user.is_active() is False:
                    return jsonify(message="INACTIVE_USER"), 403

        return login_required(f)(*args, **kwargs)

    return decorated_function
