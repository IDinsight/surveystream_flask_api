from itertools import groupby
from operator import attrgetter

from flask import jsonify, request
from sqlalchemy import String, and_, case, literal_column, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.expression import cast
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
    DQModuleNamesQueryParamValidator,
    UpdateDQChecksStateValidator,
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

    # Get checks that are invalid because the question or filter is not found in the form definition
    filter_invalid_subquery = (
        (
            db.session.query(DQCheckFilters.dq_check_uid)
            .join(
                DQCheck,
                DQCheckFilters.dq_check_uid == DQCheck.dq_check_uid,
            )
            .outerjoin(
                SCTOQuestion,
                or_(
                    and_(
                        DQCheckFilters.question_name == SCTOQuestion.question_name,
                        DQCheck.form_uid == SCTOQuestion.form_uid,
                        DQCheck.type_id.notin_([8, 9]),
                    ),
                    and_(
                        DQCheckFilters.question_name == SCTOQuestion.question_name,
                        DQCheck.dq_scto_form_uid == SCTOQuestion.form_uid,
                        DQCheck.type_id.in_([7, 8, 9]),
                    ),
                ),
            )
            .filter(SCTOQuestion.question_name == None)
        )
        .distinct()
        .subquery()
    )

    # Get checks that are invalid because the question is not found in the form definition
    question_invalid_subquery = (
        db.session.query(DQCheck.dq_check_uid)
        .outerjoin(
            SCTOQuestion,
            or_(
                and_(
                    DQCheck.type_id.notin_([8, 9]),
                    DQCheck.question_name == SCTOQuestion.question_name,
                    SCTOQuestion.form_uid == form_uid,
                ),
                and_(
                    DQCheck.type_id.in_([7, 8, 9]),
                    DQCheck.question_name == SCTOQuestion.question_name,
                    SCTOQuestion.form_uid == DQCheck.dq_scto_form_uid,
                ),
            ),
        )
        .filter(SCTOQuestion.question_name == None, DQCheck.all_questions == False)
        .distinct()
        .subquery()
    )

    # Get checks with active status
    dq_questions_subquery = (
        db.session.query(
            DQCheck.form_uid,
            DQCheck.type_id,
            DQCheck.dq_check_uid,
            DQCheck.all_questions,
            DQCheck.question_name,
            case(
                [
                    (
                        (DQCheck.active == True)
                        & (question_invalid_subquery.c.dq_check_uid == None)
                        & (filter_invalid_subquery.c.dq_check_uid == None),
                        True,
                    )
                ],
                else_=False,
            ).label("active"),
        )
        .outerjoin(
            question_invalid_subquery,
            DQCheck.dq_check_uid == question_invalid_subquery.c.dq_check_uid,
        )
        .outerjoin(
            filter_invalid_subquery,
            DQCheck.dq_check_uid == filter_invalid_subquery.c.dq_check_uid,
        )
        .filter(DQCheck.form_uid == form_uid)
        .subquery()
    )

    # Get count per check type
    dq_checks_subquery = (
        db.session.query(
            dq_questions_subquery.c.form_uid,
            dq_questions_subquery.c.type_id,
            dq_questions_subquery.c.all_questions,
            func.count(dq_questions_subquery.c.dq_check_uid).label("num_configured"),
            func.sum(
                case(
                    [
                        (
                            dq_questions_subquery.c.active == True,
                            1,
                        )
                    ],
                    else_=0,
                )
            ).label("num_active"),
        )
        .group_by(
            dq_questions_subquery.c.form_uid,
            dq_questions_subquery.c.type_id,
            dq_questions_subquery.c.all_questions,
        )
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
                        else_=cast(
                            func.coalesce(dq_checks_subquery.c.num_configured, 0),
                            String,
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
                        else_=cast(
                            func.coalesce(dq_checks_subquery.c.num_active, 0), String
                        ),
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

    if type_id in [7, 8, 9]:
        dq_scto_form_uids = list(set([check.dq_scto_form_uid for check in dq_checks]))
        dq_scto_questions = SCTOQuestion.query.filter(
            SCTOQuestion.form_uid.in_(dq_scto_form_uids)
        ).all()

    check_data = []
    for check in dq_checks:
        check_dict = check.to_dict()

        # Initialize note and repeat group flag
        check_dict["note"] = None
        check_dict["is_repeat_group"] = False

        if not check.all_questions:
            # Check if questions are available in the form definition and if it is a repeat group variable
            question_found = False
            dq_question_found = False

            if type_id not in [8, 9]:
                for question in scto_questions:
                    if question.question_name == check.question_name:
                        question_found = True
                        if question.is_repeat_group:
                            check_dict["is_repeat_group"] = True
                        else:
                            check_dict["is_repeat_group"] = False
                        break

            if type_id in [7, 8, 9]:
                for question in dq_scto_questions:
                    if (
                        question.question_name == check.question_name
                        and question.form_uid == check.dq_scto_form_uid
                    ):
                        dq_question_found = True

                        # Repeat group for mismatch check is set based on main form question
                        if type_id in [8, 9]:
                            if question.is_repeat_group:
                                check_dict["is_repeat_group"] = True
                            else:
                                check_dict["is_repeat_group"] = False
                        break

            if not dq_question_found and type_id in [7, 8, 9]:
                check_dict["active"] = False
                check_dict["note"] = "Question not found in DQ form definition"

            if not question_found and type_id not in [8, 9]:
                check_dict["active"] = False
                check_dict["note"] = "Question not found in form definition"

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
                filter_question_found = False
                for question in scto_questions:
                    if question.question_name == filter_item["question_name"]:
                        filter_question_found = True
                        if question.is_repeat_group:
                            filter_item["is_repeat_group"] = True
                        else:
                            filter_item["is_repeat_group"] = False
                        break

                if not filter_question_found:
                    check_dict["active"] = False
                    check_dict["note"] = "Filter question not found in form definition"

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
    else:
        # Delete existing all questions check for the form and type since a question specific check is being added
        db.session.query(DQCheck).filter(
            DQCheck.form_uid == form_uid,
            DQCheck.type_id == validated_payload.type_id.data,
            DQCheck.all_questions == True,
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


@dq_bp.route("/checks/activate", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(UpdateDQChecksStateValidator)
@custom_permissions_required("WRITE Data Quality", "body", "form_uid")
def activate_dq_checks(validated_payload):
    """
    Function to mark dq checks as active

    """
    form_uid = validated_payload.form_uid.data
    type_id = validated_payload.type_id.data
    check_uids = validated_payload.check_uids.data

    dq_checks = DQCheck.query.filter(
        DQCheck.form_uid == form_uid,
        DQCheck.type_id == type_id,
        DQCheck.dq_check_uid.in_(check_uids),
    ).all()

    invalid_checks = []

    for dq_check in dq_checks:
        if not dq_check.all_questions:
            # Check if the question is available in the form definition
            scto_question = SCTOQuestion.query.filter(
                SCTOQuestion.form_uid == form_uid,
                SCTOQuestion.question_name == dq_check.question_name,
            ).first()

            if scto_question is None:
                invalid_checks.append(dq_check.dq_check_uid)
                continue

        filters = DQCheckFilters.query.filter(
            DQCheckFilters.dq_check_uid == dq_check.dq_check_uid
        ).all()

        # Check if all questions used in filters are valid
        for filter_item in filters:
            scto_question = SCTOQuestion.query.filter(
                SCTOQuestion.form_uid == form_uid,
                SCTOQuestion.question_name == filter_item.question_name,
            ).first()

            if scto_question is None:
                invalid_checks.append(dq_check.dq_check_uid)

    if len(invalid_checks) > 0:
        return (
            jsonify(
                {
                    "message": "Cannot activate checks with questions that are no longer in the form defintiion",
                    "success": False,
                    "invalid_checks": invalid_checks,
                }
            ),
            404,
        )

    # Else mark the checks as active
    DQCheck.query.filter(
        DQCheck.form_uid == form_uid,
        DQCheck.type_id == type_id,
        DQCheck.dq_check_uid.in_(check_uids),
    ).update({"active": True}, synchronize_session=False)

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"message": str(e), "success": False}), 500

    return jsonify({"message": "Success", "success": True}), 200


@dq_bp.route("/checks/deactivate", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(UpdateDQChecksStateValidator)
@custom_permissions_required("WRITE Data Quality", "body", "form_uid")
def deactivate_dq_checks(validated_payload):
    """
    Function to mark dq checks as inactive

    """
    form_uid = validated_payload.form_uid.data
    type_id = validated_payload.type_id.data
    check_uids = validated_payload.check_uids.data

    # Mark the checks as inactive
    DQCheck.query.filter(
        DQCheck.form_uid == form_uid,
        DQCheck.type_id == type_id,
        DQCheck.dq_check_uid.in_(check_uids),
    ).update({"active": False}, synchronize_session=False)

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"message": str(e), "success": False}), 500

    return jsonify({"message": "Success", "success": True}), 200


@dq_bp.route("/checks", methods=["DELETE"])
@logged_in_active_user_required
@validate_payload(UpdateDQChecksStateValidator)
@custom_permissions_required("WRITE Data Quality", "body", "form_uid")
def delete_dq_checks(validated_payload):
    """
    Function to delete a dq check

    """
    form_uid = validated_payload.form_uid.data
    type_id = validated_payload.type_id.data
    check_uids = validated_payload.check_uids.data

    DQCheck.query.filter(
        DQCheck.form_uid == form_uid,
        DQCheck.type_id == type_id,
        DQCheck.dq_check_uid.in_(check_uids),
    ).delete(synchronize_session=False)

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"message": str(e), "success": False}), 500

    return jsonify({"message": "Success", "success": True}), 200


@dq_bp.route("/checks/module-names", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(DQModuleNamesQueryParamValidator)
@custom_permissions_required("READ Data Quality", "query", "form_uid")
def get_dq_module_names(validated_query_params):
    """
    Function to get dq module names

    """
    form_uid = validated_query_params.form_uid.data

    module_names = (
        db.session.query(DQCheck.module_name)
        .filter(DQCheck.form_uid == form_uid)
        .distinct()
        .all()
    )

    # Return 404 if no module names found
    if not module_names:
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "message": "DQ module names not found",
                }
            ),
            404,
        )

    # Return the response
    return (
        jsonify(
            {
                "success": True,
                "data": [module_name[0] for module_name in module_names],
            },
        ),
        200,
    )
