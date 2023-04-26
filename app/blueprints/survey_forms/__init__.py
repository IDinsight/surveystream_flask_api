from flask import Blueprint

survey_forms_blueprint = Blueprint("survey_forms", __name__)

from . import controllers
