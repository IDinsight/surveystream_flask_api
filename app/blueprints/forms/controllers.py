import pysurveycto
import json
from flask import current_app, jsonify, request
from flask_login import current_user
from app import db
from app.utils.utils import logged_in_active_user_required, get_aws_secret
from . import forms_bp
from .models import (
    ParentForm,
    SCTOChoiceLabel,
    SCTOQuestionLabel,
    SCTOQuestion,
    SCTOChoiceList,
)
from .validators import (
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
            return (
                jsonify(
                    {
                        "error": "A form already exists for this survey with the same form_name or scto_form_id"
                    }
                ),
                400,
            )
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


@forms_bp.route("/<int:form_uid>/scto-form-definition/refresh", methods=["PUT"])
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

    # Delete the current SCTO form definition from the database
    # Deletes will cascade to the child tables
    SCTOQuestion.query.filter(SCTOQuestion.form_uid == form_uid).delete()
    SCTOChoiceList.query.filter(SCTOChoiceList.form_uid == form_uid).delete()

    # Get the list of columns for the `survey` and `choices` tabs of the form definition
    survey_tab_columns = scto_form_definition["fieldsRowsAndColumns"][0]
    choices_tab_columns = scto_form_definition["choicesRowsAndColumns"][0]
    unique_list_names = []
    try:
        # Process the lists and choices from teh `choices` tab of the form definition
        for row in scto_form_definition["choicesRowsAndColumns"][1:]:
            choices_dict = dict(zip(choices_tab_columns, row))
            if choices_dict["list_name"].strip() != "":
                if choices_dict["list_name"] not in unique_list_names:
                    # Add the choice list to the database
                    scto_choice_list = SCTOChoiceList(
                        form_uid=form_uid,
                        list_name=choices_dict["list_name"],
                    )
                    db.session.add(scto_choice_list)
                    db.session.flush()

                    unique_list_names.append(choices_dict["list_name"])

                choice_labels = [
                    col
                    for col in choices_tab_columns
                    if col.split(":")[0].lower() == "label"
                ]

                for choice_label in choice_labels:
                    # We are going to get the language from the label column that is in the format `label:<language>` or just `label` if the language is not specified
                    language = "default"
                    if len(choice_label.split(":")) > 1:
                        language = choice_label.split(":")[1]

                    # Add the choice label to the database
                    scto_choice_label = SCTOChoiceLabel(
                        list_uid=scto_choice_list.list_uid,
                        choice_value=choices_dict["value"],
                        label=choices_dict[choice_label],
                        language=language,
                    )
                    db.session.add(scto_choice_label)

        # Loop through the rows of the `survey` tab of the form definition
        for row in scto_form_definition["fieldsRowsAndColumns"][1:]:
            questions_dict = dict(zip(survey_tab_columns, row))
            if questions_dict["name"].strip() != "":
                # There can be nested repeat groups, so we need to keep track of the depth in order to determine if a question is part of a repeat group
                repeat_group_depth = 0
                # Handle the questions
                list_uid = None
                list_name = None
                is_repeat_group = False

                # Get the choice name for select questions
                # This will be used to link to the choice options table
                if questions_dict["type"].strip().lower().split(" ")[0] in [
                    "select_one",
                    "select_multiple",
                ]:
                    list_name = questions_dict["type"].strip().split(" ")[1]
                    list_uid = (
                        SCTOChoiceList.query.filter_by(
                            form_uid=form_uid, list_name=list_name
                        )
                        .first()
                        .list_uid
                    )

                # Check if a repeat group is starting
                if questions_dict["type"].strip().lower() == "begin repeat":
                    repeat_group_depth += 1

                if repeat_group_depth > 0:
                    is_repeat_group = True

                # Add the question to the database
                scto_question = SCTOQuestion(
                    form_uid=form_uid,
                    question_name=questions_dict["name"],
                    question_type=questions_dict["type"].strip().lower(),
                    list_uid=list_uid,
                    is_repeat_group=is_repeat_group,
                )
                db.session.add(scto_question)
                db.session.flush()

                # Check if a repeat group is ending
                if questions_dict["type"].strip().lower() == "end repeat":
                    repeat_group_depth -= 1

                # Handle the question labels
                question_labels = [
                    col
                    for col in survey_tab_columns
                    if col.split(":")[0].lower() == "label"
                ]

                for question_label in question_labels:
                    # We are going to get the language from the label column that is in the format `label:<language>` or just `label` if the language is not specified
                    language = "default"
                    if len(question_label.split(":")) > 1:
                        language = question_label.split(":")[1]

                    # Add the question label to the database
                    scto_question_label = SCTOQuestionLabel(
                        question_uid=scto_question.question_uid,
                        label=questions_dict[question_label],
                        language=language,
                    )
                    db.session.add(scto_question_label)

        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return (
            jsonify({"error": "SurveyCTO form definition contains duplicate entities"}),
            500,
        )

    response = {
        "success": True,
    }

    return jsonify(response), 200


@forms_bp.route("/<int:form_uid>/scto-form-definition/scto-questions", methods=["GET"])
@logged_in_active_user_required
def get_scto_variables(form_uid):
    """
    Get SurveyCTO form definition questions from the database table
    """

    parent_form = ParentForm.query.filter_by(form_uid=form_uid).first()

    # Verify the form exists
    if parent_form is None:
        return jsonify({"error": "Parent form not found"}), 404

    scto_questions = (
        SCTOQuestion.query.filter_by(form_uid=form_uid)
        .filter(
            SCTOQuestion.question_type.notin_(
                [
                    "begin group",
                    "end group",
                    "begin repeat",
                    "end repeat",
                    "note",
                    "image",
                    "audio",
                    "video",
                    "text audit",
                ]
            )
        )
        .all()
    )

    # Return the list of variables for the dropdowns
    response = {
        "success": True,
        "data": [scto_question.to_dict() for scto_question in scto_questions],
    }

    return jsonify(response), 200
