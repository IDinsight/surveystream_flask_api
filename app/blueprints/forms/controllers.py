import json

import pandas as pd
import pysurveycto
from flask import current_app, jsonify, request
from flask_login import current_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from app import db
from app.utils.utils import (
    custom_permissions_required,
    get_aws_secret,
    logged_in_active_user_required,
    update_module_status,
    update_module_status_after_request,
    validate_payload,
    validate_query_params,
)

from . import forms_bp
from .models import (
    Form,
    SCTOChoiceLabel,
    SCTOChoiceList,
    SCTOFormSettings,
    SCTOQuestion,
    SCTOQuestionLabel,
    SCTOQuestionMapping,
)
from .validators import (
    CreateFormValidator,
    CreateSCTOQuestionMappingValidator,
    GetFormDefinitionQueryParamValidator,
    GetFormQueryParamValidator,
    UpdateFormValidator,
    UpdateSCTOQuestionMappingValidator,
)


@forms_bp.route("", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(GetFormQueryParamValidator)
@custom_permissions_required(
    ["READ Data Quality Forms", "READ Admin Forms"], "query", "survey_uid"
)
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
@custom_permissions_required(
    ["READ Data Quality Forms", "READ Admin Forms"], "path", "form_uid"
)
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
@custom_permissions_required(
    ["WRITE Data Quality Forms", "WRITE Admin Forms"], "body", "survey_uid"
)
@update_module_status_after_request(3, "survey_uid")
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
    if (
        validated_payload.form_type.data == "admin"
        and validated_payload.admin_form_type.data is None
    ):
        return (
            jsonify({"error": "form_type=admin must have a admin_form_type defined"}),
            422,
        )
    if (
        validated_payload.form_type.data == "parent"
        and validated_payload.number_of_attempts.data is None
    ):
        return (
            jsonify(
                {"error": "form_type=parent must have a number_of_attempts defined"}
            ),
            422,
        )

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
        admin_form_type=validated_payload.admin_form_type.data,
        parent_form_uid=validated_payload.parent_form_uid.data,
        number_of_attempts=(
            validated_payload.number_of_attempts.data
            if validated_payload.number_of_attempts.data is not None
            else None
        ),
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
@custom_permissions_required(
    ["WRITE Data Quality Forms", "WRITE Admin Forms"], "path", "form_uid"
)
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
    if (
        validated_payload.form_type.data == "admin"
        and validated_payload.admin_form_type.data is None
    ):
        return (
            jsonify({"error": "form_type=admin must have a admin_form_type defined"}),
            422,
        )
    if (
        validated_payload.form_type.data == "parent"
        and validated_payload.number_of_attempts.data is None
    ):
        return (
            jsonify(
                {"error": "form_type=parent must have a number_of_attempts defined"}
            ),
            422,
        )

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
                Form.admin_form_type: validated_payload.admin_form_type.data,
                Form.parent_form_uid: validated_payload.parent_form_uid.data,
                Form.number_of_attempts: (
                    validated_payload.number_of_attempts.data
                    if validated_payload.number_of_attempts.data is not None
                    else None
                ),
            },
            synchronize_session="fetch",
        )
        if validated_payload.form_type.data == "parent":
            form = Form.query.filter_by(form_uid=form_uid).first()
            # Update surveycto scto_server_name and timezone for all forms of this survey
            Form.query.filter_by(survey_uid=form.survey_uid).update(
                {
                    Form.scto_server_name: validated_payload.scto_server_name.data,
                    Form.tz_name: validated_payload.tz_name.data,
                },
                synchronize_session=False,
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
@custom_permissions_required(
    ["WRITE Data Quality Forms", "WRITE Admin Forms"], "path", "form_uid"
)
def delete_form(form_uid):
    """
    Delete a form
    """

    # Check if the logged in user has access to the survey

    form = Form.query.filter_by(form_uid=form_uid).first()
    if form is None:
        return jsonify({"error": "Form not found"}), 404

    db.session.delete(form)

    # Update the module status
    update_module_status(3, survey_uid=form.survey_uid)

    db.session.commit()
    return "", 204


@forms_bp.route("/<int:form_uid>/scto-question-mapping", methods=["POST"])
@logged_in_active_user_required
@validate_payload(CreateSCTOQuestionMappingValidator)
@custom_permissions_required(
    ["WRITE Data Quality Forms", "WRITE Admin Forms"], "path", "form_uid"
)
@update_module_status_after_request(3, "form_uid")
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
    if form.form_type in ["parent", "dq"] and validated_payload.target_id.data is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"form_type={form.form_type} must have a mapping for target_id",
                }
            ),
            422,
        )
    if form.form_type == "parent" and validated_payload.survey_status.data is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"form_type={form.form_type} must have a mapping for survey_status",
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
@custom_permissions_required(
    ["WRITE Data Quality Forms", "WRITE Admin Forms"], "path", "form_uid"
)
@update_module_status_after_request(3, "form_uid")
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
    if form.form_type in ["parent", "dq"] and validated_payload.target_id.data is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"form_type={form.form_type} must have a mapping for target_id",
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
@custom_permissions_required(
    ["READ Data Quality Forms", "WRITE Admin Forms"], "path", "form_uid"
)
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
@custom_permissions_required(
    ["WRITE Data Quality Forms", "WRITE Admin Forms"], "path", "form_uid"
)
@update_module_status_after_request(3, "form_uid")
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
@custom_permissions_required(
    ["WRITE Data Quality Forms", "WRITE Admin Forms"], "path", "form_uid"
)
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
    choices_tab_columns = [
        col.replace("label::", "label:")
        for col in scto_form_definition["choicesRowsAndColumns"][0]
    ]  # Deal with horrible formatting quirks that SurveyCTO allows
    settings_tab_columns = scto_form_definition["settingsRowsAndColumns"][0]
    errors, warnings = [], []

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

    # Load choices from the `choices` tab of the form definition
    choices_df = pd.DataFrame(
        scto_form_definition["choicesRowsAndColumns"][1:], columns=choices_tab_columns
    )
    choices_df = choices_df.loc[choices_df["list_name"].str.strip() != ""]

    value_column_name = "value"
    if "value" not in choices_df.columns:
        if "name" in choices_df.columns:
            value_column_name = "name"

        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": [
                            "An error was found on the choices tab of your SurveyCTO form definition. No 'value' or 'name' column was found. Please update your form definition on SurveyCTO and try again."
                        ],
                    }
                ),
                422,
            )

    choice_labels = [
        col for col in choices_tab_columns if col.split(":")[0].lower() == "label"
    ]
    # drop duplicates across all relevant columns
    choices_df = choices_df[
        ["list_name", value_column_name] + choice_labels
    ].drop_duplicates()

    # Find duplicate (list name + choice value) set in the choices tab and add duplicate rows to warnings
    # Warning are not returned at present but kept here for future use
    duplicate_choice_values = choices_df[
        choices_df.duplicated(subset=["list_name", value_column_name])
    ][["list_name", value_column_name]].drop_duplicates()

    for i, row in duplicate_choice_values.iterrows():
        warnings.append(
            f'A warning was found on the choices tab of your SurveyCTO form definition. The choice list "{row["list_name"]}" has multiple choices with the value "{row[value_column_name]}". Please update your form definition on SurveyCTO and try again.'
        )

    if len(errors) > 0:
        return jsonify({"success": False, "errors": errors}), 422

    # Load choice lists
    loaded_list_names = (
        {}
    )  # Dictionary to keep track of loaded list names and their uids for later use
    choice_list_names = list(choices_df["list_name"].unique())
    for list_name in choice_list_names:
        if list_name.strip() == "" or list_name in loaded_list_names:
            continue
        scto_choice_list = SCTOChoiceList(
            form_uid=form_uid,
            list_name=list_name,
        )
        db.session.add(scto_choice_list)
        loaded_list_names[list_name] = None

    try:
        db.session.flush()
    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "errors": [
                        "An unknown error occurred while loading the choice lists in your SurveyCTO form definition. Please update your form definition on SurveyCTO and try again."
                    ]
                }
            ),
            500,
        )

    # Load choice labels - this is done after loading all choice lists to minimize the number of flushes
    # We don't have any unique constraints defined on this table, so we will just load everything
    for choices_dict in choices_df.to_dict(orient="records"):
        # Get the list_uid for the choice list
        scto_choice_list_uid = (
            SCTOChoiceList.query.filter_by(
                form_uid=form_uid, list_name=choices_dict["list_name"]
            )
            .first()
            .list_uid
        )

        loaded_list_names[choices_dict["list_name"]] = scto_choice_list_uid

        for choice_label in choice_labels:
            # We are going to get the language from the label column that is in the format `label:<language>` or just `label` if the language is not specified
            choice_value = choices_dict.get("value", choices_dict.get("name", None))
            language = "default"
            if len(choice_label.split(":")) > 1:
                language = choice_label.split(":")[
                    -1
                ]  # Get the last element because SCTO allows for multiple colons like label::hindi

            # Add the choice label to the database
            scto_choice_label = SCTOChoiceLabel(
                list_uid=scto_choice_list_uid,
                choice_value=choice_value,
                label=choices_dict[choice_label],
                language=language,
            )
            db.session.add(scto_choice_label)

    try:
        db.session.flush()
    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "errors": [
                        f"An unknown error occurred while loading choice list labels in your SurveyCTO form definition. Please update your form definition on SurveyCTO and try again."
                    ]
                }
            ),
            500,
        )

    # Load questions from the `survey` tab of the form definition
    fields_df = pd.DataFrame(
        scto_form_definition["fieldsRowsAndColumns"][1:], columns=survey_tab_columns
    )
    fields_df = fields_df.loc[fields_df["name"].str.strip() != ""]
    # Remove questions with disabled = Yes
    if "disabled" in fields_df.columns:
        fields_df = fields_df.loc[
            fields_df["disabled"].str.strip().str.lower() != "yes"
        ]

    # Check if there are any duplicate question names of same type in the survey tab, and add duplicate issues in warnings
    # Warning are not returned at present but kept here for future use
    duplicate_question_names = fields_df[fields_df.duplicated(subset=["type", "name"])][
        ["type", "name"]
    ].drop_duplicates()
    for i, row in duplicate_question_names.iterrows():
        warnings.append(
            f'A warning was found on the survey tab of your SurveyCTO form definition. The question name "{row["name"]}" and type "{row["type"]}" is used multiple times. Please update your form definition on SurveyCTO and try again.'
        )

    # There can be nested repeat groups, so we need to keep track of the depth in order to determine if a question is part of a repeat group
    repeat_group_depth = 0

    # Loop through the rows of the `survey` tab of the form definition
    for questions_dict in fields_df.to_dict(orient="records"):
        list_uid = None
        list_name = None
        is_repeat_group = False

        # Get the choice name for select questions
        # This will be used to link to the choice options table
        if questions_dict["type"].strip().lower().split(" ")[0] in [
            "select_one",
            "select_multiple",
        ]:
            list_name = questions_dict["type"].strip().split(" ")[-1]
            list_uid = loaded_list_names.get(list_name, None)

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
            is_required=questions_dict.get("required", "No").strip().lower() == "yes",
        )
        db.session.add(scto_question)

        # Check if a repeat group is ending
        if questions_dict["type"].strip().lower() == "end repeat":
            repeat_group_depth -= 1

        try:
            db.session.flush()
        except Exception as e:
            db.session.rollback()
            return (jsonify({"error": str(e)}), 500)

        # We need to handle labels in the same for loop as question names
        # are not unique in SurveyCTO

        # Handle the question labels
        question_labels = [
            col for col in survey_tab_columns if col.split(":")[0].lower() == "label"
        ]

        for question_label in question_labels:
            # We are going to get the language from the label column that is in the format `label:<language>` or just `label` if the language is not specified
            language = "default"
            if len(question_label.split(":")) > 1:
                language = question_label.split(":")[
                    -1
                ]  # Get the last element because SCTO allows for multiple colons like label::hindi

            # Add the question label to the database
            scto_question_label = SCTOQuestionLabel(
                question_uid=scto_question.question_uid,
                label=questions_dict[question_label],
                language=language,
            )
            db.session.add(scto_question_label)

    try:
        db.session.commit()
        survey_uid = form.survey_uid
        from app.blueprints.notifications.utils import check_form_variable_missing

        check_form_variable_missing(survey_uid, form_uid, db)
    except IntegrityError as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "error": [
                        "An unknown error occurred when loading the survey tab of your SurveyCTO form definition. Please update your form definition on SurveyCTO and try again."
                    ]
                }
            ),
            500,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    response = {
        "success": True,
    }

    return jsonify(response), 200


@forms_bp.route("/<int:form_uid>/scto-form-definition", methods=["DELETE"])
@logged_in_active_user_required
@custom_permissions_required(
    ["WRITE Data Quality Forms", "WRITE Admin Forms"], "path", "form_uid"
)
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
@validate_query_params(GetFormDefinitionQueryParamValidator)
@custom_permissions_required(
    ["READ Data Quality Forms", "READ Admin Forms"], "path", "form_uid"
)
def get_scto_form_definition(form_uid, validated_query_params):
    """
    Get SurveyCTO form definition questions from the database table
    We are filtering these based on the question types that are supported for question mapping by SurveyStream
    """
    include_repeat_groups = validated_query_params.include_repeat_groups.data

    form = Form.query.filter_by(form_uid=form_uid).first()

    # Verify the form exists
    if form is None:
        return jsonify({"error": "Form not found"}), 404

    scto_questions_query = SCTOQuestion.query.filter_by(form_uid=form_uid).filter(
        SCTOQuestion.question_type.notin_(
            [
                "begin group",
                "end group",
                "begin repeat",
                "end repeat",
                "note",
                "text audit",
                "sensor_statistic",
                "sensor_stream",
            ]
        )
    )

    if not include_repeat_groups:
        scto_questions_query = scto_questions_query.filter(
            SCTOQuestion.is_repeat_group == False
        )

    scto_questions = scto_questions_query.all()
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
                        "is_required": False,
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
