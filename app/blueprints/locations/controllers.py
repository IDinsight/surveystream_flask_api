from flask import jsonify, request
from app.utils.utils import (
    logged_in_active_user_required,
    custom_permissions_required,
    validate_query_params,
    validate_payload,
)
from flask_login import current_user
from sqlalchemy import insert, cast, Integer
from sqlalchemy.sql import case
from sqlalchemy.exc import IntegrityError
import pandas as pd
import base64
from app import db
from .models import GeoLevel, Location
from .routes import locations_bp
from .validators import (
    SurveyGeoLevelsQueryParamValidator,
    SurveyGeoLevelsPayloadValidator,
    LocationsFileUploadValidator,
    LocationsQueryParamValidator,
)
from .utils import (
    LocationsUpload,
    GeoLevelHierarchy,
    LocationColumnMapping,
    GeoLevelPayloadItem,
)
from .errors import (
    HeaderRowEmptyError,
    InvalidLocationsError,
    InvalidGeoLevelHierarchyError,
    InvalidGeoLevelMappingError,
)
import binascii


@locations_bp.route("/geo-levels", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(SurveyGeoLevelsQueryParamValidator)
@custom_permissions_required("READ Survey Locations", "query", "survey_uid")
def get_survey_geo_levels(validated_query_params):
    """
    Get the geo levels for a given survey
    """

    survey_uid = validated_query_params.survey_uid.data
    user_uid = current_user.user_uid

    # Check if the logged in user has permission to access the given survey

    # Get the geo levels for the survey
    geo_levels = (
        GeoLevel.query.filter_by(survey_uid=survey_uid)
        .order_by(GeoLevel.geo_level_uid)
        .all()
    )

    response = jsonify(
        {
            "success": True,
            "data": [geo_level.to_dict() for geo_level in geo_levels],
        }
    )
    response.add_etag()

    return response, 200


@locations_bp.route("/geo-levels", methods=["PUT"])
@logged_in_active_user_required
@validate_query_params(SurveyGeoLevelsQueryParamValidator)
@validate_payload(SurveyGeoLevelsPayloadValidator)
@custom_permissions_required("WRITE Survey Locations", "query", "survey_uid")
def update_survey_geo_levels(validated_query_params, validated_payload):
    """
    Method to update the geo levels for a given survey
    """

    survey_uid = validated_query_params.survey_uid.data
    user_uid = current_user.user_uid

    # Check if the logged in user has permission to access the given survey

    # Import the request body payload validator
    payload = request.get_json()

    # If validate_hierarchy is true, validate the hierarchy of the geo levels
    if payload.get("validate_hierarchy"):
        geo_levels = [
            GeoLevelPayloadItem(item) for item in validated_payload.geo_levels.data
        ]

        if len(geo_levels) > 0:
            try:
                GeoLevelHierarchy(geo_levels)
            except InvalidGeoLevelHierarchyError as e:
                return (
                    jsonify({"success": False, "errors": e.geo_level_hierarchy_errors}),
                    422,
                )

    # Get the geo level data in the db for the given survey
    existing_geo_levels = GeoLevel.query.filter_by(survey_uid=survey_uid).all()

    # Find existing geo levels that need to be deleted because they are not in the payload
    for existing_geo_level in existing_geo_levels:
        if existing_geo_level.geo_level_uid not in [
            geo_level.get("geo_level_uid")
            for geo_level in validated_payload.geo_levels.data
        ]:
            try:
                # Update the geo level record so its deletion gets captured by the table logging triggers
                GeoLevel.query.filter(
                    GeoLevel.geo_level_uid == existing_geo_level.geo_level_uid
                ).update(
                    {
                        GeoLevel.user_uid: user_uid,
                        GeoLevel.to_delete: 1,
                    },
                    synchronize_session=False,
                )

                # Delete the geo level record
                GeoLevel.query.filter(
                    GeoLevel.geo_level_uid == existing_geo_level.geo_level_uid
                ).delete()

                db.session.commit()
            except IntegrityError as e:
                db.session.rollback()
                return jsonify(message=str(e)), 500

    # Get the geo levels that need to be updated
    geo_levels_to_update = [
        geo_level
        for geo_level in validated_payload.geo_levels.data
        if geo_level["geo_level_uid"] is not None
    ]
    if len(geo_levels_to_update) > 0:
        try:
            GeoLevel.query.filter(
                GeoLevel.geo_level_uid.in_(
                    [geo_level["geo_level_uid"] for geo_level in geo_levels_to_update]
                )
            ).update(
                {
                    GeoLevel.geo_level_name: case(
                        {
                            geo_level["geo_level_uid"]: geo_level["geo_level_name"]
                            for geo_level in geo_levels_to_update
                        },
                        value=GeoLevel.geo_level_uid,
                    ),
                    GeoLevel.parent_geo_level_uid: case(
                        {
                            geo_level["geo_level_uid"]: cast(
                                geo_level["parent_geo_level_uid"], Integer
                            )
                            for geo_level in geo_levels_to_update
                        },
                        value=GeoLevel.geo_level_uid,
                    ),
                    GeoLevel.user_uid: user_uid,
                },
                synchronize_session=False,
            )

            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            return jsonify(message=str(e)), 500

    # Get the geo levels that need to be created
    geo_levels_to_insert = [
        geo_level
        for geo_level in validated_payload.geo_levels.data
        if geo_level["geo_level_uid"] is None
    ]
    if len(geo_levels_to_insert) > 0:
        for geo_level in geo_levels_to_insert:
            statement = insert(GeoLevel).values(
                geo_level_name=geo_level["geo_level_name"],
                survey_uid=survey_uid,
                parent_geo_level_uid=geo_level["parent_geo_level_uid"],
                user_uid=user_uid,
            )

            db.session.execute(statement)
            db.session.commit()

    return jsonify(message="Success"), 200


@locations_bp.route("", methods=["POST"])
@logged_in_active_user_required
@validate_query_params(LocationsQueryParamValidator)
@validate_payload(LocationsFileUploadValidator)
@custom_permissions_required("WRITE Survey Locations", "query", "survey_uid")
def upload_locations(validated_query_params, validated_payload):
    """
    Method to validate the uploaded locations file and save it
    to the database
    """

    survey_uid = validated_query_params.survey_uid.data

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
                        "file": [],
                        "geo_level_mapping": [],
                    },
                }
            ),
            422,
        )

    try:
        column_mapping = LocationColumnMapping(
            geo_levels, validated_payload.geo_level_mapping.data
        )
    except InvalidGeoLevelMappingError as e:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "geo_level_mapping": e.geo_level_mapping_errors,
                        "file": [],
                    },
                }
            ),
            422,
        )

    # Get the expected columns from the mapped column names
    expected_columns = []
    for geo_level in geo_level_hierarchy.ordered_geo_levels:
        location_type_columns = column_mapping.get_by_uid(geo_level.geo_level_uid)
        expected_columns += [
            location_type_columns["location_id_column"],
            location_type_columns["location_name_column"],
        ]

    # Create a LocationsUpload object from the uploaded file
    try:
        locations_upload = LocationsUpload(
            csv_string=base64.b64decode(
                validated_payload.file.data, validate=True
            ).decode("utf-8")
        )
    except binascii.Error:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "file": ["File data has invalid base64 encoding"],
                        "geo_level_mapping": [],
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
                        "file": ["File data has invalid UTF-8 encoding"],
                        "geo_level_mapping": [],
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
                        "file": e.message,
                        "geo_level_mapping": [],
                    },
                }
            ),
            422,
        )

    # Validate the locations data
    try:
        locations_upload.validate_records(
            expected_columns,
            geo_level_hierarchy.ordered_geo_levels,
            column_mapping.geo_level_mapping_lookup,
        )
    except InvalidLocationsError as e:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "file": e.locations_errors,
                        "geo_level_mapping": [],
                    },
                }
            ),
            422,
        )

    # We will have to delete the existing locations for the survey
    Location.query.filter_by(survey_uid=survey_uid).delete()

    for i, geo_level in enumerate(geo_level_hierarchy.ordered_geo_levels):
        # Get the location_id and location_name column names for the geo level
        location_type_columns = column_mapping.get_by_uid(geo_level.geo_level_uid)
        location_id_column_name = location_type_columns["location_id_column"]
        location_name_column_name = location_type_columns["location_name_column"]

        columns = [location_id_column_name, location_name_column_name]

        parent_geo_level_uid = geo_level.parent_geo_level_uid

        parent_locations = {}
        parent_location_id_column_name = None

        if parent_geo_level_uid is not None:
            parent_locations = {
                str(location.location_id): location.location_uid
                for location in Location.query.filter_by(
                    survey_uid=survey_uid, geo_level_uid=parent_geo_level_uid
                )
            }

            parent_location_id_column_name = column_mapping.get_by_uid(
                parent_geo_level_uid
            )["location_id_column"]

            columns.append(parent_location_id_column_name)

        # Create and add location models for the geo level

        location_records_to_insert = []
        for i, row in enumerate(
            locations_upload.locations_df[columns].drop_duplicates().itertuples()
        ):
            parent_location_uid = None
            if parent_geo_level_uid is not None:
                parent_location_uid = parent_locations.get(str(row[3]))

            location_records_to_insert.append(
                {
                    "survey_uid": survey_uid,
                    "location_id": row[1],
                    "location_name": row[2],
                    "parent_location_uid": parent_location_uid,
                    "geo_level_uid": geo_level.geo_level_uid,
                }
            )

            # Insert the records in batches of 1000
            if i > 0 and i % 1000 == 0:
                db.session.execute(insert(Location).values(location_records_to_insert))
                db.session.flush()
                location_records_to_insert.clear()

        # We need to flush the session to get the location_uids
        # These will be used to set the parent_location_uids for the next geo level
        if len(location_records_to_insert) > 0:
            db.session.execute(insert(Location).values(location_records_to_insert))
            db.session.flush()

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify(message="Success"), 200


@locations_bp.route("", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(SurveyGeoLevelsQueryParamValidator)
@custom_permissions_required("READ Survey Locations", "query", "survey_uid")
def get_locations(validated_query_params):
    """
    Method to retrieve the locations information from the database
    """

    survey_uid = validated_query_params.survey_uid.data
    user_uid = current_user.user_uid

    # Check if the logged in user has permission to access the given survey

    # Get the geo levels for the survey
    geo_levels = GeoLevel.query.filter_by(survey_uid=survey_uid).all()

    # If there are no geo levels, return an empty response
    if geo_levels is None or len(geo_levels) == 0:
        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "records": [],
                        "ordered_columns": [],
                    },
                }
            ),
            200,
        )

    # Validate the geo level hierarchy

    try:
        geo_level_hierarchy = GeoLevelHierarchy(geo_levels)
    except InvalidGeoLevelHierarchyError as e:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "geo_level_hierarchy": "The locations could not be returned because the location type hierarchy for this survey is invalid. Please navigate to the location type hierarchy page to view and address the specific errors.",
                    },
                }
            ),
            500,
        )

    # Get the expected columns from the mapped column names
    expected_columns = []
    for geo_level in geo_level_hierarchy.ordered_geo_levels:
        expected_columns.append(geo_level.geo_level_name + " ID")
        expected_columns.append(geo_level.geo_level_name + " Name")

    final_df = pd.DataFrame()
    for i, geo_level in enumerate(geo_level_hierarchy.ordered_geo_levels):
        locations = (
            db.session.query(
                Location.location_uid,
                Location.location_id,
                Location.location_name,
                Location.parent_location_uid,
            )
            .filter_by(survey_uid=survey_uid, geo_level_uid=geo_level.geo_level_uid)
            .all()
        )

        if locations is None or len(locations) == 0:
            return (
                jsonify(
                    {
                        "success": True,
                        "data": {
                            "records": [],
                            "ordered_columns": expected_columns,
                        },
                    }
                ),
                200,
            )

        df = pd.DataFrame(
            [
                {
                    "location_uid": location.location_uid,
                    "location_id": location.location_id,
                    "location_name": location.location_name,
                    "parent_location_uid": location.parent_location_uid,
                }
                for location in locations
            ]
        ).rename(
            columns={
                "location_id": geo_level.geo_level_name + " ID",
                "location_name": geo_level.geo_level_name + " Name",
            }
        )

        if i == 0:
            final_df = pd.concat([final_df, df], ignore_index=True)

        else:
            final_df = final_df.merge(
                df,
                how="left",
                left_on="location_uid",
                right_on="parent_location_uid",
            )

            final_df.drop(
                columns=["parent_location_uid_x", "location_uid_x"], inplace=True
            )
            final_df.rename(
                columns={
                    "parent_location_uid_y": "parent_location_uid",
                    "location_uid_y": "location_uid",
                },
                inplace=True,
            )

    final_df.drop(columns=["location_uid", "parent_location_uid"], inplace=True)

    response = jsonify(
        {
            "success": True,
            "data": {
                "records": final_df.to_dict(orient="records"),
                "ordered_columns": expected_columns,
            },
        }
    )

    return response, 200
