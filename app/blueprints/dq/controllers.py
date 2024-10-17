from flask import jsonify, request
from sqlalchemy import case
from sqlalchemy.sql.functions import func

from app import db
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_payload,
    validate_query_params,
)

from . import dq_bp
from .models import DQCheck, DQCheckTypes, DQConfig
from .validators import DQConfigQueryParamValidator, UpdateDQConfigValidator


@dq_bp.route("/check-types", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(DQConfigQueryParamValidator)
def get_dq_check_types(validated_query_params):
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
    response = jsonify(
        {
            "success": True,
            "data": check_types.to_dict(),
        },
        500,
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
            func.count(DQCheck.dq_check_uid).label("dq_checks_count"),
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
                    "count",
                    case(
                        [
                            (
                                dq_checks_subquery.c.all_questions == True,
                                "All",
                            )
                        ],
                        else_=func.coalesce(dq_checks_subquery.c.dq_checks_count, 0),
                    ),
                )
            ).label("dq_checks"),
        )
        .group_by(dq_checks_subquery.cform_uid)
        .subquery()
    )

    dq_config = (
        db.session.query(
            DQConfig.form_uid,
            DQConfig.survey_status_filter,
            DQConfig.paused_check_types,
            dq_checks_subquery.c.dq_checks,
        )
        .outerjoin(
            dq_checks_subquery,
            DQConfig.form_uid == dq_checks_subquery.c.form_uid,
        )
        .outerjoin(
            DQCheckTypes,
            dq_checks_subquery.c.type_id == DQCheckTypes.type_id,
        )
        .filter(DQConfig.form_uid == form_uid)
        .all()
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
            "data": dq_config.to_dict(),
        }
    )

    return response, 200


@dq_bp.route("/config", methods=["PUT"])
@logged_in_active_user_required
@validate_query_params(UpdateDQConfigValidator)
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
        paused_check_types=payload["paused_check_types"],
    )
    db.session.add(dq_config)

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"message": str(e), "success": False}), 500

    return jsonify({"message": "Success", "success": True}), 200
