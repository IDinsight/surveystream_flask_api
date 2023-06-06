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

    timezones = db.engine.execute(
        "SELECT name, abbrev, utc_offset FROM pg_timezone_names;"
    )

    data = [
        {
            "name": timezone[0],
            "abbrev": timezone[1],
            "utc_offset": "%+03d:%02d"
            % divmod((timezone[2].days * 86400 + timezone[2].seconds) // 60, 60)
            if timezone[2]
            else "+00:00",
        }
        for timezone in timezones
    ]
    response = {"success": True, "data": data}

    return jsonify(response), 200
