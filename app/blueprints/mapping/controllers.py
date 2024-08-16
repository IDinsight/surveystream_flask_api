import json

from flask import jsonify, request
from sqlalchemy import distinct, func
from sqlalchemy.exc import IntegrityError

from app import db
from app.blueprints.auth.models import User
from app.blueprints.locations.models import Location
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
    UpdateMappingConfigValidator,
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
            func.array_agg(targets_subquery.c.target_uid).label("target_uids"),
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

    # Fetch all targets to supervisor mappings
    mappings = target_mapping.generate_mappings()
    mapped_targets = [mapping["target_uid"] for mapping in mappings]

    # Build the response
    data = []
    for target_group in targets:
        mapping_complete = True
        mapping_found = False

        # Check if all targets in the group have been mapped
        for target_uid in target_group.target_uids:
            if target_uid not in mapped_targets:
                mapping_complete = False
                break

        # Find the supervisor group that has the same mapping criteria values as the target group
        for supervisor_group in supervisors:
            if (
                target_group.mapped_to_values
                == supervisor_group.mapping_criteria_values["criteria"]
            ):
                data.append(
                    {
                        "target_mapping_criteria_values": target_group.mapping_criteria_values,
                        "target_count": target_group.target_count,
                        "supervisor_mapping_criteria_values": supervisor_group.mapping_criteria_values,
                        "supervisor_count": supervisor_group.supervisor_count,
                        "mapping_status": "Complete" if mapping_complete else "Pending",
                    }
                )
                mapping_found = True
                break

        # If no mapping configuration entry is found, add a pending mapping entry
        if not mapping_found:
            data.append(
                {
                    "target_mapping_criteria_values": target_group.mapping_criteria_values,
                    "target_count": target_group.target_count,
                    "supervisor_mapping_criteria_values": None,
                    "supervisor_count": None,
                    "mapping_status": "Pending",
                }
            )

    return jsonify({"success": True, "data": data}), 200


@mapping_bp.route("/targets-mapping-config", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(UpdateMappingConfigValidator)
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
    for mapping_config in payload["mapping_config"]:
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

    # Delete existing saved target to supervisor mappings for the form
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

    # Fetch all targets to supervisor mappings
    mappings = target_mapping.generate_mappings()

    target_subquery = target_mapping.get_targets_with_mapped_to_subquery()
    supervisors_subquery = target_mapping.get_supervisors_subquery()

    # Fetch all supervisors for the survey
    supervisors_data = (
        db.session.query(
            User.user_uid,
            User.email,
            (User.first_name + " " + User.last_name).label("full_name"),
            supervisors_subquery.c.mapping_criteria_values.label(
                "supervisor_mapping_criteria_values"
            ),
        )
        .join(supervisors_subquery, supervisors_subquery.c.user_uid == User.user_uid)
        .all()
    )

    # Fetch all targets for the form
    targets_query = db.session.query(
        target_subquery.c.target_uid,
        target_subquery.c.target_id,
        target_subquery.c.gender,
        target_subquery.c.language,
        target_subquery.c.location_id,
        target_subquery.c.location_name,
        target_subquery.c.mapping_criteria_values.label(
            "target_mapping_criteria_values"
        ),
        target_subquery.c.mapped_to_values,
    )

    # Check if we need to paginate the results
    if "page" in request.args and "per_page" in request.args:
        page = request.args.get("page", None, type=int)
        per_page = request.args.get("per_page", None, type=int)

        targets_query = targets_query.paginate(page=page, per_page=per_page)

        data = []
        for target in targets_query.items:
            target_uid = target.target_uid

            mapping_found = False
            for mapping in mappings:
                if target_uid == mapping["target_uid"]:
                    supervisor_uid = mapping["supervisor_uid"]
                    mapping_found = True
                    break

            if mapping_found:
                for supervisor in supervisors_data:
                    if (supervisor.user_uid == supervisor_uid) and (
                        supervisor.supervisor_mapping_criteria_values["criteria"]
                        == target.mapped_to_values
                    ):
                        break

                data.append(
                    {
                        "target_uid": target.target_uid,
                        "target_id": target.target_id,
                        "gender": target.gender,
                        "language": target.language,
                        "location_id": target.location_id,
                        "location_name": target.location_name,
                        "target_mapping_criteria_values": target.target_mapping_criteria_values,
                        "supervisor_uid": supervisor_uid,
                        "supervisor_email": supervisor.email,
                        "supervisor_name": supervisor.full_name,
                        "supervisor_mapping_criteria_values": supervisor.supervisor_mapping_criteria_values,
                    }
                )
            else:
                if "Location" in target_mapping.mapping_criteria:
                    # Find the location ID and Name for the target's mapped to values
                    location = (
                        db.session.query(Location.location_id, Location.location_name)
                        .filter(
                            Location.location_uid
                            == target.mapped_to_values["Location"],
                            Location.survey_uid == target_mapping.survey_uid,
                        )
                        .first()
                    )

                data.append(
                    {
                        "target_uid": target.target_uid,
                        "target_id": target.target_id,
                        "gender": target.gender,
                        "language": target.language,
                        "location_id": target.location_id,
                        "location_name": target.location_name,
                        "target_mapping_criteria_values": target.target_mapping_criteria_values,
                        "supervisor_uid": None,
                        "supervisor_email": None,
                        "supervisor_name": None,
                        "supervisor_mapping_criteria_values": {
                            "criteria": target.mapped_to_values,
                            "other": {
                                "location_id": location.location_id,
                                "location_name": location.location_name,
                            }
                            if "Location" in target_mapping.mapping_criteria
                            else {},
                        },
                    }
                )

        return (
            jsonify(
                {
                    "success": True,
                    "data": data,
                    "pagination": {
                        "count": targets_query.total,
                        "page": page,
                        "per_page": per_page,
                        "pages": targets_query.pages,
                    },
                }
            ),
            200,
        )
    else:
        data = []
        for target in targets_query.all():
            target_uid = target.target_uid

            mapping_found = False
            for mapping in mappings:
                if target_uid == mapping["target_uid"]:
                    supervisor_uid = mapping["supervisor_uid"]
                    mapping_found = True
                    break

            if mapping_found:
                for supervisor in supervisors_data:
                    if (supervisor.user_uid == supervisor_uid) and (
                        supervisor.supervisor_mapping_criteria_values["criteria"]
                        == target.mapped_to_values
                    ):
                        break

                data.append(
                    {
                        "target_uid": target.target_uid,
                        "target_id": target.target_id,
                        "gender": target.gender,
                        "language": target.language,
                        "location_id": target.location_id,
                        "location_name": target.location_name,
                        "target_mapping_criteria_values": target.target_mapping_criteria_values,
                        "supervisor_uid": supervisor_uid,
                        "supervisor_email": supervisor.email,
                        "supervisor_name": supervisor.full_name,
                        "supervisor_mapping_criteria_values": supervisor.supervisor_mapping_criteria_values,
                    }
                )
            else:
                if "Location" in target_mapping.mapping_criteria:
                    # Find the location ID and Name for the target's mapped to values
                    location = (
                        db.session.query(Location.location_id, Location.location_name)
                        .filter(
                            Location.location_uid
                            == target.mapped_to_values["Location"],
                            Location.survey_uid == target_mapping.survey_uid,
                        )
                        .first()
                    )

                data.append(
                    {
                        "target_uid": target.target_uid,
                        "target_id": target.target_id,
                        "gender": target.gender,
                        "language": target.language,
                        "location_id": target.location_id,
                        "location_name": target.location_name,
                        "target_mapping_criteria_values": target.target_mapping_criteria_values,
                        "supervisor_uid": None,
                        "supervisor_email": None,
                        "supervisor_name": None,
                        "supervisor_mapping_criteria_values": {
                            "criteria": target.mapped_to_values,
                            "other": {
                                "location_id": location.location_id,
                                "location_name": location.location_name,
                            }
                            if "Location" in target_mapping.mapping_criteria
                            else {},
                        },
                    }
                )

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
