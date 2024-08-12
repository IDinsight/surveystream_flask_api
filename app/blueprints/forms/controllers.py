import pysurveycto
import json
from flask import current_app, jsonify, request
from flask_login import current_user
from app import db
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    get_aws_secret,
    validate_query_params,
    validate_payload,
)
from . import forms_bp
from .models import (
    Form,
    SCTOFormSettings,
    SCTOQuestionMapping,
    SCTOChoiceLabel,
    SCTOQuestionLabel,
    SCTOQuestion,
    SCTOChoiceList,
)
from .validators import (
    CreateFormValidator,
    UpdateFormValidator,
    GetFormQueryParamValidator,
    CreateSCTOQuestionMappingValidator,
    UpdateSCTOQuestionMappingValidator,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased
import pandas as pd


@forms_bp.route("", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(GetFormQueryParamValidator)
@custom_permissions_required(["READ Data Quality Forms"], "query", "survey_uid")
def get_forms(validated_query_params):
    """
    Return details for a user's forms
    If ?survey_uid=<int:survey_uid> is passed, return forms for that survey
    If ?form_type=<str:form_type> is passed, return forms of that type (parent or dq)
    """

    survey_uid = validated_query_params.survey_uid.data
    form_type = validated_query_params.form_type.data

    filters = []
    if survey_uid:
        filters.append(Form.survey_uid == survey_uid)
    if form_type:
        filters.append(Form.form_type == form_type)

    Parent = aliased(Form)

    result = (
        db.session.query(Form, Parent)
        .outerjoin(Parent, Form.parent_form_uid == Parent.form_uid)
        .filter(*filters)
        .all()
    )

    data = []
    for form, parent in result:
        if form.form_type == "dq":
            parent_scto_form_id = parent.scto_form_id
        else:
            parent_scto_form_id = None

        data.append({**form.to_dict(), **{"parent_scto_form_id": parent_scto_form_id}})

    response = {"success": True, "data": data}

    return jsonify(response), 200


@forms_bp.route("/<int:form_uid>", methods=["GET"])
@logged_in_active_user_required
@custom_permissions_required(["READ Data Quality Forms"], "path", "form_uid")
def get_form(form_uid):
    """
    Return details for a form
    """
    form = Form.query.filter_by(form_uid=form_uid).first()

    if form is None:
        return jsonify({"success": False, "message": "Form not found"}), 404

    data = form.to_dict()
    if form.form_type == "dq":
        parent_form = Form.query.filter_by(form_uid=form.parent_form_uid).first()
        data["parent_scto_form_id"] = parent_form.scto_form_id
    else:
        data["parent_scto_form_id"] = None

    response = {"success": True, "data": data}

    return jsonify(response), 200


@forms_bp.route("", methods=["POST"])
@logged_in_active_user_required
@validate_payload(CreateFormValidator)
@custom_permissions_required(["WRITE Data Quality Forms"], "body", "survey_uid")
def create_form(validated_payload):
    """
    Create a form
    """

    # Check if the logged in user has access to the survey

    if (
        validated_payload.form_type.data == "dq"
        and validated_payload.parent_form_uid.data is None
    ):
        return jsonify({"error": "form_type=dq must have a parent form defined"}), 422
    if (
        validated_payload.form_type.data == "dq"
        and validated_payload.dq_form_type.data is None
    ):
        return jsonify({"error": "form_type=dq must have a dq_form_type defined"}), 422

    form = Form(
        survey_uid=validated_payload.survey_uid.data,
        scto_form_id=validated_payload.scto_form_id.data,
        form_name=validated_payload.form_name.data,
        tz_name=validated_payload.tz_name.data,
        scto_server_name=validated_payload.scto_server_name.data,
        encryption_key_shared=validated_payload.encryption_key_shared.data,
        server_access_role_granted=validated_payload.server_access_role_granted.data,
        server_access_allowed=validated_payload.server_access_allowed.data,
        form_type=validated_payload.form_type.data,
        dq_form_type=validated_payload.dq_form_type.data,
        parent_form_uid=validated_payload.parent_form_uid.data,
    )

    try:
        db.session.add(form)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "message": "A form already exists for this survey with \
                            the same form_name or scto_form_id"
                    },
                }
            ),
            400,
        )
    return (
        jsonify(
            {
                "success": True,
                "data": {"message": "success", "survey": form.to_dict()},
            }
        ),
        201,
    )


@forms_bp.route("/<int:form_uid>", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(UpdateFormValidator)
@custom_permissions_required(["WRITE Data Quality Forms"], "path", "form_uid")
def update_form(form_uid, validated_payload):
    """
    Update a form
    """

    if Form.query.filter_by(form_uid=form_uid).first() is None:
        return jsonify({"error": "Form not found"}), 404

    if (
        validated_payload.form_type.data == "dq"
        and validated_payload.parent_form_uid.data is None
    ):
        return jsonify({"error": "form_type=dq must have a parent form defined"}), 422
    if (
        validated_payload.form_type.data == "dq"
        and validated_payload.dq_form_type.data is None
    ):
        return jsonify({"error": "form_type=dq must have a dq_form_type defined"}), 422

    try:
        Form.query.filter_by(form_uid=form_uid).update(
            {
                Form.scto_form_id: validated_payload.scto_form_id.data,
                Form.form_name: validated_payload.form_name.data,
                Form.tz_name: validated_payload.tz_name.data,
                Form.scto_server_name: validated_payload.scto_server_name.data,
                Form.encryption_key_shared: validated_payload.encryption_key_shared.data,
                Form.server_access_role_granted: validated_payload.server_access_role_granted.data,
                Form.server_access_allowed: validated_payload.server_access_allowed.data,
                Form.form_type: validated_payload.form_type.data,
                Form.dq_form_type: validated_payload.dq_form_type.data,
                Form.parent_form_uid: validated_payload.parent_form_uid.data,
            },
            synchronize_session="fetch",
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "message": "A form already exists for this survey with \
                            the same form_name or scto_form_id"
                    },
                }
            ),
            400,
        )

    form = Form.query.filter_by(form_uid=form_uid).first()
    return jsonify(form.to_dict()), 200


@forms_bp.route("/<int:form_uid>", methods=["DELETE"])
@logged_in_active_user_required
@custom_permissions_required(["WRITE Data Quality Forms"], "path", "form_uid")
def delete_form(form_uid):
    """
    Delete a form
    """

    # Check if the logged in user has access to the survey

    form = Form.query.filter_by(form_uid=form_uid).first()
    if form is None:
        return jsonify({"error": "Form not found"}), 404

    db.session.delete(form)
    db.session.commit()
    return "", 204


@forms_bp.route("/<int:form_uid>/scto-question-mapping", methods=["POST"])
@logged_in_active_user_required
@validate_payload(CreateSCTOQuestionMappingValidator)
@custom_permissions_required(["WRITE Data Quality Forms"], "path", "form_uid")
def create_scto_question_mapping(form_uid, validated_payload):
    """
    Create a SurveyCTO question mapping for a form
    """

    payload = request.get_json()

    # Check if the logged in user has access to the survey

    form = Form.query.filter_by(form_uid=form_uid).first()
    if form is None:
        return jsonify({"error": "Form not found"}), 404

    # Check if the form type is dq and if the dq_enumerator_id is provided
    if form.form_type == "dq" and validated_payload.dq_enumerator_id.data is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "form_type=dq must have a mapping for dq_enumerator_id",
                }
            ),
            422,
        )

    scto_question_mapping = SCTOQuestionMapping(
        form_uid=form_uid,
        survey_status=validated_payload.survey_status.data,
        revisit_section=validated_payload.revisit_section.data,
        target_id=validated_payload.target_id.data,
        enumerator_id=validated_payload.enumerator_id.data,
        dq_enumerator_id=validated_payload.dq_enumerator_id.data,
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


@forms_bp.route("/<int:form_uid>/scto-question-mapping", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(UpdateSCTOQuestionMappingValidator)
@custom_permissions_required(["WRITE Data Quality Forms"], "path", "form_uid")
def update_scto_question_mapping(form_uid, validated_payload):
    """
    Update the SCTO question mapping for a form
    """
    payload = request.get_json()

    form = Form.query.filter_by(form_uid=form_uid).first()
    if form is None:
        return jsonify({"error": "Form not found"}), 404

    # Check if the form type is dq and if the dq_enumerator_id is provided
    if form.form_type == "dq" and validated_payload.dq_enumerator_id.data is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "form_type=dq must have a mapping for dq_enumerator_id",
                }
            ),
            422,
        )

    if SCTOQuestionMapping.query.filter_by(form_uid=form_uid).first() is None:
        return jsonify({"error": "Question mapping for form not found"}), 404

    try:
        SCTOQuestionMapping.query.filter_by(form_uid=form_uid).update(
            {
                SCTOQuestionMapping.survey_status: validated_payload.survey_status.data,
                SCTOQuestionMapping.revisit_section: validated_payload.revisit_section.data,
                SCTOQuestionMapping.target_id: validated_payload.target_id.data,
                SCTOQuestionMapping.enumerator_id: validated_payload.enumerator_id.data,
                SCTOQuestionMapping.dq_enumerator_id: validated_payload.dq_enumerator_id.data,
                SCTOQuestionMapping.locations: (
                    payload["locations"] if "locations" in payload else None
                ),
            },
            synchronize_session="fetch",
        )
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify({"success": True}), 200


@forms_bp.route("/<int:form_uid>/scto-question-mapping", methods=["GET"])
@logged_in_active_user_required
@custom_permissions_required(["READ Data Quality Forms"], "path", "form_uid")
def get_scto_question_mapping(form_uid):
    """
    Get the SCTO question mapping for a form
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
@custom_permissions_required(["WRITE Data Quality Forms"], "path", "form_uid")
def delete_scto_question_mapping(form_uid):
    """
    Delete the question mapping for a form
    """

    # Check if the logged in user has access to the survey

    scto_question_mapping = SCTOQuestionMapping.query.filter_by(
        form_uid=form_uid
    ).first()
    if scto_question_mapping is None:
        return jsonify({"error": "Question mapping not found for form"}), 404

    db.session.delete(scto_question_mapping)
    db.session.commit()
    return "", 204


@forms_bp.route("/<int:form_uid>/scto-form-definition/refresh", methods=["POST"])
@logged_in_active_user_required
@custom_permissions_required(["WRITE Data Quality Forms"], "path", "form_uid")
def ingest_scto_form_definition(form_uid):
    """
    Ingest form definition from the SurveyCTO server
    """
    form = Form.query.filter_by(form_uid=form_uid).first()

    # Verify the form exists
    if form is None:
        return jsonify({"error": f"Form with form_uid={form_uid} not found"}), 404

    if form.scto_server_name is None:
        return (
            jsonify({"error": "SurveyCTO server name not provided for the form"}),
            404,
        )

    # Get the SurveyCTO credentials
    try:
        scto_credential_response = get_aws_secret(
            "{scto_server_name}-surveycto-server".format(
                scto_server_name=form.scto_server_name
            ),
            current_app.config["AWS_REGION"],
            is_global_secret=True,
        )

        scto_credentials = json.loads(scto_credential_response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Initialize the SurveyCTO object
    scto = pysurveycto.SurveyCTOObject(
        form.scto_server_name,
        scto_credentials["username"],
        scto_credentials["password"],
    )

    # Get the form definition
    try:
        scto_form_definition = scto.get_form_definition(form.scto_form_id)
        scto_form_version = scto.get_deployed_form_version(form.scto_form_id)
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

    public_key = settings_dict.get("public_key", None)
    submission_url = settings_dict.get("submission_url", None)

    # return jsonify(settings_dict), 422
    scto_settings = SCTOFormSettings(
        form_uid=form_uid,
        form_title=settings_dict["form_title"],
        version=scto_form_version,
        public_key=public_key,
        submission_url=submission_url,
        default_language=settings_dict["default_language"],
    )

    db.session.add(scto_settings)

    # Check for duplicate choice values in the choices tab
    errors = []
    df = pd.DataFrame(
        scto_form_definition["choicesRowsAndColumns"][1:], columns=choices_tab_columns
    )

    df = df.loc[df["list_name"] != ""]

    value_column_name = "value"
    if "value" not in df.columns:
        if "name" in df.columns:
            value_column_name = "name"

        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "No 'value' or 'name' column found on the choices tab of the SurveyCTO form definition",
                    }
                ),
                422,
            )

    duplicate_choice_values = df[
        df.duplicated(subset=["list_name", value_column_name])
    ][["list_name", value_column_name]].drop_duplicates()

    for i, row in duplicate_choice_values.iterrows():
        errors.append(
            f"Duplicate choice values found for list_name={row[0]} and value={row[1]} on the choices tab of the SurveyCTO form definition"
        )

    if len(errors) > 0:
        return jsonify({"success": False, "error": "\n".join(errors)}), 422

    choice_labels = [
        col for col in choices_tab_columns if col.split(":")[0].lower() == "label"
    ]

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

            for choice_label in choice_labels:
                # We are going to get the language from the label column that is in the format `label:<language>` or just `label` if the language is not specified
                choice_value = choices_dict.get("value", choices_dict.get("name", None))
                language = "default"
                if len(choice_label.split(":")) > 1:
                    language = choice_label.split(":")[1]

                # Add the choice label to the database
                scto_choice_label = SCTOChoiceLabel(
                    list_uid=scto_choice_list.list_uid,
                    choice_value=choice_value,
                    label=choices_dict[choice_label],
                    language=language,
                )
                db.session.add(scto_choice_label)

    # Loop through the rows of the `survey` tab of the form definition
    for row in scto_form_definition["fieldsRowsAndColumns"][1:]:
        questions_dict = dict(zip(survey_tab_columns, row))

        # Skip questions with disabled = Yes
        if questions_dict.get("disabled", "No").strip().lower() == "yes":
            continue

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
            jsonify({"error": "SurveyCTO form definition contains duplicate entities"}),
            500,
        )

    response = {
        "success": True,
    }

    return jsonify(response), 200


@forms_bp.route("/<int:form_uid>/scto-form-definition", methods=["DELETE"])
@logged_in_active_user_required
@custom_permissions_required(["WRITE Data Quality Forms"], "path", "form_uid")
def delete_scto_form_definition(form_uid):
    """
    Delete the SuveyCTO form definition for a form
    """

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


@forms_bp.route("/<int:form_uid>/scto-form-definition", methods=["GET"])
@logged_in_active_user_required
@custom_permissions_required(["READ Data Quality Forms"], "path", "form_uid")
def get_scto_form_definition(form_uid):
    """
    Get SurveyCTO form definition questions from the database table
    We are filtering these based on the question types that are supported for question mapping by SurveyStream
    """

    form = Form.query.filter_by(form_uid=form_uid).first()

    # Verify the form exists
    if form is None:
        return jsonify({"error": "Form not found"}), 404

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
        question_dict_arr = []
        question_names_arr = []
        for scto_question in scto_questions:
            question_dict = scto_question.to_dict()
            question_name = question_dict["question_name"]
            question_names_arr.append(question_name)
            question_dict_arr.append(question_dict)

        metadata_fields = [
            "instanceID",
            "formdef_version",
            "starttime",
            "endtime",
            "SubmissionDate",
        ]
        for field in metadata_fields:
            if field not in question_names_arr:
                question_dict_arr.append(
                    {
                        "question_uid": field,  # these won't be linked to a proper uid in the DB
                        "form_uid": form_uid,
                        "question_name": field,
                        "question_type": "text",
                        "list_uid": None,
                        "is_repeat_group": False,
                    }
                )

        # Form definition (partial)
        response = {
            "success": True,
            "data": {
                "questions": question_dict_arr,
                "settings": scto_form_settings.to_dict(),
            },
        }

        return jsonify(response), 200
