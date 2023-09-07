import pysurveycto
import json
from flask import current_app, jsonify, request
from flask_login import current_user
from app import db
from app.utils.utils import logged_in_active_user_required, get_aws_secret
from . import forms_bp
from .models import (
    ParentForm,
    SCTOFormSettings,
    SCTOQuestionMapping,
    SCTOChoiceLabel,
    SCTOQuestionLabel,
    SCTOQuestion,
    SCTOChoiceList,
)
from .validators import (
    CreateParentFormValidator,
    UpdateParentFormValidator,
    DeleteParentFormValidator,
    GetParentFormQueryParamValidator,
    CreateSCTOQuestionMappingValidator,
    UpdateSCTOQuestionMappingValidator,
    DeleteSCTOQuestionMappingValidator,
    IngestSCTOFormDefinitionValidator,
    DeleteSCTOFormDefinitionValidator,
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
        parent_form = ParentForm(
            survey_uid=payload_validator.survey_uid.data,
            scto_form_id=payload_validator.scto_form_id.data,
            form_name=payload_validator.form_name.data,
            tz_name=payload_validator.tz_name.data,
            scto_server_name=payload_validator.scto_server_name.data,
            encryption_key_shared=payload_validator.encryption_key_shared.data,
            server_access_role_granted=payload_validator.server_access_role_granted.data,
            server_access_allowed=payload_validator.server_access_allowed.data,
        )
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

    # Import the request body payload validator
    csrf_validator = DeleteParentFormValidator.from_json({})

    # Check if the logged in user has access to the survey

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        csrf_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if csrf_validator.validate():
        parent_form = ParentForm.query.filter_by(form_uid=form_uid).first()
        if parent_form is None:
            return jsonify({"error": "Form not found"}), 404

        db.session.delete(parent_form)
        db.session.commit()
        return "", 204
    else:
        return jsonify({"success": False, "errors": csrf_validator.errors}), 422


@forms_bp.route("/<int:form_uid>/scto-question-mapping", methods=["POST"])
@logged_in_active_user_required
def create_scto_question_mapping(form_uid):
    """
    Create a SurveyCTO question mapping for a parent form
    """

    payload = request.get_json()

    # Import the request body payload validator
    payload_validator = CreateSCTOQuestionMappingValidator.from_json(payload)

    # Check if the logged in user has access to the survey

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    # Validate the request body payload
    if payload_validator.validate():
        parent_form = ParentForm.query.filter_by(form_uid=form_uid).first()
        if parent_form is None:
            return jsonify({"error": "Form not found"}), 404
        scto_question_mapping = SCTOQuestionMapping(
            form_uid=form_uid,
            survey_status=payload_validator.survey_status.data,
            revisit_section=payload_validator.revisit_section.data,
            target_id=payload_validator.target_id.data,
            enumerator_id=payload_validator.enumerator_id.data,
            locations=payload["locations"] if "locations" in payload else None,
        )
        try:
            db.session.add(scto_question_mapping)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return (
                jsonify({"error": "A question mapping already exists for this form"}),
                400,
            )
        return (
            jsonify(
                {
                    "success": True,
                }
            ),
            201,
        )

    else:
        return jsonify({"success": False, "errors": payload_validator.errors}), 422


@forms_bp.route("/<int:form_uid>/scto-question-mapping", methods=["PUT"])
@logged_in_active_user_required
def update_scto_question_mapping(form_uid):
    """
    Update the SCTO question mapping for a parent form
    """
    payload = request.get_json()

    # Import the request body payload validator
    payload_validator = UpdateSCTOQuestionMappingValidator.from_json(payload)

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    # Validate the request body payload
    if payload_validator.validate():
        if SCTOQuestionMapping.query.filter_by(form_uid=form_uid).first() is None:
            return jsonify({"error": "Question mapping for form not found"}), 404

        try:
            SCTOQuestionMapping.query.filter_by(form_uid=form_uid).update(
                {
                    SCTOQuestionMapping.survey_status: payload_validator.survey_status.data,
                    SCTOQuestionMapping.revisit_section: payload_validator.revisit_section.data,
                    SCTOQuestionMapping.target_id: payload_validator.target_id.data,
                    SCTOQuestionMapping.enumerator_id: payload_validator.enumerator_id.data,
                    SCTOQuestionMapping.locations: payload["locations"]
                    if "locations" in payload
                    else None,
                },
                synchronize_session="fetch",
            )
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

        return jsonify({"success": True}), 200

    else:
        return jsonify({"success": False, "errors": payload_validator.errors}), 422


@forms_bp.route("/<int:form_uid>/scto-question-mapping", methods=["GET"])
@logged_in_active_user_required
def get_scto_question_mapping(form_uid):
    """
    Get the SCTO question mapping for a parent form
    """

    scto_question_mapping = SCTOQuestionMapping.query.filter_by(
        form_uid=form_uid
    ).first()
    if scto_question_mapping is None:
        return jsonify({"error": "Question mapping for form not found"}), 404

    response = {"success": True, "data": scto_question_mapping.to_dict()}

    return jsonify(response), 200


@forms_bp.route("/<int:form_uid>/scto-question-mapping", methods=["DELETE"])
@logged_in_active_user_required
def delete_scto_question_mapping(form_uid):
    """
    Delete the question mapping for a parent form
    """

    # Import the request body payload validator
    csrf_validator = DeleteSCTOQuestionMappingValidator.from_json({})

    # Check if the logged in user has access to the survey

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        csrf_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if csrf_validator.validate():
        scto_question_mapping = SCTOQuestionMapping.query.filter_by(
            form_uid=form_uid
        ).first()
        if scto_question_mapping is None:
            return jsonify({"error": "Question mapping not found for form"}), 404

        db.session.delete(scto_question_mapping)
        db.session.commit()
        return "", 204
    else:
        return jsonify({"success": False, "errors": csrf_validator.errors}), 422


@forms_bp.route("/<int:form_uid>/scto-form-definition/refresh", methods=["POST"])
@logged_in_active_user_required
def ingest_scto_form_definition(form_uid):
    """
    Ingest form definition from the SurveyCTO server
    """

    csrf_validator = IngestSCTOFormDefinitionValidator.from_json({})
    if "X-CSRF-Token" in request.headers:
        csrf_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if csrf_validator.validate():
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
            scto_form_version = scto.get_deployed_form_version(parent_form.scto_form_id)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        # Delete the current SCTO form definition from the database
        # Deletes will cascade to the child tables
        SCTOFormSettings.query.filter(SCTOFormSettings.form_uid == form_uid).delete()
        SCTOQuestion.query.filter(SCTOQuestion.form_uid == form_uid).delete()
        SCTOChoiceList.query.filter(SCTOChoiceList.form_uid == form_uid).delete()

        # Get the list of columns for the `survey` and `choices` tabs of the form definition
        survey_tab_columns = scto_form_definition["fieldsRowsAndColumns"][0]
        choices_tab_columns = scto_form_definition["choicesRowsAndColumns"][0]
        settings_tab_columns = scto_form_definition["settingsRowsAndColumns"][0]
        unique_list_names = []

        # Process the settings tab of the form definition
        settings_dict = dict(
            zip(
                settings_tab_columns,
                scto_form_definition["settingsRowsAndColumns"][1:][0],
            )
        )
        # return jsonify(settings_dict), 422
        scto_settings = SCTOFormSettings(
            form_uid=form_uid,
            form_title=settings_dict["form_title"],
            version=scto_form_version,
            public_key=settings_dict["public_key"],
            submission_url=settings_dict["submission_url"],
            default_language=settings_dict["default_language"],
        )

        db.session.add(scto_settings)

        # Process the lists and choices from the `choices` tab of the form definition
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
                    try:
                        db.session.flush()
                    except IntegrityError as e:
                        db.session.rollback()
                        return (
                            jsonify(
                                {
                                    "error": "SurveyCTO form definition contains duplicate choice list entities"
                                }
                            ),
                            500,
                        )

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

                try:
                    db.session.flush()
                except IntegrityError as e:
                    db.session.rollback()
                    return (jsonify({"error": str(e)}),)

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

        try:
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            return (
                jsonify(
                    {"error": "SurveyCTO form definition contains duplicate entities"}
                ),
                500,
            )

        response = {
            "success": True,
        }

        return jsonify(response), 200
    else:
        return jsonify({"success": False, "errors": csrf_validator.errors}), 422


@forms_bp.route("/<int:form_uid>/scto-form-definition", methods=["DELETE"])
@logged_in_active_user_required
def delete_scto_form_definition(form_uid):
    """
    Delete the SuveyCTO form definition for a parent form
    """

    csrf_validator = DeleteSCTOFormDefinitionValidator.from_json({})
    if "X-CSRF-Token" in request.headers:
        csrf_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if csrf_validator.validate():
        scto_questions = SCTOQuestion.query.filter_by(form_uid=form_uid).first()
        if scto_questions is None:
            return (
                jsonify({"error": "SurveyCTO form definition not found for form"}),
                404,
            )

        SCTOFormSettings.query.filter(SCTOFormSettings.form_uid == form_uid).delete()
        SCTOQuestion.query.filter(SCTOQuestion.form_uid == form_uid).delete()
        SCTOChoiceList.query.filter(SCTOChoiceList.form_uid == form_uid).delete()

        db.session.commit()
        return "", 204
    else:
        return jsonify({"success": False, "errors": csrf_validator.errors}), 422


@forms_bp.route("/<int:form_uid>/scto-form-definition", methods=["GET"])
@logged_in_active_user_required
def get_scto_form_definition(form_uid):
    """
    Get SurveyCTO form definition questions from the database table
    We are filtering these based on the question types that are supported for question mapping by SurveyStream
    """

    parent_form = ParentForm.query.filter_by(form_uid=form_uid).first()

    # Verify the form exists
    if parent_form is None:
        return jsonify({"error": "Parent form not found"}), 404

    scto_questions = (
        SCTOQuestion.query.filter_by(form_uid=form_uid, is_repeat_group=False)
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
                    "file",
                    "text audit",
                    "audio audit" "sensor_statistic",
                    "sensor_stream",
                ]
            )
        )
        .all()
    )

    scto_form_settings = SCTOFormSettings.query.filter_by(form_uid=form_uid).first()

    if scto_form_settings is None:
        response = {"success": True, "data": None}
        return jsonify(response), 200

    else:
        # Form definition (partial)
        response = {
            "success": True,
            "data": {
                "questions": [
                    scto_question.to_dict() for scto_question in scto_questions
                ],
                "settings": scto_form_settings.to_dict(),
            },
        }

        return jsonify(response), 200
