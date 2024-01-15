from flask import Blueprint

table_config_bp = Blueprint(
    "table_config", __name__, url_prefix="/api/assignments/table-config"
)
