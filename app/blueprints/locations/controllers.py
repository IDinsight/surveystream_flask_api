import base64
import binascii

import pandas as pd
from flask import jsonify, request
from flask_login import current_user
from sqlalchemy import Integer, cast, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import case

from app import db
from app.blueprints.surveys.models import Survey
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_payload,
    validate_query_params,
)

from .errors import (
    HeaderRowEmptyError,
    InvalidGeoLevelHierarchyError,
    InvalidGeoLevelMappingError,
    InvalidLocationsError,
)
from .models import GeoLevel, Location
from .routes import locations_bp
from .utils import (
    GeoLevelHierarchy,
    GeoLevelPayloadItem,
    LocationColumnMapping,
    LocationsUpload,
)
from .validators import (
    LocationsFileUploadValidator,
    LocationsQueryParamValidator,
    LocationUpdateParamValidator,
    SurveyGeoLevelsPayloadValidator,
    SurveyGeoLevelsQueryParamValidator,
    SurveyPrimeGeoLevelValidator,
)


@locations_bp.route("/geo-levels", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(SurveyGeoLevelsQueryParamValidator)
@custom_permissions_required("READ Survey Locations", "query", "survey_uid")
def get_survey_geo_levels(validated_query_params):
    """
    Get the geo levels for a given survey
    """

    survey_uid = validated_query_params.survey_uid.data

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

    Update Logic:

    IF New geo level added or existing geo levels deleted or geo level hierarchy is changed:
        All locations and dependent data is deleted
        Insert query for all geo levels

    ELSE Only geo level name is changed:
        No data is deleted
        Update query for geo levels
    """

    survey_uid = validated_query_params.survey_uid.data
    user_uid = current_user.user_uid
    input_geo_levels = validated_payload.geo_levels.data

    payload = request.get_json()

    if payload.get("validate_hierarchy", False):
        geo_levels = [
            GeoLevelPayloadItem(item) for item in validated_payload.geo_levels.data
        ]
        try:
            geo_level_hierarchy = GeoLevelHierarchy(geo_levels)
        except InvalidGeoLevelHierarchyError as e:
            return (
                jsonify({"success": False, "errors": e.geo_level_hierarchy_errors}),
                422,
            )

    # Get the geo level data in the db for the given survey
    existing_geo_levels = GeoLevel.query.filter_by(survey_uid=survey_uid).all()

    geo_level_hierarchy_changed = False
    if existing_geo_levels is None or len(existing_geo_levels) == 0:
        geo_level_hierarchy_changed = True
    else:
        # Check if geo level hierarchy exists
        existing_hierarchy = [
            geo_level
            for geo_level in existing_geo_levels
            if geo_level.parent_geo_level_uid is None
        ]
        if len(existing_hierarchy) == 1:
            # Create a GeoLevelHierarchy object from the existing geo levels
            existing_geo_level_hierarchy = GeoLevelHierarchy(
                [
                    GeoLevelPayloadItem(geo_level.to_dict())
                    for geo_level in existing_geo_levels
                ]
            )
            existing_geo_level_ordered = [
                geo_level.geo_level_uid
                for geo_level in existing_geo_level_hierarchy.ordered_geo_levels
            ]
            if payload.get("validate_hierarchy", False):
                input_geo_levels_ordered = [
                    geo_level.geo_level_uid
                    for geo_level in geo_level_hierarchy.ordered_geo_levels
                ]
            else:
                input_geo_levels_ordered = []
            geo_level_hierarchy_changed = (
                existing_geo_level_ordered != input_geo_levels_ordered
            )
    # Check if there are any new geo levels that need to be inserted
    new_geo_levels = [
        geo_level
        for geo_level in input_geo_levels
        if geo_level["geo_level_uid"] is None
    ]

    try:
        if geo_level_hierarchy_changed or (len(new_geo_levels) > 0):
            # Delete existing target,enumerator,location mapping data
            from app.blueprints.enumerators.models import (
                MonitorLocation,
                SurveyorLocation,
            )
            from app.blueprints.forms.models import Form, SCTOQuestionMapping
            from app.blueprints.targets.models import Target
            from app.blueprints.user_management.models import UserLocation

            form = Form.query.filter_by(survey_uid=survey_uid).first()
            if form is None:
                return (
                    jsonify(
                        {
                            "error": "Form not found",
                        }
                    ),
                    404,
                )
            form_uid = form.form_uid

            Target.query.filter(
                Target.form_uid == form_uid, Target.location_uid is not None
            ).update(
                {
                    Target.location_uid: None,
                },
                synchronize_session=False,
            )

            MonitorLocation.query.filter(MonitorLocation.form_uid == form_uid).delete()
            SurveyorLocation.query.filter(
                SurveyorLocation.form_uid == form_uid
            ).delete()

            UserLocation.query.filter_by(survey_uid=survey_uid).delete()

            # Set location in SCTOQuestionMapping to None
            SCTOQuestionMapping.query.filter_by(form_uid=form_uid).update(
                {
                    SCTOQuestionMapping.locations: None,
                },
                synchronize_session=False,
            )

            # Delete the existing geo levels - Also deletes all locations due to cascade
            GeoLevel.query.filter_by(survey_uid=survey_uid).delete()

            db.session.flush()

            # Insert the new geo levels
            for geo_level in input_geo_levels:
                new_geo_level = GeoLevel(
                    survey_uid=survey_uid,
                    geo_level_uid=geo_level["geo_level_uid"],
                    geo_level_name=geo_level["geo_level_name"],
                    parent_geo_level_uid=geo_level["parent_geo_level_uid"],
                    user_uid=user_uid,
                )

                db.session.add(new_geo_level)
            db.session.commit()

        else:
            # Update the geo levels
            GeoLevel.query.filter(
                GeoLevel.geo_level_uid.in_(
                    [geo_level["geo_level_uid"] for geo_level in input_geo_levels]
                )
            ).update(
                {
                    GeoLevel.geo_level_name: case(
                        {
                            geo_level["geo_level_uid"]: geo_level["geo_level_name"]
                            for geo_level in input_geo_levels
                        },
                        value=GeoLevel.geo_level_uid,
                    ),
                    GeoLevel.parent_geo_level_uid: case(
                        {
                            geo_level["geo_level_uid"]: cast(
                                geo_level["parent_geo_level_uid"], Integer
                            )
                            for geo_level in input_geo_levels
                        },
                        value=GeoLevel.geo_level_uid,
                    ),
                    GeoLevel.user_uid: user_uid,
                },
                synchronize_session=False,
            )
            db.session.commit()
        return jsonify(message="Success"), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@locations_bp.route("/<int:survey_uid>/prime-geo-level", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(SurveyPrimeGeoLevelValidator)
@custom_permissions_required("WRITE Survey Locations", "path", "survey_uid")
def update_prime_geo_level(survey_uid, validated_payload):
    if Survey.query.filter_by(survey_uid=survey_uid).first() is None:
        return jsonify({"error": "Survey not found"}), 404

    # Check if the prime geo level is same as input geo level
    survey = Survey.query.filter_by(survey_uid=survey_uid).first()
    if survey.prime_geo_level_uid == validated_payload.prime_geo_level_uid.data:
        return jsonify(survey.to_dict()), 200
    else:
        try:

            from app.blueprints.forms.models import Form

            # Update the prime geo level
            Survey.query.filter_by(survey_uid=survey_uid).update(
                {
                    Survey.prime_geo_level_uid: validated_payload.prime_geo_level_uid.data,
                },
                synchronize_session=False,
            )
            db.session.flush()

            # Delete location user mapping table entries
            from app.blueprints.user_management.models import UserLocation

            UserLocation.query.filter_by(survey_uid=survey_uid).delete()

            # Check if location column in enumerator column config
            from app.blueprints.enumerators.models import (
                MonitorLocation,
                SurveyorLocation,
            )

            form = Form.query.filter_by(survey_uid=survey_uid).first()
            if form is None:
                return (
                    jsonify(
                        {
                            "error": "Form not found",
                        }
                    ),
                    404,
                )
            form_uid = form.form_uid

            # Delete the existing target,enumerator,location mapping data
            MonitorLocation.query.filter(MonitorLocation.form_uid == form_uid).delete()
            SurveyorLocation.query.filter(
                SurveyorLocation.form_uid == form_uid
            ).delete()

            db.session.commit()
            survey = Survey.query.filter_by(survey_uid=survey_uid).first()
            return jsonify(survey.to_dict()), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500


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

    # We will have to delete the existing locations and dependent data for the survey
    # Delete existing target,enumerator,location mapping data
    from app.blueprints.enumerators.models import MonitorLocation, SurveyorLocation
    from app.blueprints.forms.models import Form
    from app.blueprints.targets.models import Target
    from app.blueprints.user_management.models import UserLocation

    form_uid = Form.query.filter_by(survey_uid=survey_uid).first().form_uid

    Target.query.filter(
        Target.form_uid == form_uid, Target.location_uid is not None
    ).update(
        {
            Target.location_uid: None,
        },
        synchronize_session=False,
    )

    MonitorLocation.query.filter(MonitorLocation.form_uid == form_uid).delete()
    SurveyorLocation.query.filter(SurveyorLocation.form_uid == form_uid).delete()

    UserLocation.query.filter_by(survey_uid=survey_uid).delete()

    Location.query.filter_by(survey_uid=survey_uid).delete()

    db.session.flush()

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


@locations_bp.route("/long", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(LocationsQueryParamValidator)
@custom_permissions_required("READ Survey Locations", "query", "survey_uid")
def get_locations_data_long(validated_query_params):
    """
    Method to retrieve the locations information from the database in long format
    """

    survey_uid = validated_query_params.survey_uid.data
    geo_level_uid = validated_query_params.geo_level_uid.data

    locations_query = (
        db.session.query(
            GeoLevel.geo_level_uid,
            GeoLevel.geo_level_name,
            GeoLevel.parent_geo_level_uid,
            Location.location_uid,
            Location.location_id,
            Location.location_name,
            Location.parent_location_uid,
        )
        .join(Location, GeoLevel.geo_level_uid == Location.geo_level_uid)
        .filter(Location.survey_uid == survey_uid)
    )

    if geo_level_uid is not None:
        locations_query = locations_query.filter(
            Location.geo_level_uid == geo_level_uid
        )

    locations = locations_query.all()

    return (
        jsonify(
            {
                "success": True,
                "data": [
                    {
                        "geo_level_uid": location.geo_level_uid,
                        "geo_level_name": location.geo_level_name,
                        "parent_geo_level_uid": location.parent_geo_level_uid,
                        "location_uid": location.location_uid,
                        "location_id": location.location_id,
                        "location_name": location.location_name,
                        "parent_location_uid": location.parent_location_uid,
                    }
                    for location in locations
                ],
            }
        ),
        200,
    )


@locations_bp.route("", methods=["PUT"])
@logged_in_active_user_required
@validate_query_params(LocationsQueryParamValidator)
@validate_payload(LocationsFileUploadValidator)
@custom_permissions_required("WRITE Survey Locations", "query", "survey_uid")
def append_locations(validated_query_params, validated_payload):
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

    # Get the existing locations for the survey

    existing_locations_df = pd.DataFrame()
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
            continue

        location_column_mapping = column_mapping.get_by_uid(geo_level.geo_level_uid)

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
                "location_id": location_column_mapping["location_id_column"],
                "location_name": location_column_mapping["location_name_column"],
            }
        )

        if i == 0:
            existing_locations_df = pd.concat(
                [existing_locations_df, df], ignore_index=True
            )

        else:
            existing_locations_df = existing_locations_df.merge(
                df,
                how="left",
                left_on="location_uid",
                right_on="parent_location_uid",
            )

            existing_locations_df.drop(
                columns=["parent_location_uid_x", "location_uid_x"], inplace=True
            )
            existing_locations_df.rename(
                columns={
                    "parent_location_uid_y": "parent_location_uid",
                    "location_uid_y": "location_uid",
                },
                inplace=True,
            )

    existing_locations_df.drop(
        columns=["location_uid", "parent_location_uid"], inplace=True
    )

    # Validate the locations data
    try:
        locations_upload.validate_records(
            expected_columns,
            geo_level_hierarchy.ordered_geo_levels,
            column_mapping.geo_level_mapping_lookup,
            existing_locations_df,
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

            if row[1] in existing_locations_df[location_id_column_name].values:
                continue

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


@locations_bp.route("/<int:location_uid>", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(LocationUpdateParamValidator)
@custom_permissions_required("WRITE Survey Locations", "body", "survey_uid")
def update_location(location_uid, validated_payload):
    """
    Update individual location details
    """
    location_name = validated_payload.location_name.data
    parent_location_uid = validated_payload.parent_location_uid.data

    location = Location.query.filter_by(location_uid=location_uid).first()

    if location is None:
        return jsonify({"error": "Location not found"}), 404

    location.location_name = location_name
    location.parent_location_uid = parent_location_uid

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"location": location.to_dict(), "success": True}), 200


@locations_bp.route("/uid", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(SurveyGeoLevelsQueryParamValidator)
@custom_permissions_required("READ Survey Locations", "query", "survey_uid")
def get_locations_with_uid(validated_query_params):
    """
    Method to retrieve the locations information from the database
    Different from get_locations as it returns location_uid for each geo level
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
        expected_columns.append(geo_level.geo_level_name + " UID")

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
        df[geo_level.geo_level_name + " UID"] = df["location_uid"]

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
