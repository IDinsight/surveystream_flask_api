from flask import jsonify, request
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_query_params,
    validate_payload,
)
from sqlalchemy.exc import IntegrityError
from app import db
from app.blueprints.forms.models import ParentForm
from .models import (
    TargetStatusMapping,
    DefaultTargetStatusMapping,
)
from .routes import target_status_mapping_bp
from .validators import (
    TargetStatusMappingQueryParamValidator,
    UpdateTargetStatusMapping
)


@target_status_mapping_bp.route("", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(TargetStatusMappingQueryParamValidator)
@custom_permissions_required("READ Target Status", "query", "form_uid")
def get_target_status_mapping(validated_query_params):
    """
    Method to get target status mapping
    """

    form_uid = validated_query_params.form_uid.data
    surveying_method = validated_query_params.surveying_method.data

    # First check if data is in the target_status_mapping table
    target_status_mapping = (
        db.session.query(TargetStatusMapping)
        .filter(
            TargetStatusMapping.form_uid == form_uid
        )
        .all()
    )

    # If no form level data in target_status_mapping table, then pick the default mapping from default_target_status_mapping table
    if len(target_status_mapping) == 0:
        target_status_mapping = (
            db.session.query(
                DefaultTargetStatusMapping.survey_status,
                DefaultTargetStatusMapping.survey_status_label,
                DefaultTargetStatusMapping.completed_flag,
                DefaultTargetStatusMapping.refusal_flag,
                DefaultTargetStatusMapping.target_assignable,
                DefaultTargetStatusMapping.webapp_tag_color
            )
            .filter(
                DefaultTargetStatusMapping.surveying_method == surveying_method
            )
            .all()
        )

    data = [
            {
                "survey_status": target_status.survey_status,
                "survey_status_label": target_status.survey_status_label,
                "completed_flag": target_status.completed_flag,
                "refusal_flag": target_status.refusal_flag,
                "target_assignable": target_status.target_assignable,
                "webapp_tag_color": target_status.webapp_tag_color
            } 
            for target_status in target_status_mapping
            ]
    
    response = jsonify(
        {
            "success": True,
            "data": data,
        }
    )
    

    return response, 200


@target_status_mapping_bp.route("", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(UpdateTargetStatusMapping)
@custom_permissions_required("WRITE Target Status", "body", "form_uid")
def update_target_status_mapping(validated_payload):
    """
    Method to save target status mapping
    """

    payload = request.get_json()
    form_uid = validated_payload.form_uid.data

    print(form_uid)
    if (
        ParentForm.query.filter(
            ParentForm.form_uid == form_uid,
        ).first()
        is None
    ):
        return (
            jsonify(
                {
                    "success": False,
                    "errors": f"Form with UID {form_uid} does not exist",
                }
            ),
            422,
        )
    
    TargetStatusMapping.query.filter(
        TargetStatusMapping.form_uid == form_uid,
    ).delete()

    db.session.flush()

    

    for target_status in payload["target_status_mapping"]:
        db.session.add(
            TargetStatusMapping(
                form_uid=form_uid,
                survey_status=target_status["survey_status"],
                survey_status_label=target_status["survey_status_label"],
                completed_flag=target_status["completed_flag"],
                refusal_flag=target_status["refusal_flag"],
                target_assignable=target_status["target_assignable"],
                webapp_tag_color=target_status["webapp_tag_color"],
            )
        )

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"success": True}), 200


