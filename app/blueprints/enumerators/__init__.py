from flask import Blueprint

enumerators_blueprint = Blueprint("enumerators", __name__)

from . import controllers
