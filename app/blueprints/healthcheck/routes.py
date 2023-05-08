from flask import Blueprint

healthcheck_bp = Blueprint("healthcheck", __name__, url_prefix="/api/healthcheck")
