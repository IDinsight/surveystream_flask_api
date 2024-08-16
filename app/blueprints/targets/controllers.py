import base64
import binascii

from flask import jsonify, request
from flask_login import current_user
from sqlalchemy import cast, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.functions import func

from app import db
from app.blueprints.forms.models import Form
from app.blueprints.locations.errors import InvalidGeoLevelHierarchyError
from app.blueprints.locations.models import GeoLevel, Location
from app.blueprints.locations.utils import GeoLevelHierarchy
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_payload,
    validate_query_params,
)

from .errors import (
    HeaderRowEmptyError,
    InvalidColumnMappingError,
    InvalidFileStructureError,
    InvalidNewColumnError,
    InvalidTargetRecordsError,
)
from .models import Target, TargetColumnConfig, TargetStatus
from .queries import build_bottom_level_locations_with_location_hierarchy_subquery
from .routes import targets_bp
from .utils import TargetColumnMapping, TargetsUpload
from .validators import (
    BulkUpdateTargetsValidator,
    TargetsFileUploadValidator,
    TargetsQueryParamValidator,
    UpdateTarget,
    UpdateTargetsColumnConfig,
    UpdateTargetStatus,
)


@targets_bp.route("", methods=["POST"])
@logged_in_active_user_required
@validate_query_params(TargetsQueryParamValidator)
@validate_payload(TargetsFileUploadValidator)
@custom_permissions_required("WRITE Targets", "query", "form_uid")
def upload_targets(validated_query_params, validated_payload):
    """
    Method to validate the uploaded targets file and save it to the database
    """

    form_uid = validated_query_params.form_uid.data

    # Get the survey UID from the form UID
    form = Form.query.filter_by(form_uid=form_uid).first()

    if form is None:
        return (
            jsonify(
                message=f"The form 'form_uid={form_uid}' could not be found. Cannot upload targets for an undefined form."
            ),
            404,
        )

    survey_uid = form.survey_uid

    # Create the column mapping object from the payload
    try:
        column_mapping = TargetColumnMapping(
            validated_payload.column_mapping.data, form_uid, validated_payload.mode.data
        )
    except InvalidColumnMappingError as e:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "column_mapping": e.column_mapping_errors,
                    },
                }
            ),
            422,
        )
    except InvalidNewColumnError as e:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "column_mapping": e.new_column_errors,
                    },
                }
            ),
            422,
        )

    # If the column mapping has a location_id_column, make sure the geo levels for the survey are valid
    if hasattr(column_mapping, "location_id_column"):
        geo_levels = GeoLevel.query.filter_by(survey_uid=survey_uid).all()

        try:
            geo_level_hierarchy = GeoLevelHierarchy(geo_levels)
        except InvalidGeoLevelHierarchyError as e:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": {
                            "geo_level_hierarchy": e.geo_level_hierarchy_errors,
                        },
                    }
                ),
                422,
            )
    else:
        geo_level_hierarchy = None

    # Create a TargetsUpload object from the uploaded file
    try:
        targets_upload = TargetsUpload(
            csv_string=base64.b64decode(
                validated_payload.file.data, validate=True
            ).decode("utf-8"),
            column_mapping=column_mapping,
            survey_uid=survey_uid,
            form_uid=form_uid,
        )
    except binascii.Error:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "file_structure_errors": [
                            "File data has invalid base64 encoding"
                        ],
                    },
                }
            ),
            422,
        )
    except UnicodeDecodeError:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "file_structure_errors": [
                            "File data has invalid UTF-8 encoding"
                        ],
                    },
                }
            ),
            422,
        )
    except HeaderRowEmptyError as e:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "file_structure_errors": e.message,
                    },
                }
            ),
            422,
        )

    # Get the bottom level geo level UID for the survey, this is used to validate the location IDs
    if not geo_level_hierarchy:
        bottom_level_geo_level_uid = None
    else:
        bottom_level_geo_level_uid = geo_level_hierarchy.ordered_geo_levels[
            -1
        ].geo_level_uid

    # Validate the targets data
    record_errors = None
    try:
        targets_upload.validate_records(
            column_mapping,
            bottom_level_geo_level_uid,
            validated_payload.mode.data,
        )
    except InvalidFileStructureError as e:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "file_structure_errors": e.file_structure_errors,
                    },
                }
            ),
            422,
        )
    except InvalidTargetRecordsError as e:
        record_errors = e.record_errors
        if validated_payload.load_successful.data is True:
            # Filter the records that were successfully validated
            targets_upload.filter_successful_records(
                record_errors,
            )

        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": {
                            "record_errors": record_errors,
                        },
                    }
                ),
                422,
            )

    try:
        targets_upload.save_records(
            column_mapping,
            validated_payload.mode.data,
        )

    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    # If load_successful is True and errors were found in the records, return the errors
    if validated_payload.load_successful.data is True and record_errors:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "record_errors": record_errors,
                    },
                }
            ),
            422,
        )
    else:
        return jsonify(message="Success"), 200


@targets_bp.route("", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(TargetsQueryParamValidator)
@custom_permissions_required("READ Targets", "query", "form_uid")
def get_targets(validated_query_params):
    """
    Method to retrieve the targets information from the database
    """

    form_uid = validated_query_params.form_uid.data
    user_uid = current_user.user_uid

    # Check if the logged in user has permission to access the given form

    ## TODO handle cases where these are None
    survey_uid = Form.query.filter_by(form_uid=form_uid).first().survey_uid

    # We need to get the bottom level geo level UID for the survey in order to join in the location information
    if (
        Target.query.filter(
            Target.form_uid == form_uid, Target.location_uid.isnot(None)
        ).first()
        is not None
    ):
        # Get the geo levels for the survey
        geo_levels = GeoLevel.query.filter_by(survey_uid=survey_uid).all()

        try:
            geo_level_hierarchy = GeoLevelHierarchy(geo_levels)
        except InvalidGeoLevelHierarchyError as e:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": {
                            "geo_level_hierarchy": e.geo_level_hierarchy_errors,
                        },
                    }
                ),
                422,
            )

        bottom_level_geo_level_uid = geo_level_hierarchy.ordered_geo_levels[
            -1
        ].geo_level_uid

    else:
        bottom_level_geo_level_uid = None

    target_locations_subquery = (
        build_bottom_level_locations_with_location_hierarchy_subquery(
            survey_uid, bottom_level_geo_level_uid
        )
    )

    targets_query = (
        db.session.query(
            Target,
            TargetStatus,
            target_locations_subquery.c.locations.label("target_locations"),
        )
        .outerjoin(
            TargetStatus,
            Target.target_uid == TargetStatus.target_uid,
        )
        .outerjoin(
            target_locations_subquery,
            Target.location_uid == target_locations_subquery.c.location_uid,
        )
        .filter(Target.form_uid == form_uid)
    )

    # Check if we need to paginate the results
    if "page" in request.args and "per_page" in request.args:
        page = request.args.get("page", None, type=int)
        per_page = request.args.get("per_page", None, type=int)
        targets_query = targets_query.paginate(page=page, per_page=per_page)

        response = jsonify(
            {
                "success": True,
                "data": [
                    {
                        **target.to_dict(),
                        "completed_flag": getattr(
                            target_status, "completed_flag", None
                        ),
                        "refusal_flag": getattr(target_status, "refusal_flag", None),
                        "num_attempts": getattr(target_status, "num_attempts", None),
                        "last_attempt_survey_status": getattr(
                            target_status, "last_attempt_survey_status", None
                        ),
                        "last_attempt_survey_status_label": getattr(
                            target_status, "last_attempt_survey_status_label", None
                        ),
                        "final_survey_status": getattr(
                            target_status, "final_survey_status", None
                        ),
                        "final_survey_status_label": getattr(
                            target_status, "final_survey_status_label", None
                        ),
                        "target_assignable": getattr(
                            target_status, "target_assignable", None
                        ),
                        "webapp_tag_color": getattr(
                            target_status, "webapp_tag_color", None
                        ),
                        "revisit_sections": getattr(
                            target_status, "revisit_sections", None
                        ),
                        "scto_fields": getattr(target_status, "scto_fields", None),
                        "target_locations": target_locations,
                    }
                    for target, target_status, target_locations in targets_query.items
                ],
                "pagination": {
                    "count": targets_query.total,
                    "page": page,
                    "per_page": per_page,
                    "pages": targets_query.pages,
                },
            }
        )

    else:
        response = jsonify(
            {
                "success": True,
                "data": [
                    {
                        **target.to_dict(),
                        **{
                            "completed_flag": getattr(
                                target_status, "completed_flag", None
                            ),
                            "refusal_flag": getattr(
                                target_status, "refusal_flag", None
                            ),
                            "num_attempts": getattr(
                                target_status, "num_attempts", None
                            ),
                            "last_attempt_survey_status": getattr(
                                target_status, "last_attempt_survey_status", None
                            ),
                            "last_attempt_survey_status_label": getattr(
                                target_status, "last_attempt_survey_status_label", None
                            ),
                            "final_survey_status": getattr(
                                target_status, "final_survey_status", None
                            ),
                            "final_survey_status_label": getattr(
                                target_status, "final_survey_status_label", None
                            ),
                            "target_assignable": getattr(
                                target_status, "target_assignable", None
                            ),
                            "webapp_tag_color": getattr(
                                target_status, "webapp_tag_color", None
                            ),
                            "revisit_sections": getattr(
                                target_status, "revisit_sections", None
                            ),
                            "scto_fields": getattr(target_status, "scto_fields", None),
                        },
                        **{"target_locations": target_locations},
                    }
                    for target, target_status, target_locations in targets_query.all()
                ],
            }
        )

    return response, 200


@targets_bp.route("/<int:target_uid>", methods=["GET"])
@logged_in_active_user_required
@custom_permissions_required("READ Targets", "path", "target_uid")
def get_target(target_uid):
    """
    Method to retrieve a target from the database
    """

    # Check if the logged in user has permission to fetch the target

    target = Target.query.filter_by(target_uid=target_uid).first()

    if target is None:
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "message": "Target not found",
                }
            ),
            404,
        )

    ## TODO handle cases where these are None
    survey_uid = Form.query.filter_by(form_uid=target.form_uid).first().survey_uid

    if target.location_uid is not None:
        # Get the geo levels for the survey
        geo_levels = GeoLevel.query.filter_by(survey_uid=survey_uid).all()

        try:
            geo_level_hierarchy = GeoLevelHierarchy(geo_levels)
        except InvalidGeoLevelHierarchyError as e:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": {
                            "geo_level_hierarchy": e.geo_level_hierarchy_errors,
                        },
                    }
                ),
                422,
            )

        bottom_level_geo_level_uid = geo_level_hierarchy.ordered_geo_levels[
            -1
        ].geo_level_uid

    else:
        bottom_level_geo_level_uid = None

    target_locations_subquery = (
        build_bottom_level_locations_with_location_hierarchy_subquery(
            survey_uid, bottom_level_geo_level_uid
        )
    )

    result = (
        db.session.query(
            Target,
            TargetStatus,
            target_locations_subquery.c.locations.label("target_locations"),
        )
        .outerjoin(
            TargetStatus,
            Target.target_uid == TargetStatus.target_uid,
        )
        .outerjoin(
            target_locations_subquery,
            Target.location_uid == target_locations_subquery.c.location_uid,
        )
        .filter(Target.target_uid == target_uid)
        .all()
    )

    response = jsonify(
        {
            "success": True,
            "data": [
                {
                    **target.to_dict(),
                    **{
                        "completed_flag": getattr(
                            target_status, "completed_flag", None
                        ),
                        "refusal_flag": getattr(target_status, "refusal_flag", None),
                        "num_attempts": getattr(target_status, "num_attempts", None),
                        "last_attempt_survey_status": getattr(
                            target_status, "last_attempt_survey_status", None
                        ),
                        "last_attempt_survey_status_label": getattr(
                            target_status, "last_attempt_survey_status_label", None
                        ),
                        "final_survey_status": getattr(
                            target_status, "final_survey_status", None
                        ),
                        "final_survey_status_label": getattr(
                            target_status, "final_survey_status_label", None
                        ),
                        "target_assignable": getattr(
                            target_status, "target_assignable", None
                        ),
                        "webapp_tag_color": getattr(
                            target_status, "webapp_tag_color", None
                        ),
                        "revisit_sections": getattr(
                            target_status, "revisit_sections", None
                        ),
                        "scto_fields": getattr(target_status, "scto_fields", None),
                    },
                    **{"target_locations": target_locations},
                }
                for target, target_status, target_locations in result
            ][0],
        }
    )

    return response, 200


@targets_bp.route("/<int:target_uid>", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(UpdateTarget)
@custom_permissions_required("WRITE Targets", "path", "target_uid")
def update_target(target_uid, validated_payload):
    """
    Method to update a target in the database
    """

    payload = request.get_json()

    location_uid = validated_payload.location_uid.data

    target = Target.query.filter_by(target_uid=target_uid).first()
    if target is None:
        return jsonify({"error": "Target not found"}), 404

    survey_uid = Form.query.filter_by(form_uid=target.form_uid).first().survey_uid

    # Check if the location_uid is valid

    if location_uid is not None:
        # Get the geo levels for the survey
        geo_levels = GeoLevel.query.filter_by(survey_uid=survey_uid).all()

        try:
            geo_level_hierarchy = GeoLevelHierarchy(geo_levels)
        except InvalidGeoLevelHierarchyError as e:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": {
                            "geo_level_hierarchy": e.geo_level_hierarchy_errors,
                        },
                    }
                ),
                422,
            )

        bottom_level_geo_level_uid = geo_level_hierarchy.ordered_geo_levels[
            -1
        ].geo_level_uid

        location = Location.query.filter_by(
            location_uid=location_uid,
            geo_level_uid=bottom_level_geo_level_uid,
        ).first()

        if location is None:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": f"Location UID {location_uid} not found in the database for the bottom level geo level",
                    }
                ),
                404,
            )

    # The payload needs to pass in the same custom field keys as are in the database
    # This is because this method is used to update values but not add/remove/modify columns
    custom_fields_in_db = getattr(target, "custom_fields", None)
    custom_fields_in_payload = payload.get("custom_fields")

    keys_in_db = []
    keys_in_payload = []

    if custom_fields_in_db is not None:
        keys_in_db = custom_fields_in_db.keys()

    if custom_fields_in_payload is not None:
        keys_in_payload = custom_fields_in_payload.keys()

    for payload_key in keys_in_payload:
        if payload_key not in keys_in_db and payload_key != "column_mapping":
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": f"The payload has a custom key with field label {payload_key} that does not exist in the custom fields for the database record. This method can only be used to update values for existing fields, not to add/remove/modify fields",
                    }
                ),
                422,
            )
    for db_key in keys_in_db:
        if db_key not in keys_in_payload and db_key != "column_mapping":
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": f"The payload is missing a custom key with field label {db_key} that exists in the database. This method can only be used to update values for existing fields, not to add/remove/modify fields",
                    }
                ),
                422,
            )
        if db_key == "column_mapping":
            # add column mapping to custom_fields from db
            payload["custom_fields"]["column_mapping"] = custom_fields_in_db[db_key]

    try:
        Target.query.filter_by(target_uid=target_uid).update(
            {
                Target.target_id: validated_payload.target_id.data,
                Target.language: validated_payload.language.data,
                Target.gender: validated_payload.gender.data,
                Target.location_uid: location_uid,
                Target.custom_fields: payload["custom_fields"],
            },
            synchronize_session="fetch",
        )

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify({"success": True}), 200


@targets_bp.route("/<int:target_uid>", methods=["DELETE"])
@logged_in_active_user_required
@custom_permissions_required("WRITE Targets", "path", "target_uid")
def delete_target(target_uid):
    """
    Method to delete a target from the database
    """

    if Target.query.filter_by(target_uid=target_uid).first() is None:
        return jsonify({"error": "Target not found"}), 404

    TargetStatus.query.filter_by(target_uid=target_uid).delete()
    Target.query.filter_by(target_uid=target_uid).delete()

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify({"success": True}), 200


# Patch method to bulk update target details
@targets_bp.route("", methods=["PATCH"])
@logged_in_active_user_required
@validate_payload(BulkUpdateTargetsValidator)
@custom_permissions_required("WRITE Targets", "body", "form_uid")
def bulk_update_targets(validated_payload):
    """
    Method to bulk update targets
    """

    payload = request.get_json()
    form_uid = validated_payload.form_uid.data

    survey_uid = Form.query.filter_by(form_uid=form_uid).first().survey_uid

    column_config = TargetColumnConfig.query.filter(
        TargetColumnConfig.form_uid == form_uid,
    ).all()

    if len(column_config) == 0:
        return (
            jsonify(
                {"success": False, "errors": "Column configuration not found for form"}
            ),
            404,
        )

    # Check if payload keys are in the column config
    for key in payload.keys():
        if key not in ("target_uids", "form_uid", "csrf_token", "location_uid"):
            if key not in [column.column_name for column in column_config]:
                return (
                    jsonify(
                        {
                            "success": False,
                            "errors": f"Column key '{key}' not found in column configuration",
                        }
                    ),
                    422,
                )
        elif key == "location_uid":
            if "bottom_geo_level_location" not in [
                column.column_name for column in column_config
            ]:
                return (
                    jsonify(
                        {
                            "success": False,
                            "errors": f"Location key 'location_uid' provided in payload but column 'bottom_geo_level_location' not found in column configuration",
                        }
                    ),
                    422,
                )

    bulk_editable_fields = {
        "basic_details": [],
        "location": [],
        "custom_fields": [],
    }

    for column in column_config:
        if column.bulk_editable:
            bulk_editable_fields[column.column_type].append(column.column_name)

    for key in payload.keys():
        if key not in ("target_uids", "form_uid", "csrf_token", "location_uid"):
            if (
                key
                not in bulk_editable_fields["basic_details"]
                + bulk_editable_fields["custom_fields"]
            ):
                return (
                    jsonify(
                        {
                            "success": False,
                            "errors": f"Column key {key} is not bulk editable",
                        }
                    ),
                    422,
                )
        elif key == "location_uid":
            if "bottom_geo_level_location" not in bulk_editable_fields["location"]:
                return (
                    jsonify(
                        {
                            "success": False,
                            "errors": f"Location key 'location_uid' provided in payload but column 'bottom_geo_level_location' is not bulk editable",
                        }
                    ),
                    422,
                )

    basic_details_patch_keys = [
        key
        for key in payload.keys()
        if key not in ("target_uids", "form_uid", "csrf_token")
        and key in bulk_editable_fields["basic_details"]
    ]

    location_patch_keys = [
        key
        for key in payload.keys()
        if key == "location_uid"
        and "bottom_geo_level_location" in bulk_editable_fields["location"]
    ]

    custom_fields_patch_keys = [
        key
        for key in payload.keys()
        if key not in ("target_uids", "form_uid", "csrf_token")
        and key in bulk_editable_fields["custom_fields"]
    ]

    # Check if the location_uid is valid
    if "location_uid" in location_patch_keys:
        # Get the geo levels for the survey
        geo_levels = GeoLevel.query.filter_by(survey_uid=survey_uid).all()

        try:
            geo_level_hierarchy = GeoLevelHierarchy(geo_levels)
        except InvalidGeoLevelHierarchyError as e:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": {
                            "geo_level_hierarchy": e.geo_level_hierarchy_errors,
                        },
                    }
                ),
                422,
            )

        bottom_level_geo_level_uid = geo_level_hierarchy.ordered_geo_levels[
            -1
        ].geo_level_uid

        location = Location.query.filter_by(
            location_uid=validated_payload.location_uid.data,
            geo_level_uid=bottom_level_geo_level_uid,
        ).first()

        if location is None:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": f"Location UID {validated_payload.location_uid.data} not found in the database for the bottom level geo level",
                    }
                ),
                404,
            )

    basic_details_and_location_patch_keys = (
        basic_details_patch_keys + location_patch_keys
    )
    if len(basic_details_and_location_patch_keys) > 0:
        Target.query.filter(
            Target.target_uid.in_(validated_payload.target_uids.data)
        ).update(
            {key: payload[key] for key in basic_details_and_location_patch_keys},
            synchronize_session=False,
        )

    if len(custom_fields_patch_keys) > 0:
        for custom_field in custom_fields_patch_keys:
            db.session.execute(
                update(Target)
                .values(
                    custom_fields=func.jsonb_set(
                        Target.custom_fields,
                        "{%s}" % custom_field,
                        cast(
                            payload[custom_field],
                            JSONB,
                        ),
                    )
                )
                .where(Target.target_uid.in_(validated_payload.target_uids.data))
            )

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"success": True}), 200


@targets_bp.route("/column-config", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(UpdateTargetsColumnConfig)
@custom_permissions_required("WRITE Targets", "body", "form_uid")
def update_target_column_config(validated_payload):
    """
    Method to update targets' column configuration
    """

    payload = request.get_json()
    form_uid = validated_payload.form_uid.data

    if (
        Form.query.filter(
            Form.form_uid == form_uid,
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

    TargetColumnConfig.query.filter(
        TargetColumnConfig.form_uid == form_uid,
    ).delete()

    db.session.flush()

    for column in payload["column_config"]:
        if not isinstance(column["bulk_editable"], bool):
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": f"Field 'bulk_editable' must be a boolean",
                    }
                ),
                422,
            )
        if not isinstance(column["contains_pii"], bool):
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": f"Field 'contains_pii' must be a boolean",
                    }
                ),
                422,
            )

        db.session.add(
            TargetColumnConfig(
                form_uid=form_uid,
                column_name=column["column_name"],
                column_type=column["column_type"],
                bulk_editable=column["bulk_editable"],
                contains_pii=column["contains_pii"],
            )
        )

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"success": True}), 200


@targets_bp.route("/column-config", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(TargetsQueryParamValidator)
@custom_permissions_required("READ Targets", "query", "form_uid")
def get_target_column_config(validated_query_params):
    """
    Method to get targets' column configuration
    """

    form_uid = validated_query_params.form_uid.data

    column_config = TargetColumnConfig.query.filter_by(form_uid=form_uid).all()

    config_data = [
        {
            "column_name": column.column_name,
            "column_type": column.column_type,
            "bulk_editable": column.bulk_editable,
            "contains_pii": column.contains_pii,
        }
        for column in column_config
    ]

    location_column = next(
        (column for column in config_data if column["column_type"] == "location"),
        None,
    )

    location_columns = []

    if location_column:
        form = Form.query.filter_by(form_uid=form_uid).first()

        if form is None:
            return (
                jsonify(
                    message=f"The form 'form_uid={form_uid}' could not be found.",
                    success=False,
                ),
                404,
            )

        survey_uid = form.survey_uid
        geo_levels = GeoLevel.query.filter_by(survey_uid=survey_uid).all()

        if geo_levels:
            try:
                geo_level_hierarchy = GeoLevelHierarchy(geo_levels)
            except InvalidGeoLevelHierarchyError as e:
                return (
                    jsonify(
                        {"success": False, "errors": {"geo_level_hierarchy": e.errors}}
                    ),
                    422,
                )

            for i, geo_level in enumerate(geo_level_hierarchy.ordered_geo_levels):
                location_columns.extend(
                    [
                        {
                            "column_key": f"target_locations[{i}].location_id",
                            "column_label": f"{geo_level.geo_level_name} ID",
                        },
                        {
                            "column_key": f"target_locations[{i}].location_name",
                            "column_label": f"{geo_level.geo_level_name} Name",
                        },
                    ]
                )

    # Add target_status columns
    target_status_columns = [
        {
            "column_key": "num_attempts",
            "column_label": "Number of Attempts",
        },
        {
            "column_key": "final_survey_status",
            "column_label": "Final Survey Status",
        },
        {
            "column_key": "final_survey_status_label",
            "column_label": "Final Survey Status Label",
        },
        {
            "column_key": "revisit_sections",
            "column_label": "Revisit Sections",
        },
    ]

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "file_columns": config_data,
                    "location_columns": location_columns,
                    "target_status_columns": target_status_columns,
                },
            }
        ),
        200,
    )


@targets_bp.route("/target-status", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(UpdateTargetStatus)
@custom_permissions_required("WRITE Targets", "body", "form_uid")
def update_target_status(validated_payload):
    """
    Method to update target status
    """

    payload = request.get_json()
    form_uid = validated_payload.form_uid.data

    if (
        Form.query.filter(
            Form.form_uid == form_uid,
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

    subquery = db.session.query(Target.target_uid).filter(Target.form_uid == form_uid)

    db.session.query(TargetStatus).filter(TargetStatus.target_uid.in_(subquery)).delete(
        synchronize_session=False
    )

    db.session.flush()

    for each_target in payload["target_status"]:
        target_id = each_target["target_id"]
        target = Target.query.filter(
            Target.target_id == target_id,
            Target.form_uid == form_uid,
        ).first()

        if target is not None:
            db.session.add(
                TargetStatus(
                    target_uid=target.target_uid,
                    completed_flag=each_target["completed_flag"],
                    refusal_flag=each_target["refusal_flag"],
                    num_attempts=each_target["num_attempts"],
                    last_attempt_survey_status=each_target[
                        "last_attempt_survey_status"
                    ],
                    last_attempt_survey_status_label=each_target[
                        "last_attempt_survey_status_label"
                    ],
                    final_survey_status=each_target["final_survey_status"],
                    final_survey_status_label=each_target["final_survey_status_label"],
                    target_assignable=each_target["target_assignable"],
                    webapp_tag_color=each_target["webapp_tag_color"],
                    revisit_sections=each_target["revisit_sections"],
                    scto_fields=each_target["scto_fields"],
                )
            )
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"success": True}), 200
