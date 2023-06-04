from flask import jsonify
from app.utils.utils import logged_in_active_user_required
from app import db
from .routes import timezones_bp


@timezones_bp.route("", methods=["GET"])
@logged_in_active_user_required
def get_timezones():
    """
    Fetch PostgreSQL timezones
    """

    timezones = db.engine.execute("SELECT name FROM pg_timezone_names;")
    data = [timezone[0] for timezone in timezones]
    response = {"success": True, "data": data}

    return jsonify(response), 200
