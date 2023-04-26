from flask import Blueprint

docs_blueprint = Blueprint("docs", __name__)

from . import views
