from flask import jsonify, request
from app.utils.utils import logged_in_active_user_required
from flask_login import current_user
from sqlalchemy import insert, cast, Integer
from sqlalchemy.sql import case
from sqlalchemy.exc import IntegrityError
import pandas as pd
import numpy as np
from csv import DictReader
import base64
import io
from app import db
from .models import GeoLevel, Location
from .routes import locations_bp
from .validators import (
    SurveyGeoLevelsQueryParamValidator,
    SurveyGeoLevelsPayloadValidator,
    LocationsFileUploadValidator,
    LocationsQueryParamValidator,
)


@locations_bp.route("/geo-levels", methods=["GET"])
@logged_in_active_user_required
def get_survey_geo_levels():
    """
    Get the geo levels for a given survey
    """

    # Validate the query parameter
    query_param_validator = SurveyGeoLevelsQueryParamValidator.from_json(request.args)
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

    survey_uid = request.args.get("survey_uid")
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
def update_survey_geo_levels():
    # Validate the query parameter
    query_param_validator = SurveyGeoLevelsQueryParamValidator.from_json(request.args)
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

    survey_uid = request.args.get("survey_uid")
    user_uid = current_user.user_uid

    # Check if the logged in user has permission to access the given survey

    # Import the request body payload validator
    payload = request.get_json()
    payload_validator = SurveyGeoLevelsPayloadValidator.from_json(payload)

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    # Validate the request body payload
    if payload_validator.validate():
        # If validate_hierarchy is true, validate the hierarchy of the geo levels
        if payload.get("validate_hierarchy"):
            errors_list = []

            geo_levels = payload_validator.geo_levels.data

            # Exactly one geo level should have no parent
            top_level_geo_level_count = 0
            for geo_level in geo_levels:
                if geo_level["parent_geo_level_uid"] is None:
                    top_level_geo_level_count += 1
            if top_level_geo_level_count != 1:
                errors_list.append(
                    f"The hierarchy should have exactly one top level geo level (ie, a geo level with no parent). The current hierarchy has {top_level_geo_level_count} geo levels with no parent."
                )

            # Each parent geo level should be one of the geo levels in the payload
            geo_level_uids = [geo_level["geo_level_uid"] for geo_level in geo_levels]
            for geo_level in geo_levels:
                if (
                    geo_level["parent_geo_level_uid"] is not None
                    and geo_level["parent_geo_level_uid"] not in geo_level_uids
                ):
                    errors_list.append(
                        f"Geo level '{geo_level['geo_level_name']}' references a parent geo level with geo_level_uid={geo_level['parent_geo_level_uid']} that is not found in the hierarchy."
                    )

            # A geo level should not be its own parent
            for geo_level in geo_levels:
                if geo_level["parent_geo_level_uid"] == geo_level["geo_level_uid"]:
                    errors_list.append(
                        f"Geo level '{geo_level['geo_level_name']}' is referenced as its own parent. Self-referencing is not allowed."
                    )

            # Each geo level should be referenced as a parent exactly once
            parent_geo_level_uids = [
                geo_level["parent_geo_level_uid"]
                for geo_level in geo_levels
                if geo_level["parent_geo_level_uid"] is not None
            ]
            for geo_level in geo_levels:
                parent_reference_count = 0
                for parent_geo_level_uid in parent_geo_level_uids:
                    if geo_level["geo_level_uid"] == parent_geo_level_uid:
                        parent_reference_count += 1
                if parent_reference_count != 1:
                    errors_list.append(
                        f"Each geo level should be referenced as a parent geo level exactly once. Geo level '{geo_level['geo_level_name']}' is referenced as a parent {parent_reference_count} times."
                    )

            if len(errors_list) > 0:
                return (
                    jsonify({"success": False, "errors": errors_list}),
                    422,
                )

        # Get the geo level data in the db for the given survey
        existing_geo_levels = GeoLevel.query.filter_by(survey_uid=survey_uid).all()

        # Find existing geo levels that need to be deleted because they are not in the payload
        for existing_geo_level in existing_geo_levels:
            if existing_geo_level.geo_level_uid not in [
                geo_level.get("geo_level_uid")
                for geo_level in payload_validator.geo_levels.data
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
            for geo_level in payload_validator.geo_levels.data
            if geo_level["geo_level_uid"] is not None
        ]
        if len(geo_levels_to_update) > 0:
            try:
                GeoLevel.query.filter(
                    GeoLevel.geo_level_uid.in_(
                        [
                            geo_level["geo_level_uid"]
                            for geo_level in geo_levels_to_update
                        ]
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
            for geo_level in payload_validator.geo_levels.data
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

    else:
        return jsonify({"success": False, "errors": payload_validator.errors}), 422


@locations_bp.route("", methods=["POST"])
def upload_locations():
    """
    Method to validate the uploaded locations file and save it
    to the database
    """

    # Validate the query parameter
    query_param_validator = LocationsQueryParamValidator.from_json(request.args)
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

    survey_uid = request.args.get("survey_uid")

    payload_validator = LocationsFileUploadValidator.from_json(request.get_json())

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

    # Get the geo level mapping from the payload
    geo_level_mapping = payload_validator.geo_level_mapping.data

    # Get the geo levels for the survey
    geo_levels = GeoLevel.query.filter_by(survey_uid=survey_uid).all()

    # Create an ordered list of geo levels based on the geo level hierarchy
    # IMPORTANT: This assumes that the geo level hierarchy has been validated
    ordered_geo_levels = [
        geo_level for geo_level in geo_levels if geo_level.parent_geo_level_uid is None
    ]
    for i in range(len(geo_levels) - 1):
        for geo_level in geo_levels:
            if geo_level.parent_geo_level_uid == ordered_geo_levels[i].geo_level_uid:
                ordered_geo_levels.append(geo_level)

    # Validate the geo level mapping
    mapping_errors = []

    # Each geo level should appear in the mapping exactly once
    for geo_level in geo_levels:
        geo_level_mapping_count = 0
        for mapping in geo_level_mapping:
            if geo_level.geo_level_uid == mapping["geo_level_uid"]:
                geo_level_mapping_count += 1
        if geo_level_mapping_count != 1:
            mapping_errors.append(
                f"Each geo level defined in the geo level hierarchy should appear exactly once in the geo level column mapping. Geo level '{geo_level.geo_level_name}' appears {geo_level_mapping_count} time(s) in the geo level mapping."
            )

    # Each geo level in the mapping should be one of the geo levels for the survey
    for mapping in geo_level_mapping:
        if mapping["geo_level_uid"] not in [
            geo_level.geo_level_uid for geo_level in geo_levels
        ]:
            mapping_errors.append(
                f"Geo level '{mapping['geo_level_uid']}' in the geo level column mapping is not one of the geo levels for the survey."
            )

    # Mapped column names should be unique
    column_names = []
    for mapping in geo_level_mapping:
        if mapping["location_id_column"] in column_names:
            mapping_errors.append(
                f"Column name '{mapping['location_id_column']}' appears more than once in the geo level column mapping. Column names should be unique."
            )
        if mapping["location_name_column"] in column_names:
            mapping_errors.append(
                f"Column name '{mapping['location_name_column']}' appears more than once in the geo level column mapping. Column names should be unique."
            )
        column_names.append(mapping["location_id_column"])
        column_names.append(mapping["location_name_column"])

    if len(mapping_errors) > 0:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "geo_level_mapping": mapping_errors,
                    },
                }
            ),
            422,
        )
    # Create a lookup object for the geo level mapping
    geo_level_mapping_lookup = {
        mapping["geo_level_uid"]: mapping for mapping in geo_level_mapping
    }

    # Get the expected columns from the mapped column names
    expected_columns = []
    for geo_level in ordered_geo_levels:
        expected_columns.append(
            geo_level_mapping_lookup[geo_level.geo_level_uid]["location_id_column"]
        )
        expected_columns.append(
            geo_level_mapping_lookup[geo_level.geo_level_uid]["location_name_column"]
        )

    # Read the csv content into a dataframe
    locations_df = pd.read_csv(
        io.StringIO(base64.b64decode(payload_validator.file.data).decode("utf-8")),
        dtype=str,
        keep_default_na=False,
    )

    # Override the column names in case there are duplicate column names
    # This is needed because pandas will append a .1 to the duplicate column name
    # Get column names from csv file using DictReader
    col_names = DictReader(
        io.StringIO(base64.b64decode(payload_validator.file.data).decode("utf-8"))
    ).fieldnames
    locations_df.columns = col_names

    # Strip white space from all columns
    for index in range(locations_df.shape[1]):
        locations_df.iloc[:, index] = locations_df.iloc[:, index].astype(str)
        locations_df.iloc[:, index] = locations_df.iloc[:, index].str.strip()

    # Replace empty strings with NaN
    locations_df = locations_df.replace("", np.nan)

    # Shift the index by 1 so that the row numbers start at 1
    locations_df.index += 1

    # Rename the index column to row_number
    locations_df.index.name = "row_number"

    # Validate the csv file

    file_errors = []

    # Check if any columns were able to be read in - if not the first row is probably empty
    if len(col_names) == 0:
        file_errors.append(
            "Column names were not found in the file. Make sure the first row of the file contains column names."
        )

    # Each mapped column should appear in the csv file exactly once
    file_columns = locations_df.columns.to_list()
    for column_name in expected_columns:
        if file_columns.count(column_name) != 1:
            file_errors.append(
                f"Column name '{column_name}' from the column mapping appears {file_columns.count(column_name)} time(s) in the uploaded file. It should appear exactly once."
            )

    # Each column in the csv file should be mapped exactly once
    for column_name in file_columns:
        if expected_columns.count(column_name) != 1:
            file_errors.append(
                f"Column name '{column_name}' in the csv file appears {expected_columns.count(column_name)} time(s) in the geo level column mapping. It should appear exactly once."
            )

    # The file should contain no blank fields
    blank_fields = [
        f"'column': {locations_df.columns[j]}, 'row': {i + 1}"
        for i, j in zip(*np.where(pd.isnull(locations_df)))
    ]
    if len(blank_fields) > 0:
        blank_fields_formatted = "\n".join(item for item in blank_fields)
        file_errors.append(
            f"The file contains {len(blank_fields)} blank fields. Blank fields are not allowed. Blank fields are found in the following columns and rows:\n{blank_fields_formatted}"
        )

    # The file should have no duplicate rows
    duplicates_df = locations_df[locations_df.duplicated(keep=False)]
    if len(duplicates_df) > 0:
        file_errors.append(
            f"The file has {len(duplicates_df)} duplicate rows. Duplicate rows are not allowed. The following rows are duplicates:\n{duplicates_df.to_string()}"
        )

    # A location cannot be assigned to multiple parents
    for geo_level in reversed(ordered_geo_levels):
        if geo_level.parent_geo_level_uid is not None:
            geo_level_id_column_name = geo_level_mapping_lookup[
                geo_level.geo_level_uid
            ]["location_id_column"]
            parent_geo_level_id_column_name = geo_level_mapping_lookup[
                geo_level.parent_geo_level_uid
            ]["location_id_column"]
            # If we deduplicate on the parent location id column and the location id column, the number of rows should be the same as just deduplicating on the location id column
            # If this check fails we know that the location id column has locations that are mapped to more than one parent
            if len(
                locations_df[
                    locations_df.duplicated(
                        subset=[
                            parent_geo_level_id_column_name,
                            geo_level_id_column_name,
                        ],
                    )
                ]
            ) != len(
                locations_df[
                    locations_df.duplicated(
                        subset=[geo_level_id_column_name],
                    )
                ]
            ):
                file_errors.append(
                    f"Geo level {geo_level.geo_level_name} has location id's that are mapped to more than one parent location in column {parent_geo_level_id_column_name}. A location (defined by the location id column) cannot be assigned to multiple parents. Make sure to use a unique location id for each location. The following rows have location id's that are mapped to more than one parent location:\n{locations_df[locations_df.drop_duplicates(subset=[parent_geo_level_id_column_name, geo_level_id_column_name]).duplicated(subset=[geo_level_id_column_name], keep=False).reindex(locations_df.index, fill_value=False)].to_string()}"
                )

    if len(file_errors) > 0:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "file": file_errors,
                    },
                }
            ),
            422,
        )

    # We will have to delete the existing locations for the survey
    Location.query.filter_by(survey_uid=survey_uid).delete()

    for i, geo_level in enumerate(ordered_geo_levels):
        # Get the location_id and location_name column names for the geo level
        location_id_column_name = geo_level_mapping_lookup[geo_level.geo_level_uid][
            "location_id_column"
        ]
        location_name_column_name = geo_level_mapping_lookup[geo_level.geo_level_uid][
            "location_name_column"
        ]

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

            parent_location_id_column_name = geo_level_mapping_lookup[
                parent_geo_level_uid
            ]["location_id_column"]

            columns.append(parent_location_id_column_name)

        # Create and add location models for the geo level
        for i, row in enumerate(locations_df[columns].drop_duplicates().itertuples()):
            parent_location_uid = None
            if parent_geo_level_uid is not None:
                parent_location_uid = parent_locations.get(str(row[3]))

            location = Location(
                survey_uid=survey_uid,
                location_id=row[1],
                location_name=row[2],
                parent_location_uid=parent_location_uid,
                geo_level_uid=geo_level.geo_level_uid,
            )

            db.session.add(location)

            if i % 1000 == 0:
                db.session.flush()

        # We need to flush the session to get the location_uids
        # These will be used to set the parent_location_uids for the next geo level
        db.session.flush()

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    # If validations fail, return error
    return jsonify(message="Success"), 200


@locations_bp.route("", methods=["GET"])
def get_locations():
    """
    Method to retrieve the locations information from the database
    """

    # Validate the query parameter
    query_param_validator = SurveyGeoLevelsQueryParamValidator.from_json(request.args)
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

    survey_uid = request.args.get("survey_uid")
    user_uid = current_user.user_uid

    # Check if the logged in user has permission to access the given survey

    # Get the geo levels for the survey
    geo_levels = GeoLevel.query.filter_by(survey_uid=survey_uid).all()

    # Create an ordered list of geo levels based on the geo level hierarchy
    # IMPORTANT: This assumes that the geo level hierarchy has been validated
    ordered_geo_levels = [
        geo_level for geo_level in geo_levels if geo_level.parent_geo_level_uid is None
    ]
    for i in range(len(geo_levels) - 1):
        for geo_level in geo_levels:
            if geo_level.parent_geo_level_uid == ordered_geo_levels[i].geo_level_uid:
                ordered_geo_levels.append(geo_level)

    # Get the expected columns from the mapped column names
    expected_columns = []
    for geo_level in ordered_geo_levels:
        expected_columns.append(geo_level.geo_level_name + " ID")
        expected_columns.append(geo_level.geo_level_name + " Name")

    final_df = pd.DataFrame()
    for i, geo_level in enumerate(ordered_geo_levels):
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
