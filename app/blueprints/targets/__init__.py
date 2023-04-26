from flask import Blueprint

targets_blueprint = Blueprint("targets", __name__)

from . import controllers
