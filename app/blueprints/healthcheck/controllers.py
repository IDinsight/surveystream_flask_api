from . import healthcheck_bp
from flask import jsonify
from app import db


@healthcheck_bp.route("", methods=["GET"])
def healthcheck():
    """
    Check if app can connect to DB
    """
    try:
        db.session.execute("SELECT 1;")
        return jsonify(message="Healthy testing"), 200
    except:
        return jsonify(message="Failed DB connection"), 500
