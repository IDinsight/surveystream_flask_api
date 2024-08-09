import json

from flask import jsonify, request
from sqlalchemy import JSON, and_, case, distinct, func, type_coerce
from sqlalchemy.exc import IntegrityError

from app import db
from app.blueprints.auth.models import User
from app.blueprints.targets.models import Target
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_payload,
    validate_query_params,
)

from .errors import InvalidMappingRecordsError, MappingError
from .models import UserMappingConfig, UserSurveyorMapping, UserTargetMapping
from .routes import mapping_bp
from .utils import TargetMapping
from .validators import (
    GetMappingParamValidator,
    MappingConfigQueryParamValidator,
    UpdateTargetMappingConfigValidator,
    UpdateTargetMappingValidator,
)


@mapping_bp.route("/targets-mapping-config", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(MappingConfigQueryParamValidator)
@custom_permissions_required("READ Mapping", "query", "form_uid")
def get_target_mapping_config(validated_query_params):
    """
    Method to retrieve targets to supervisor mapping configurations for a form
    """

    form_uid = validated_query_params.form_uid.data

    try:
        target_mapping = TargetMapping(form_uid)
    except MappingError as e:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "mapping_errors": e.mapping_errors,
                    },
                }
            ),
            422,
        )

    # Fetch all targets for the form
    targets_subquery = target_mapping.get_targets_with_mapped_to_subquery()

    targets = (
        db.session.query(
            targets_subquery.c.mapping_criteria_values,
            targets_subquery.c.mapped_to_values,
            func.coalesce(func.count(distinct(targets_subquery.c.target_uid)), 0).label(
                "target_count"
            ),
            func.sum(case((UserTargetMapping.user_uid == None, 1), else_=0)).label(
                "unmapped_count"
            ),
        )
        .outerjoin(
            UserTargetMapping,
            targets_subquery.c.target_uid == UserTargetMapping.target_uid,
        )
        .group_by(
            targets_subquery.c.mapping_criteria_values,
            targets_subquery.c.mapped_to_values,
        )
        .all()
    )

    # Fetch all lowest level supervisors for the survey
    supervisors_subquery = target_mapping.get_supervisors_subquery()
    supervisors = (
        db.session.query(
            supervisors_subquery.c.mapping_criteria_values,
            func.coalesce(
                func.count(distinct(supervisors_subquery.c.user_uid)), 0
            ).label("supervisor_count"),
        )
        .group_by(supervisors_subquery.c.mapping_criteria_values)
        .all()
    )

    # Build the response
    data = []
    for target_group in targets:
        target_mapping_criteria_values = target_group.mapping_criteria_values
        mapped_to_values = target_group.mapped_to_values
        mapping_found = False

        # Check if there is a mapping configuration entry for the target and supervisor group
        for supervisor_group in supervisors:
            supervisor_mapping_criteria_values = (
                supervisor_group.mapping_criteria_values
            )

            if mapped_to_values == supervisor_mapping_criteria_values:
                data.append(
                    {
                        "target": target_mapping_criteria_values,
                        "target_count": target_group.target_count,
                        "supervisor": supervisor_mapping_criteria_values,
                        "supervisor_count": supervisor_group.supervisor_count,
                        "mapping_status": "Pending"
                        if target_group.unmapped_count > 0
                        else "Complete",
                    }
                )
                mapping_found = True
                break

        # If no mapping configuration entry is found, add a pending mapping entry
        if not mapping_found:
            data.append(
                {
                    "target": target_mapping_criteria_values,
                    "target_count": target_group[-1],
                    "supervisor": None,
                    "supervisor_count": None,
                    "mapping_status": "Pending",
                }
            )

    return jsonify({"success": True, "data": data}), 200


@mapping_bp.route("/targets-mapping-config", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(UpdateTargetMappingConfigValidator)
@custom_permissions_required("WRITE Mapping", "body", "form_uid")
def update_target_mapping_config(validated_payload):
    """
    Method to save a mapping configuration for a target to supervisor mapping

    """
    form_uid = validated_payload.form_uid.data
    payload = request.get_json()

    # Delete existing mapping configuration for the form
    db.session.query(UserMappingConfig).filter(
        UserMappingConfig.form_uid == form_uid,
        UserMappingConfig.mapping_type == "target",
    ).delete()

    # Save the new mapping configuration
    for mapping_config in payload["target_mapping_config"]:
        mapping_values = mapping_config["mapping_values"]
        mapping_values = dict(
            {item["criteria"]: item["value"] for item in mapping_values}
        )

        mapped_to = mapping_config["mapped_to"]
        mapped_to = dict({item["criteria"]: item["value"] for item in mapped_to})

        if mapping_values == mapped_to:
            continue

        user_mapping_config = UserMappingConfig(
            form_uid=form_uid,
            mapping_type="target",
            mapping_values=mapping_values,
            mapped_to=mapped_to,
        )
        db.session.add(user_mapping_config)

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    # Update the target to supervisor mappings based on the new configuration
    try:
        target_mapping = TargetMapping(form_uid)
    except MappingError as e:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "mapping_errors": e.mapping_errors,
                    },
                }
            ),
            422,
        )

    # Generate new mappings and save them
    mappings = target_mapping.generate_mappings()
    if mappings:
        target_mapping.save_mappings(
            mappings["mappings"], mappings["targets_with_invalid_mappings"]
        )

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify(message="Success"), 200


@mapping_bp.route("/targets-mapping-config", methods=["DELETE"])
@logged_in_active_user_required
@validate_query_params(MappingConfigQueryParamValidator)
@custom_permissions_required("WRITE Mapping", "query", "form_uid")
def delete_target_mapping_config(validated_query_params):
    """
    Method to delete mapping configurations for a target to supervisor mapping for a form

    """
    form_uid = validated_query_params.form_uid.data

    # Delete existing mapping configuration for the form
    db.session.query(UserMappingConfig).filter(
        UserMappingConfig.form_uid == form_uid,
        UserMappingConfig.mapping_type == "target",
    ).delete()

    # Delete existing target to supervisor mappings for the form
    db.session.query(UserTargetMapping).filter(
        UserTargetMapping.target_uid.in_(
            db.session.query(Target.target_uid).filter(Target.form_uid == form_uid)
        )
    ).delete(synchronize_session=False)

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    # Update the target to supervisor mappings based on the new configurations
    try:
        target_mapping = TargetMapping(form_uid)
    except MappingError as e:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "mapping_errors": e.mapping_errors,
                    },
                }
            ),
            422,
        )

    # Generate new mappings and save them
    mappings = target_mapping.generate_mappings()
    if mappings:
        target_mapping.save_mappings(
            mappings["mappings"], mappings["targets_with_invalid_mappings"]
        )

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify(message="Success"), 200


@mapping_bp.route("/targets-mapping", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(GetMappingParamValidator)
@custom_permissions_required("READ Mapping", "query", "form_uid")
def get_target_mapping(validated_query_params):
    """
    Method to retrieve target to supervisor mappings for a form

    """
    form_uid = validated_query_params.form_uid.data

    try:
        target_mapping = TargetMapping(form_uid)
    except MappingError as e:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "mapping_errors": e.mapping_errors,
                    },
                }
            ),
            422,
        )

    target_subquery = target_mapping.get_targets_with_mapped_to_subquery()
    supervisors_subquery = target_mapping.get_supervisors_subquery()

    # Fetch additional target details to help with manual mapping
    mapping_data = (
        db.session.query(
            target_subquery.c.target_uid,
            target_subquery.c.target_id,
            target_subquery.c.gender,
            target_subquery.c.language,
            target_subquery.c.location_id,
            target_subquery.c.location_name,
            target_subquery.c.mapping_criteria_values.label(
                "target_mapping_criteria_values"
            ),
            UserTargetMapping.user_uid,
            User.email,
            (User.first_name + " " + User.last_name).label("full_name"),
            func.coalesce(
                supervisors_subquery.c.mapping_criteria_values,
                target_subquery.c.mapping_criteria_values,
            ).label("supervisor_mapping_criteria_values"),
        )
        .outerjoin(
            UserTargetMapping,
            UserTargetMapping.target_uid == target_subquery.c.target_uid,
        )
        .outerjoin(User, User.user_uid == UserTargetMapping.user_uid)
        .outerjoin(
            supervisors_subquery,
            and_(
                (supervisors_subquery.c.user_uid == User.user_uid),
                *[
                    (
                        type_coerce(
                            supervisors_subquery.c.mapping_criteria_values, JSON
                        )[criteria]
                        == type_coerce(target_subquery.c.mapped_to_values, JSON)[
                            criteria
                        ]
                    )
                    for criteria in target_mapping.mapping_criteria
                ]
            ),
        )
        .all()
    )

    data = [
        {
            "target_uid": mapping.target_uid,
            "target_id": mapping.target_id,
            "gender": mapping.gender,
            "language": mapping.language,
            "location_id": mapping.location_id,
            "location_name": mapping.location_name,
            "target_mapping_criteria_values": mapping.target_mapping_criteria_values,
            "supervisor_uid": mapping.user_uid,
            "supervisor_email": mapping.email,
            "supervisor_name": mapping.full_name,
            "supervisor_mapping_criteria_values": mapping.supervisor_mapping_criteria_values,
        }
        for mapping in mapping_data
    ]

    return jsonify({"success": True, "data": data}), 200


@mapping_bp.route("/targets-mapping", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(UpdateTargetMappingValidator)
@custom_permissions_required("WRITE Mapping", "body", "form_uid")
def update_target_mapping(validated_payload):
    """
    Method to update target to supervisor mappings for a form

    """
    form_uid = validated_payload.form_uid.data
    mappings = validated_payload.mappings.data

    try:
        target_mapping = TargetMapping(form_uid)
    except MappingError as e:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "mapping_errors": e.mapping_errors,
                    },
                }
            ),
            422,
        )

    try:
        target_mapping.validate_mappings(mappings)
    except InvalidMappingRecordsError as e:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "record_errors": e.record_errors,
                    },
                }
            ),
            422,
        )

    target_mapping.save_mappings(mappings)

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify(message="Success"), 200
