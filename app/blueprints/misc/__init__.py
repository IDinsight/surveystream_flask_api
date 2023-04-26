from flask import Blueprint

misc_blueprint = Blueprint("misc", __name__)

from . import controllers
