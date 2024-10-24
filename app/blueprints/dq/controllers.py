from itertools import groupby
from operator import attrgetter

from flask import jsonify, request
from sqlalchemy import case, literal_column
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.functions import func

from app import db
from app.blueprints.forms.models import SCTOQuestion
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_payload,
    validate_query_params,
)

from . import dq_bp
from .models import DQCheck, DQCheckFilters, DQCheckTypes, DQConfig
from .utils import validate_dq_check
from .validators import (
    DQChecksQueryParamValidator,
    DQCheckValidator,
    DQConfigQueryParamValidator,
    UpdateDQConfigValidator,
)


@dq_bp.route("/check-types", methods=["GET"])
@logged_in_active_user_required
def get_dq_check_types():
    """
    Function to get dq check types

    """
    check_types = DQCheckTypes.query.all()

    # Return 404 if no check types found
    if not check_types:
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "message": "DQ check types not found",
                }
            ),
            404,
        )

    # Return the response
    return (
        jsonify(
            {
                "success": True,
                "data": [check.to_dict() for check in check_types],
            },
        ),
        200,
    )


@dq_bp.route("/config", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(DQConfigQueryParamValidator)
@custom_permissions_required("READ Data Quality", "query", "form_uid")
def get_dq_config(validated_query_params):
    """
    Function to get dq configs per form

    """

    form_uid = validated_query_params.form_uid.data

    # Get count per check type
    dq_checks_subquery = (
        db.session.query(
            DQCheck.form_uid,
            DQCheck.type_id,
            DQCheck.all_questions,
            func.count(DQCheck.dq_check_uid).label("num_configured"),
            func.sum(
                case(
                    [
                        (
                            DQCheck.active == True,
                            1,
                        )
                    ],
                    else_=0,
                )
            ).label("num_active"),
        )
        .group_by(DQCheck.form_uid, DQCheck.type_id, DQCheck.all_questions)
        .filter(DQCheck.form_uid == form_uid)
        .subquery()
    )

    dq_checks_subquery = (
        db.session.query(
            dq_checks_subquery.c.form_uid,
            func.array_agg(
                func.json_build_object(
                    "type_id",
                    dq_checks_subquery.c.type_id,
                    "num_configured",
                    case(
                        [
                            (
                                dq_checks_subquery.c.all_questions == True,
                                literal_column("'All'"),
                            )
                        ],
                        else_=str(
                            func.coalesce(dq_checks_subquery.c.num_configured, 0)
                        ),
                    ),
                    "num_active",
                    case(
                        [
                            (
                                (dq_checks_subquery.c.all_questions == True)
                                & (dq_checks_subquery.c.num_active > 0),
                                literal_column("'All'"),
                            )
                        ],
                        else_=str(func.coalesce(dq_checks_subquery.c.num_active, 0)),
                    ),
                )
            ).label("dq_checks"),
        )
        .group_by(dq_checks_subquery.c.form_uid)
        .subquery()
    )

    dq_config = (
        db.session.query(
            DQConfig.form_uid,
            DQConfig.survey_status_filter,
            dq_checks_subquery.c.dq_checks,
        )
        .outerjoin(
            dq_checks_subquery,
            DQConfig.form_uid == dq_checks_subquery.c.form_uid,
        )
        .filter(DQConfig.form_uid == form_uid)
        .first()
    )

    # Return 404 if no configs found
    if not dq_config:
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "message": "DQ configs not found",
                }
            ),
            404,
        )

    # Return the response
    response = jsonify(
        {
            "success": True,
            "data": {
                "form_uid": dq_config.form_uid,
                "survey_status_filter": dq_config.survey_status_filter,
                "dq_checks": dq_config.dq_checks,
            },
        }
    )

    return response, 200


@dq_bp.route("/config", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(UpdateDQConfigValidator)
@custom_permissions_required("WRITE Data Quality", "body", "form_uid")
def update_dq_config(validated_payload):
    """
    Function to update dq config

    """
    form_uid = validated_payload.form_uid.data
    payload = request.get_json()

    db.session.query(DQConfig).filter(
        DQConfig.form_uid == form_uid,
    ).delete()

    dq_config = DQConfig(
        form_uid=form_uid,
        survey_status_filter=payload["survey_status_filter"],
    )
    db.session.add(dq_config)

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"message": str(e), "success": False}), 500

    return jsonify({"message": "Success", "success": True}), 200


@dq_bp.route("/checks", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(DQChecksQueryParamValidator)
@custom_permissions_required("READ Data Quality", "query", "form_uid")
def get_dq_checks(validated_query_params):
    """
    Function to get dq checks for a form

    """
    form_uid = validated_query_params.form_uid.data
    type_id = validated_query_params.type_id.data

    dq_checks = DQCheck.query.filter(
        DQCheck.form_uid == form_uid,
        DQCheck.type_id == type_id,
    ).all()

    scto_questions = SCTOQuestion.query.filter(SCTOQuestion.form_uid == form_uid).all()

    check_data = []
    for check in dq_checks:
        check_dict = check.to_dict()

        # Initialize note and repeat group flag
        check_dict["note"] = None
        check_dict["is_repeat_group"] = False

        if not check.all_questions:
            # Check if questions are available in the form definition and if it is a repeat group variable
            if check.question_name not in [
                question.question_name for question in scto_questions
            ]:
                check_dict["active"] = False
                check_dict["note"] = "Question not found in form definition"
            else:
                for question in scto_questions:
                    if question.question_name == check.question_name:
                        if question.is_repeat_group:
                            check_dict["is_repeat_group"] = True
                        else:
                            check_dict["is_repeat_group"] = False
                        break

        check_filters = DQCheckFilters.query.filter(
            DQCheckFilters.dq_check_uid == check.dq_check_uid
        ).all()

        filter_list = [
            {"filter_group": [filter.to_dict() for filter in filter_group]}
            for key, filter_group in groupby(
                check_filters, key=attrgetter("filter_group_id")
            )
        ]

        # check if all questions used in filters are valid
        for filter_group in filter_list:
            for filter_item in filter_group["filter_group"]:
                if filter_item["question_name"] not in [
                    question.question_name for question in scto_questions
                ]:
                    check_dict["active"] = False
                    check_dict["note"] = "Filter question not found in form definition"
                    break

        check_dict["filters"] = filter_list

        check_data.append(check_dict)

    # Return 404 if no checks found
    if not dq_checks:
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "message": "DQ checks not found",
                }
            ),
            404,
        )

    # Return the response
    response = jsonify(
        {
            "success": True,
            "data": check_data,
        }
    )

    return response, 200


@dq_bp.route("/checks", methods=["POST"])
@logged_in_active_user_required
@validate_payload(DQCheckValidator)
@custom_permissions_required("WRITE Data Quality", "body", "form_uid")
def add_dq_check(validated_payload):
    """
    Function to add a dq check

    """
    form_uid = validated_payload.form_uid.data
    type_id = validated_payload.type_id.data

    try:
        validate_dq_check(
            form_uid,
            type_id,
            validated_payload.all_questions.data,
            validated_payload.question_name.data,
            validated_payload.dq_scto_form_uid.data,
            validated_payload.check_components.data,
            validated_payload.filters.data,
            validated_payload.active.data,
        )
    except Exception as e:
        return jsonify({"message": str(e), "success": False}), 404

    # Delete existing checks for the form and type if all questions is selected
    if validated_payload.all_questions.data:
        # Delete all checks for the form and type, this cascades to filters
        db.session.query(DQCheck).filter(
            DQCheck.form_uid == form_uid,
            DQCheck.type_id == validated_payload.type_id.data,
        ).delete()

    dq_check = DQCheck(
        form_uid=form_uid,
        type_id=validated_payload.type_id.data,
        all_questions=validated_payload.all_questions.data,
        question_name=validated_payload.question_name.data,
        dq_scto_form_uid=validated_payload.dq_scto_form_uid.data,
        module_name=validated_payload.module_name.data,
        flag_description=validated_payload.flag_description.data,
        check_components=validated_payload.check_components.data,
        active=validated_payload.active.data,
    )

    try:
        db.session.add(dq_check)
        db.session.flush()

        # Add filters for the check
        dq_check_uid = dq_check.dq_check_uid
        max_filter_group_id = 0

        for filter_group in validated_payload.filters.data:
            max_filter_group_id += 1

            for filter in filter_group.get("filter_group"):
                dq_check_filter = DQCheckFilters(
                    dq_check_uid=dq_check_uid,
                    filter_group_id=max_filter_group_id,
                    question_name=filter["question_name"],
                    filter_operator=filter["filter_operator"],
                    filter_value=filter["filter_value"],
                )
                db.session.add(dq_check_filter)
        db.session.flush()
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e), "success": False}), 500

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"message": str(e), "success": False}), 500

    return jsonify({"message": "Success", "success": True}), 200


@dq_bp.route("/checks/<int:check_uid>", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(DQCheckValidator)
@custom_permissions_required("WRITE Data Quality", "body", "form_uid")
def update_dq_check(check_uid, validated_payload):
    """
    Function to update a dq check

    """
    form_uid = validated_payload.form_uid.data

    try:
        validate_dq_check(
            form_uid,
            validated_payload.type_id.data,
            validated_payload.all_questions.data,
            validated_payload.question_name.data,
            validated_payload.dq_scto_form_uid.data,
            validated_payload.check_components.data,
            validated_payload.filters.data,
            validated_payload.active.data,
        )
    except Exception as e:
        return jsonify({"message": str(e), "success": False}), 404

    dq_check = DQCheck.query.filter(
        DQCheck.dq_check_uid == check_uid, DQCheck.form_uid == form_uid
    ).first()

    if dq_check is None:
        return jsonify({"message": "DQ check not found", "success": False}), 404

    dq_check.all_questions = validated_payload.all_questions.data
    dq_check.question_name = validated_payload.question_name.data
    dq_check.dq_scto_form_uid = validated_payload.dq_scto_form_uid.data
    dq_check.module_name = validated_payload.module_name.data
    dq_check.flag_description = validated_payload.flag_description.data
    dq_check.check_components = validated_payload.check_components.data
    dq_check.active = validated_payload.active.data

    try:
        # Delete existing filters and add new filters
        DQCheckFilters.query.filter_by(dq_check_uid=check_uid).delete()
        db.session.flush()

        # Get the max filter group id
        max_filter_group_id = 0

        # Upload Filter List
        for filter_group in validated_payload.filters.data:
            max_filter_group_id += 1

            for filter_item in filter_group.get("filter_group"):
                filter_obj = DQCheckFilters(
                    dq_check_uid=check_uid,
                    filter_group_id=max_filter_group_id,
                    question_name=filter_item["question_name"],
                    filter_operator=filter_item["filter_operator"],
                    filter_value=filter_item["filter_value"],
                )
                db.session.add(filter_obj)
        db.session.flush()
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e), "success": False}), 500

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"message": str(e), "success": False}), 500

    return jsonify({"message": "Success", "success": True}), 200
