from . import docs_bp
from app.utils import logged_in_active_user_required
from flask import render_template
import yaml


@docs_bp.route("", methods=["GET"])
@logged_in_active_user_required
def view_docs():
    """
    Serve the API spec
    """
    filename = "blueprints/docs/surveystream.yml"
    with open(filename) as file:
        spec_file = yaml.safe_load(file)
    return render_template(
        "docs/index.html", spec_file=spec_file, title="SurveyStream API ReDoc"
    )
