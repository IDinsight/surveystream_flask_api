from flask import jsonify, request
from app.utils.utils import logged_in_active_user_required
from flask_login import current_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert, JSONB
from sqlalchemy.sql.functions import func
from sqlalchemy import update, cast, insert
import base64
from sqlalchemy.orm import aliased
from app import db
from app.blueprints.surveys.models import Survey
from app.blueprints.forms.models import ParentForm
from app.blueprints.locations.models import Location, GeoLevel
from .models import (
    Target,
    TargetStatus,
    TargetColumnConfig,
)
from .routes import targets_bp
from .validators import (
    TargetsFileUploadValidator,
    TargetsQueryParamValidator,
    UpdateTarget,
    BulkUpdateTargetsValidator,
    UpdateTargetsColumnConfig,
)
from .utils import (
    TargetsUpload,
    TargetColumnMapping,
)
from .queries import build_bottom_level_locations_with_location_hierarchy_subquery
from app.blueprints.locations.utils import GeoLevelHierarchy
from app.blueprints.locations.errors import InvalidGeoLevelHierarchyError
from .errors import (
    HeaderRowEmptyError,
    InvalidTargetRecordsError,
    InvalidFileStructureError,
    InvalidColumnMappingError,
)
import binascii


@targets_bp.route("", methods=["POST"])
def upload_targets():
    """
    Method to validate the uploaded targets file and save it to the database
    """

    # Validate the query parameter
    query_param_validator = TargetsQueryParamValidator.from_json(request.args)
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

    form_uid = request.args.get("form_uid")

    # Get the survey UID from the form UID
    form = ParentForm.query.filter_by(form_uid=form_uid).first()

    if form is None:
        return (
            jsonify(
                message=f"The form 'form_uid={form_uid}' could not be found. Cannot upload targets for an undefined form."
            ),
            404,
        )

    survey_uid = form.survey_uid

    payload = request.get_json()
    payload_validator = TargetsFileUploadValidator.from_json(payload)

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    # Validate the request body payload
    if not payload_validator.validate():
        return (
            jsonify(
                {
                    "success": False,
                    "errors": payload_validator.errors,
                }
            ),
            422,
        )

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

    try:
        column_mapping = TargetColumnMapping(
            payload_validator.column_mapping.data, geo_levels
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

    # Get the expected columns from the mapped column names
    expected_columns = [
        column_mapping.target_id,
    ]

    if hasattr(column_mapping, "language"):
        expected_columns.append(column_mapping.language)

    if hasattr(column_mapping, "gender"):
        expected_columns.append(column_mapping.gender)

    if hasattr(column_mapping, "location_id_column"):
        expected_columns.append(column_mapping.location_id_column)

    if hasattr(column_mapping, "custom_fields"):
        for custom_field in column_mapping.custom_fields:
            expected_columns.append(custom_field["column_name"])

    # Create a TargetsUpload object from the uploaded file
    try:
        targets_upload = TargetsUpload(
            csv_string=base64.b64decode(
                payload_validator.file.data, validate=True
            ).decode("utf-8")
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

    # Validate the targets data
    try:
        targets_upload.validate_records(
            expected_columns,
            column_mapping,
            geo_level_hierarchy.ordered_geo_levels[-1].geo_level_uid,
            form,
            payload_validator.mode.data,
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

    if payload_validator.mode.data == "overwrite":
        Target.query.filter_by(form_uid=form_uid).delete()

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify(message=str(e)), 500

    # Create a location UID lookup if the location ID column is present
    if hasattr(column_mapping, "location_id_column"):
        # Get the location UID from the location ID
        locations = Location.query.filter(
            Location.location_id.in_(
                targets_upload.targets_df[column_mapping.location_id_column]
                .drop_duplicates()
                .tolist()
            ),
            Location.survey_uid == survey_uid,
        ).with_entities(Location.location_uid, Location.location_id)

        # Create a dictionary of location ID to location UID
        location_uid_lookup = {
            location.location_id: location.location_uid for location in locations.all()
        }

    # Insert the targets into the database
    targets_upload.targets_df = targets_upload.targets_df[expected_columns]
    records_to_insert = []
    for i, row in enumerate(targets_upload.targets_df.drop_duplicates().itertuples()):
        target_dict = {
            "form_uid": form_uid,
            "target_id": row[1],
        }

        # Add the language if it exists
        if hasattr(column_mapping, "language"):
            col_index = (
                targets_upload.targets_df.columns.get_loc("language") + 1
            )  # Add 1 to the index to account for the df index
            target_dict["language"] = row[col_index]

        # Add the gender if it exists
        if hasattr(column_mapping, "gender"):
            col_index = (
                targets_upload.targets_df.columns.get_loc("gender") + 1
            )  # Add 1 to the index to account for the df index
            target_dict["gender"] = row[col_index]

        if hasattr(column_mapping, "location_id_column"):
            col_index = (
                targets_upload.targets_df.columns.get_loc(
                    column_mapping.location_id_column
                )
                + 1
            )
            target_dict["location_uid"] = location_uid_lookup[row[col_index]]

        # Add the custom fields if they exist
        if hasattr(column_mapping, "custom_fields"):
            custom_fields = {}
            for custom_field in column_mapping.custom_fields:
                col_index = (
                    targets_upload.targets_df.columns.get_loc(
                        custom_field["column_name"]
                    )
                    + 1
                )  # Add 1 to the index to account for the df index
                custom_fields[custom_field["field_label"]] = row[col_index]
            target_dict["custom_fields"] = custom_fields

        records_to_insert.append(target_dict)

        # Insert the records in batches of 1000
        if i > 0 and i % 1000 == 0:
            db.session.execute(insert(Target).values(records_to_insert))
            db.session.flush()
            records_to_insert.clear()

    if len(records_to_insert) > 0:
        db.session.execute(insert(Target).values(records_to_insert))

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify(message="Success"), 200


@targets_bp.route("", methods=["GET"])
def get_targets():
    """
    Method to retrieve the targets information from the database
    """

    # Validate the query parameter
    query_param_validator = TargetsQueryParamValidator.from_json(request.args)
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

    form_uid = request.args.get("form_uid")
    user_uid = current_user.user_uid

    # Check if the logged in user has permission to access the given form

    # This will be used to join in the locations hierarchy for each target

    ## TODO handle cases where these are None
    survey_uid = ParentForm.query.filter_by(form_uid=form_uid).first().survey_uid

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
        .filter(Target.form_uid == form_uid)
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
                        "target_assignable": getattr(
                            target_status, "target_assignable", None
                        ),
                        "webapp_tag_color": getattr(
                            target_status, "webapp_tag_color", None
                        ),
                        "revisit_sections": getattr(
                            target_status, "revisit_sections", None
                        ),
                    },
                    **{"target_locations": target_locations},
                }
                for target, target_status, target_locations in result
            ],
        }
    )

    return response, 200


@targets_bp.route("/<int:target_uid>", methods=["GET"])
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
    survey_uid = ParentForm.query.filter_by(form_uid=target.form_uid).first().survey_uid

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
                        "target_assignable": getattr(
                            target_status, "target_assignable", None
                        ),
                        "webapp_tag_color": getattr(
                            target_status, "webapp_tag_color", None
                        ),
                        "revisit_sections": getattr(
                            target_status, "revisit_sections", None
                        ),
                    },
                    **{"target_locations": target_locations},
                }
                for target, target_status, target_locations in result
            ][0],
        }
    )

    return response, 200


@targets_bp.route("/<int:target_uid>", methods=["PUT"])
def update_target(target_uid):
    """
    Method to update a target in the database
    """

    payload = request.get_json()
    payload_validator = UpdateTarget.from_json(payload)

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if payload_validator.validate():
        target = Target.query.filter_by(target_uid=target_uid).first()
        if target is None:
            return jsonify({"error": "Target not found"}), 404

        survey_uid = (
            ParentForm.query.filter_by(form_uid=target.form_uid).first().survey_uid
        )

        # Check if the location_uid is valid

        if payload_validator.location_uid.data is not None:
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
                location_uid=payload_validator.location_uid.data,
                geo_level_uid=bottom_level_geo_level_uid,
            ).first()

            if location is None:
                return (
                    jsonify(
                        {
                            "success": False,
                            "errors": f"Location UID {payload_validator.location_uid.data} not found in the database for the bottom level geo level",
                        }
                    ),
                    404,
                )
        try:
            Target.query.filter_by(target_uid=target_uid).update(
                {
                    Target.target_id: payload_validator.target_id.data,
                    Target.language: payload_validator.language.data,
                    Target.gender: payload_validator.gender.data,
                    Target.location_uid: payload_validator.location_uid.data,
                    Target.custom_fields: payload["custom_fields"],
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


@targets_bp.route("/<int:target_uid>", methods=["DELETE"])
def delete_target(target_uid):
    """
    Method to delete a target from the database
    """

    if Target.query.filter_by(target_uid=target_uid).first() is None:
        return jsonify({"error": "Target not found"}), 404

    Target.query.filter_by(target_uid=target_uid).delete()

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify({"success": True}), 200


# Patch method to bulk update enumerator details
@targets_bp.route("", methods=["PATCH"])
def bulk_update_targets():
    """
    Method to bulk update enumerators
    """

    payload = request.get_json()
    payload_validator = BulkUpdateTargetsValidator.from_json(payload)

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if not payload_validator.validate():
        return jsonify({"success": False, "errors": payload_validator.errors}), 422

    survey_uid = (
        ParentForm.query.filter_by(form_uid=payload_validator.form_uid.data)
        .first()
        .survey_uid
    )

    column_config = TargetColumnConfig.query.filter(
        TargetColumnConfig.form_uid == payload_validator.form_uid.data,
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
            location_uid=payload_validator.location_uid.data,
            geo_level_uid=bottom_level_geo_level_uid,
        ).first()

        if location is None:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": f"Location UID {payload_validator.location_uid.data} not found in the database for the bottom level geo level",
                    }
                ),
                404,
            )

    basic_details_and_location_patch_keys = (
        basic_details_patch_keys + location_patch_keys
    )
    if len(basic_details_and_location_patch_keys) > 0:
        Target.query.filter(
            Target.target_uid.in_(payload_validator.target_uids.data)
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
                .where(Target.target_uid.in_(payload_validator.target_uids.data))
            )

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"success": True}), 200


@targets_bp.route("/column-config", methods=["PUT"])
def update_target_column_config():
    """
    Method to update targets' column configuration
    """

    payload = request.get_json()
    payload_validator = UpdateTargetsColumnConfig.from_json(payload)

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if not payload_validator.validate():
        return jsonify({"success": False, "errors": payload_validator.errors}), 422

    if (
        ParentForm.query.filter(
            ParentForm.form_uid == payload_validator.form_uid.data,
        ).first()
        is None
    ):
        return (
            jsonify(
                {
                    "success": False,
                    "errors": f"Form with UID {payload_validator.form_uid.data} does not exist",
                }
            ),
            422,
        )

    TargetColumnConfig.query.filter(
        TargetColumnConfig.form_uid == payload_validator.form_uid.data,
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
                form_uid=payload_validator.form_uid.data,
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
def get_target_column_config():
    """
    Method to get targets' column configuration
    """

    payload_validator = TargetsQueryParamValidator(request.args)

    if not payload_validator.validate():
        return jsonify({"success": False, "errors": payload_validator.errors}), 422

    column_config = TargetColumnConfig.query.filter(
        TargetColumnConfig.form_uid == payload_validator.form_uid.data,
    ).all()

    return jsonify(
        {
            "success": True,
            "data": [
                {
                    "column_name": column.column_name,
                    "column_type": column.column_type,
                    "bulk_editable": column.bulk_editable,
                    "contains_pii": column.contains_pii,
                }
                for column in column_config
            ],
        }
    )
