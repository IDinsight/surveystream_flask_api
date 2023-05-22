from . import forms_bp
from app.utils import get_aws_secret, safe_isoformat, logged_in_active_user_required
from flask import jsonify
from flask_login import current_user
from app import db
from app.models.data_models import (
    UserHierarchy,
)
import pysurveycto
from flask import jsonify, request, current_app
from app.blueprints.surveys.models import Survey
from .models import ParentForm, SCTOQuestions
from .validators import ParentFlaskForm, ParentFormVarableMapping
from sqlalchemy.dialects.postgresql import insert as pg_insert

@forms_bp.route("?survey_uid=<int:survey_uid>", methods=["GET"])
@logged_in_active_user_required
def get_parent_form(survey_uid):
    """
    Returns details for a parent form
    """
    parent_form = (
        db.session.query(ParentForm)
        .join(Survey, Survey.survey_uid == ParentForm.survey_uid, isouter=True)
        .join(UserHierarchy, Survey.survey_uid == UserHierarchy.survey_uid)
        .filter(
            Survey.survey_uid == survey_uid,
            UserHierarchy.user_uid == current_user.user_uid,
        )
        .all()
    )
    data = parent_form.to_dict()
    response = {"success": True, "data": data}

    return jsonify(response), 200


@forms_bp.route("?survey_uid=<int:survey_uid>", methods=["PUT"])
@logged_in_active_user_required
def update_parent_form(survey_uid):
    """
    Returns details for a parent form
    """
    validator = ParentFlaskForm.from_json(request.get_json())

    if "X-CSRF-Token" in request.headers:
        validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403
    
    if validator.validate():
        # do upsert
        statement = (
            pg_insert(ParentForm)
            .values(
                scto_form_id=validator.scto_form_id.data,
                form_name=validator.form_name.data,
                tz_name=validator.tz_name.data,
                scto_server_name=validator.scto_server_name.data,
                encryption_key_shared=validator.encryption_key_shared.data,
                server_access_role_granted=validator.server_access_role_granted.data,
                server_access_allowed=validator.server_access_allowed.data,
                scto_variable_mapping=validator.scto_variable_mapping.data
            )
            .on_conflict_do_update(
                constraint="parent_form_pkey",
                set_={
                    "scto_form_id": validator.scto_form_id.data,
                    "form_name": validator.form_name.data,
                    "tz_name": validator.tz_name.data,
                    "scto_server_name": validator.scto_server_name.data,
                    "encryption_key_shared": validator.encryption_key_shared.data,
                    "server_access_allowed": validator.server_access_allowed.data,
                    "scto_variable_mapping": validator.scto_variable_mapping.data
                },
            )
        )

        db.session.execute(statement)
        db.session.commit()

        return jsonify(message="Success"), 200

    else:
        return jsonify({"success": False, "errors": validator.errors}), 422

@forms_bp.route("/load-variables?form_uid=<int:form_uid>", methods=["POST"])
@logged_in_active_user_required
def load_scto_variables(form_uid):
    """
    Fetch form variables from SurveyCTO
    """
    parent_form = ParentFlaskForm.query.filter_by(form_uid=form_uid).first()
    S3_REGION = current_app.config["AWS_REGION"]
     
    scto_credentials = get_aws_secret(parent_form.scto_server_name + "surveycto-server", S3_REGION)
    scto = pysurveycto.SurveyCTOObject(parent_form.scto_server_name, scto_credentials["username"], scto_credentials["password"])
    scto_form_definition = scto.get_form_definition(parent_form.scto_form_id)

    # Update tables in the database
    db.engine.execute(f"DELETE FROM scto_questionnaire_questions WHERE questionnaire_id = '{parent_form.scto_form_id}';")
    db.engine.execute(f"DELETE FROM scto_questionnaire_question_labels WHERE questionnaire_id = '{parent_form.scto_form_id}';")
    db.engine.execute(f"DELETE FROM scto_questionnaire_choice_labels WHERE questionnaire_id = '{parent_form.scto_form_id}';")

    db.engine.execute(f"""

    """
    )

    # Return the list of variables for the dropdowns
    

@forms_bp.route("/get-variables?form_uid=<int:form_uid>", methods=["POST"])
@logged_in_active_user_required
def get_scto_variables(form_uid):
    """
    Get SurveyCTO variables from the database table
    """
    parent_form = ParentFlaskForm.query.filter_by(form_uid=form_uid).first()

    parent_form = (
        db.session.query(SCTOQuestions)
        .join(ParentForm, ParentForm.scto_form_id == SCTOQuestions.questionnaire_id)
        .join(Survey, Survey.survey_uid == ParentForm.survey_uid)
        .join(Survey, Survey.survey_id == SCTOQuestions.survey_id)
        .filter(
            ParentForm.form_uid == form_uid
        )
        .all()
    )
    data = parent_form.to_dict()
    response = {"success": True, "data": data}

    return jsonify(response), 200




@forms_bp.route("/variables-mapping?form_uid=<int:form_uid>", methods=["PUT"])
@logged_in_active_user_required
def update_variable_mapping(form_uid):
    """
    Save variable mapping for the parent form
    """
    variable_mapping = ParentFlaskForm.query.filter_by(form_uid=form_uid).first()
    validator = ParentFormVarableMapping.from_json(request.get_json())

    if "X-CSRF-Token" in request.headers:
        validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if not validator.validate(variable_mapping):
        return jsonify({'success': False, 'message': validator.errors}), 422

    variable_mapping.scto_variable_mapping = validator.scto_variable_mapping.data

    db.session.commit()

    return jsonify({'success': True, 'data': variable_mapping.to_dict()}), 200


