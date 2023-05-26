from . import docs_bp
from flask import render_template, current_app
from flask_login import current_user
import yaml
from pathlib import Path


@docs_bp.route("", methods=["GET"])
def view_docs():
    """
    Serve the API spec
    """

    if current_app.config["PROTECT_DOCS_ENDPOINT"] and (
        current_user.is_authenticated == False or current_user.is_active == False
    ):
        return current_app.login_manager.unauthorized()

    filename = Path(__file__).resolve().parent / "surveystream.yml"
    with open(filename) as file:
        spec_file = yaml.safe_load(file)
    return render_template(
        "docs/index.html", spec_file=spec_file, title="SurveyStream API ReDoc"
    )
