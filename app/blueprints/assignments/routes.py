from flask import Blueprint
from .table_config.routes import table_config_bp

assignments_bp = Blueprint("assignments", __name__, url_prefix="/api/assignments")

assignments_bp.register_blueprint(table_config_bp)
