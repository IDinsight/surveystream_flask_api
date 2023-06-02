import pysurveycto
import json
from flask import current_app, jsonify, request
from flask_login import current_user
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app import db
from app.blueprints.surveys.models import Survey
from app.models.data_models import UserHierarchy
from app.utils.utils import logged_in_active_user_required, get_aws_secret
from . import forms_bp
from .models import ParentForm, SCTOChoiceLabels, SCTOQuestionLabels, SCTOQuestion
from .validators import (
    ParentFormVarableMapping,
    CreateParentFormValidator,
    UpdateParentFormValidator,
    GetParentFormQueryParamValidator,
)
from sqlalchemy.exc import IntegrityError


@forms_bp.route("", methods=["GET"])
@logged_in_active_user_required
def get_parent_forms():
    """
    Return details for a user's parent forms
    If ?survey_uid=<int:survey_uid> is passed, return parent forms for that survey
    """

    survey_uid = request.args.get("survey_uid")
    if survey_uid:
        # Validate the query parameter
        query_param_validator = GetParentFormQueryParamValidator.from_json(request.args)
        if not query_param_validator.validate():
            return (
                jsonify(
                    {
                        "success": False,
                        "data": None,
                        "message": query_param_validator.errors,
                    }
                ),
                400,
            )
        parent_forms = ParentForm.query.filter_by(survey_uid=survey_uid).all()
    else:
        parent_forms = ParentForm.query.all()

    data = [parent_form.to_dict() for parent_form in parent_forms]
    response = {"success": True, "data": data}

    return jsonify(response), 200


@forms_bp.route("/<int:form_uid>", methods=["GET"])
@logged_in_active_user_required
def get_parent_form(form_uid):
    """
    Return details for a parent form
    """
    parent_form = ParentForm.query.filter_by(form_uid=form_uid).first()
    if parent_form is None:
        return jsonify({"success": False, "message": "Form not found"}), 404

    response = {"success": True, "data": parent_form.to_dict()}

    return jsonify(response), 200


@forms_bp.route("", methods=["POST"])
@logged_in_active_user_required
def create_parent_form():
    """
    Create a parent form
    """
    payload = request.get_json()

    # Import the request body payload validator
    payload_validator = CreateParentFormValidator.from_json(payload)

    # Check if the logged in user has access to the survey

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    # Validate the request body payload
    if payload_validator.validate():
        parent_form = ParentForm(**payload)
        try:
            db.session.add(parent_form)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return jsonify({"error": "form_uid already exists"}), 400
        return (
            jsonify(
                {
                    "success": True,
                    "data": {"message": "success", "survey": parent_form.to_dict()},
                }
            ),
            201,
        )

    else:
        return jsonify({"success": False, "errors": payload_validator.errors}), 422


@forms_bp.route("/<int:form_uid>", methods=["PUT"])
@logged_in_active_user_required
def update_parent_form(form_uid):
    """
    Update a parent form
    """
    payload = request.get_json()

    # Import the request body payload validator
    payload_validator = UpdateParentFormValidator.from_json(payload)

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    # Validate the request body payload
    if payload_validator.validate():
        if ParentForm.query.filter_by(form_uid=form_uid).first() is None:
            return jsonify({"error": "Parent form not found"}), 404

        ParentForm.query.filter_by(form_uid=form_uid).update(
            {
                ParentForm.scto_form_id: payload_validator.scto_form_id.data,
                ParentForm.form_name: payload_validator.form_name.data,
                ParentForm.tz_name: payload_validator.tz_name.data,
                ParentForm.scto_server_name: payload_validator.scto_server_name.data,
                ParentForm.encryption_key_shared: payload_validator.encryption_key_shared.data,
                ParentForm.server_access_role_granted: payload_validator.server_access_role_granted.data,
                ParentForm.server_access_allowed: payload_validator.server_access_allowed.data,
                ParentForm.scto_variable_mapping: payload_validator.scto_variable_mapping.data,
            },
            synchronize_session="fetch",
        )
        db.session.commit()
        parent_form = ParentForm.query.filter_by(form_uid=form_uid).first()
        return jsonify(parent_form.to_dict()), 200

    else:
        return jsonify({"success": False, "errors": payload_validator.errors}), 422


@forms_bp.route("/<int:form_uid>", methods=["DELETE"])
@logged_in_active_user_required
def delete_form(form_uid):
    """
    Delete a parent form
    """
    parent_form = ParentForm.query.filter_by(form_uid=form_uid).first()
    if parent_form is None:
        return jsonify({"error": "Form not found"}), 404
    db.session.delete(parent_form)
    db.session.commit()
    return "", 204


@forms_bp.route("/timezones", methods=["GET"])
@logged_in_active_user_required
def get_timezones():
    """
    Fetch PostgreSQL timezones
    """

    timezones = db.engine.execute("SELECT name FROM pg_timezone_names;")
    data = [timezone[0] for timezone in timezones]
    response = {"success": True, "data": data}

    return jsonify(response), 200


@forms_bp.route("/<int:form_uid>/scto-variables", methods=["POST"])
@logged_in_active_user_required
def ingest_scto_variables(form_uid):
    """
    Ingest form variables from the SurveyCTO server
    """

    parent_form = ParentForm.query.filter_by(form_uid=form_uid).first()

    # Verify the form exists
    if parent_form is None:
        return jsonify({"error": f"Form with form_uid={form_uid} not found"}), 404

    if parent_form.scto_server_name is None:
        return (
            jsonify({"error": "SurveyCTO server name not provided for the form"}),
            404,
        )

    # Get the SurveyCTO credentials
    try:
        scto_credential_response = get_aws_secret(
            "{scto_server_name}-surveycto-server".format(
                scto_server_name=parent_form.scto_server_name
            ),
            current_app.config["AWS_REGION"],
            is_global_secret=True,
        )

        scto_credentials = json.loads(scto_credential_response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Initialize the SurveyCTO object
    scto = pysurveycto.SurveyCTOObject(
        parent_form.scto_server_name,
        scto_credentials["username"],
        scto_credentials["password"],
    )

    # Get the form definition
    try:
        scto_form_definition = scto.get_form_definition(parent_form.scto_form_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # # Delete data for the SurveyCTO form
    SCTOQuestion.query.filter_by(
        form_uid=form_uid, scto_form_id=parent_form.scto_form_id
    ).delete()
    db.session.commit()
    # db.session.query(SCTOQuestionLabels).filter(
    #     SCTOQuestionLabels.survey_questionnaire_id
    #     == survey.survey_id + "_" + parent_form.scto_form_id
    # ).delete()
    # db.session.query(SCTOQuestionLabels).filter(
    #     SCTOQuestionLabels.survey_questionnaire_id
    #     == survey.survey_id + "_" + parent_form.scto_form_id
    # ).delete()

    columns = scto_form_definition["fieldsRowsAndColumns"][0]
    duplicate_tracker = []
    try:
        for row in scto_form_definition["fieldsRowsAndColumns"][1:]:
            questions_dict = dict(zip(columns, row))
            if (
                questions_dict["name"] != ""
                and questions_dict["name"] not in duplicate_tracker
            ):
                scto_question = SCTOQuestion(
                    form_uid=form_uid,
                    scto_form_id=parent_form.scto_form_id,
                    survey_uid=parent_form.survey_uid,
                    variable_name=questions_dict["name"],
                    variable_type=None,
                    question_no=None,
                    choice_name=None,
                )
                db.session.add(scto_question)
                duplicate_tracker.append(questions_dict["name"])
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "SurveyCTO form contains duplicate variables"}), 500

    scto_questions = SCTOQuestion.query.filter_by(
        form_uid=form_uid, scto_form_id=parent_form.scto_form_id
    ).all()

    # Insert data into tables
    # Airflow load code: https://github.com/IDinsight/dod_airflow_pipeline/blob/d4e6b5bab55f7600e2b8e216d3c036a887e7acc6/tasks/load/load.py#LL119C2-L119C2

    # Return the list of variables for the dropdowns
    response = {
        "success": True,
        "data": [scto_question.to_dict() for scto_question in scto_questions],
    }

    return jsonify(response), 200


@forms_bp.route("/<int:form_uid>/scto-variables", methods=["GET"])
@logged_in_active_user_required
def get_scto_variables(form_uid):
    """
    Get SurveyCTO variables from the database table
    """

    parent_form = ParentForm.query.filter_by(form_uid=form_uid).first()

    # Verify the form exists
    if parent_form is None:
        return jsonify({"error": "Parent form not found"}), 404

    scto_questions = SCTOQuestion.query.filter_by(
        form_uid=form_uid, scto_form_id=parent_form.scto_form_id
    ).all()

    # Return the list of variables for the dropdowns
    response = {
        "success": True,
        "data": [scto_question.to_dict() for scto_question in scto_questions],
    }

    return jsonify(response), 200
