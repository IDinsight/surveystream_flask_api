from flask import jsonify, request
from app.utils.utils import logged_in_active_user_required
from flask_login import current_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert, JSONB
from sqlalchemy.sql.functions import func
from sqlalchemy import update, cast
import base64
from sqlalchemy.orm import aliased
from app import db
from app.blueprints.surveys.models import Survey
from app.blueprints.forms.models import ParentForm
from app.blueprints.locations.models import Location, GeoLevel
from .models import (
    Enumerator,
    SurveyorForm,
    SurveyorLocation,
    MonitorForm,
    MonitorLocation,
    EnumeratorColumnConfig,
)
from .routes import enumerators_bp
from .validators import (
    EnumeratorsFileUploadValidator,
    EnumeratorsQueryParamValidator,
    GetEnumeratorsQueryParamValidator,
    UpdateEnumerator,
    CreateEnumeratorRole,
    UpdateEnumeratorRole,
    DeleteEnumeratorRole,
    UpdateEnumeratorRoleStatus,
    GetEnumeratorRolesQueryParamValidator,
    BulkUpdateEnumeratorsValidator,
    BulkUpdateEnumeratorsRoleLocationValidator,
    UpdateEnumeratorsColumnConfig,
    EnumeratorColumnConfigQueryParamValidator,
)
from .utils import (
    EnumeratorsUpload,
    EnumeratorColumnMapping,
)
from .queries import build_prime_locations_with_location_hierarchy_subquery
from app.blueprints.locations.utils import GeoLevelHierarchy
from app.blueprints.locations.errors import InvalidGeoLevelHierarchyError
from .errors import (
    HeaderRowEmptyError,
    InvalidEnumeratorRecordsError,
    InvalidFileStructureError,
    InvalidColumnMappingError,
)
import binascii


@enumerators_bp.route("", methods=["POST"])
@logged_in_active_user_required
def upload_enumerators():
    """
    Method to validate the uploaded enumerators file and save it to the database
    """

    # Validate the query parameter
    query_param_validator = EnumeratorsQueryParamValidator.from_json(request.args)
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
                message=f"The form 'form_uid={form_uid}' could not be found. Cannot upload enumerators for an undefined form."
            ),
            404,
        )

    survey_uid = form.survey_uid

    payload = request.get_json()
    payload_validator = EnumeratorsFileUploadValidator.from_json(payload)

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

    # Get the prime geo level from the survey configuration
    prime_geo_level_uid = (
        Survey.query.filter_by(survey_uid=survey_uid).first().prime_geo_level_uid
    )

    try:
        column_mapping = EnumeratorColumnMapping(
            payload_validator.column_mapping.data, prime_geo_level_uid
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
        column_mapping.enumerator_id,
        column_mapping.name,
        column_mapping.email,
        column_mapping.mobile_primary,
        column_mapping.language,
        column_mapping.home_address,
        column_mapping.gender,
        column_mapping.enumerator_type,
    ]

    if hasattr(column_mapping, "location_id_column"):
        expected_columns.append(column_mapping.location_id_column)

    if hasattr(column_mapping, "custom_fields"):
        for custom_field in column_mapping.custom_fields:
            expected_columns.append(custom_field["column_name"])

    # Create an EnumeratorsUpload object from the uploaded file
    try:
        enumerators_upload = EnumeratorsUpload(
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

    # Validate the enumerators data
    try:
        enumerators_upload.validate_records(
            expected_columns,
            column_mapping,
            form,
            prime_geo_level_uid,
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
    except InvalidEnumeratorRecordsError as e:
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
        SurveyorForm.query.filter_by(form_uid=form_uid).delete()
        SurveyorLocation.query.filter_by(form_uid=form_uid).delete()
        MonitorForm.query.filter_by(form_uid=form_uid).delete()
        MonitorLocation.query.filter_by(form_uid=form_uid).delete()
        Enumerator.query.filter_by(form_uid=form_uid).delete()

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
                enumerators_upload.enumerators_df[column_mapping.location_id_column]
                .drop_duplicates()
                .tolist()
            ),
            Location.survey_uid == survey_uid,
        ).with_entities(Location.location_uid, Location.location_id)

        # Create a dictionary of location ID to location UID
        location_uid_lookup = {
            location.location_id: location.location_uid for location in locations.all()
        }

    # Order the columns in the dataframe so we can easily access them by index
    enumerators_upload.enumerators_df = enumerators_upload.enumerators_df[
        expected_columns
    ]

    # Insert the enumerators into the database
    for i, row in enumerate(
        enumerators_upload.enumerators_df.drop_duplicates().itertuples()
    ):
        enumerator = Enumerator(
            form_uid=form_uid,
            enumerator_id=row[1],
            name=row[2],
            email=row[3],
            mobile_primary=row[4],
            language=row[5],
            home_address=row[6],
            gender=row[7],
        )

        # Add the custom fields if they exist
        if hasattr(column_mapping, "custom_fields"):
            custom_fields = {}
            for custom_field in column_mapping.custom_fields:
                col_index = (
                    enumerators_upload.enumerators_df.columns.get_loc(
                        custom_field["column_name"]
                    )
                    + 1
                )  # Add 1 to the index to account for the df index
                custom_fields[custom_field["field_label"]] = row[col_index]
            enumerator.custom_fields = custom_fields

        db.session.add(enumerator)
        db.session.flush()

        enumerator_types = [item.lower().strip() for item in row[8].split(";")]

        for enumerator_type in enumerator_types:
            if enumerator_type == "surveyor":
                surveyor_form = SurveyorForm(
                    enumerator_uid=enumerator.enumerator_uid,
                    form_uid=form_uid,
                    user_uid=current_user.user_uid,
                )

                db.session.add(surveyor_form)

                if hasattr(column_mapping, "location_id_column"):
                    # Get the position of the location column in the dataframe
                    col_index = (
                        enumerators_upload.enumerators_df.columns.get_loc(
                            getattr(column_mapping, "location_id_column")
                        )
                        + 1
                    )  # Add 1 to the index to account for the df index
                    surveyor_location = SurveyorLocation(
                        enumerator_uid=enumerator.enumerator_uid,
                        form_uid=form_uid,
                        location_uid=location_uid_lookup[row[col_index]],
                    )

                    db.session.add(surveyor_location)

            if enumerator_type == "monitor":
                monitor_form = MonitorForm(
                    enumerator_uid=enumerator.enumerator_uid,
                    form_uid=form_uid,
                    user_uid=current_user.user_uid,
                )

                db.session.add(monitor_form)

                if hasattr(column_mapping, "location_id_column"):
                    # Get the position of the location column in the dataframe
                    col_index = (
                        enumerators_upload.enumerators_df.columns.get_loc(
                            getattr(column_mapping, "location_id_column")
                        )
                        + 1
                    )
                    monitor_location = MonitorLocation(
                        enumerator_uid=enumerator.enumerator_uid,
                        form_uid=form_uid,
                        location_uid=location_uid_lookup[row[col_index]],
                    )

                    db.session.add(monitor_location)

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify(message="Success"), 200


@enumerators_bp.route("", methods=["GET"])
@logged_in_active_user_required
def get_enumerators():
    """
    Method to retrieve the enumerators information from the database
    """

    # Validate the query parameter
    query_param_validator = GetEnumeratorsQueryParamValidator.from_json(request.args)
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
    enumerator_type = request.args.get("enumerator_type")
    user_uid = current_user.user_uid

    # Check if the logged in user has permission to access the given form

    # This will be used to join in the locations hierarchy for each enumerator

    ## TODO handle cases where these are None
    survey_uid = ParentForm.query.filter_by(form_uid=form_uid).first().survey_uid
    prime_geo_level_uid = (
        Survey.query.filter_by(survey_uid=survey_uid).first().prime_geo_level_uid
    )

    surveyor_locations_subquery = aliased(
        build_prime_locations_with_location_hierarchy_subquery(
            survey_uid, prime_geo_level_uid
        )
    )
    monitor_locations_subquery = aliased(
        build_prime_locations_with_location_hierarchy_subquery(
            survey_uid, prime_geo_level_uid
        )
    )

    models = [Enumerator]
    joined_keys = []

    if enumerator_type is None or enumerator_type == "surveyor":
        models.append(SurveyorForm.status.label("surveyor_status"))
        models.append(
            surveyor_locations_subquery.c.locations.label("surveyor_locations")
        )
        joined_keys.append("surveyor_status")
        joined_keys.append("surveyor_locations")

    if enumerator_type is None or enumerator_type == "monitor":
        models.append(MonitorForm.status.label("monitor_status"))
        models.append(monitor_locations_subquery.c.locations.label("monitor_locations"))
        joined_keys.append("monitor_status")
        joined_keys.append("monitor_locations")

    query_to_build = db.session.query(*models)

    if enumerator_type is None or enumerator_type == "surveyor":
        query_to_build = (
            query_to_build.outerjoin(
                SurveyorForm,
                (Enumerator.enumerator_uid == SurveyorForm.enumerator_uid)
                & (Enumerator.form_uid == SurveyorForm.form_uid),
            )
            .outerjoin(
                SurveyorLocation,
                (Enumerator.enumerator_uid == SurveyorLocation.enumerator_uid)
                & (Enumerator.form_uid == SurveyorLocation.form_uid),
            )
            .outerjoin(
                surveyor_locations_subquery,
                SurveyorLocation.location_uid
                == surveyor_locations_subquery.c.location_uid,
            )
        )

    if enumerator_type is None or enumerator_type == "monitor":
        query_to_build = (
            query_to_build.outerjoin(
                MonitorForm,
                (Enumerator.enumerator_uid == MonitorForm.enumerator_uid)
                & (Enumerator.form_uid == MonitorForm.form_uid),
            )
            .outerjoin(
                MonitorLocation,
                (Enumerator.enumerator_uid == MonitorLocation.enumerator_uid)
                & (Enumerator.form_uid == MonitorLocation.form_uid),
            )
            .outerjoin(
                monitor_locations_subquery,
                MonitorLocation.location_uid
                == monitor_locations_subquery.c.location_uid,
            )
        )

    final_query = query_to_build.filter(Enumerator.form_uid == form_uid)

    result = final_query.all()

    if enumerator_type is None:
        for (
            enumerator,
            surveyor_status,
            surveyor_locations,
            monitor_status,
            monitor_locations,
        ) in result:
            enumerator.surveyor_status = surveyor_status
            enumerator.surveyor_locations = surveyor_locations
            enumerator.monitor_status = monitor_status
            enumerator.monitor_locations = monitor_locations

        response = jsonify(
            {
                "success": True,
                "data": [
                    enumerator.to_dict(joined_keys=joined_keys)
                    for enumerator, surveyor_status, surveyor_locations, monitor_status, monitor_locations in result
                ],
            }
        )

        return response, 200

    elif enumerator_type == "surveyor":
        for (
            enumerator,
            surveyor_status,
            surveyor_locations,
        ) in result:
            enumerator.surveyor_status = surveyor_status
            enumerator.surveyor_locations = surveyor_locations

        response = jsonify(
            {
                "success": True,
                "data": [
                    enumerator.to_dict(joined_keys=joined_keys)
                    for enumerator, surveyor_status, surveyor_locations in result
                ],
            }
        )

        return response, 200

    elif enumerator_type == "monitor":
        for (
            enumerator,
            monitor_status,
            monitor_locations,
        ) in result:
            enumerator.monitor_status = monitor_status
            enumerator.monitor_locations = monitor_locations

        response = jsonify(
            {
                "success": True,
                "data": [
                    enumerator.to_dict(joined_keys=joined_keys)
                    for enumerator, monitor_status, monitor_locations in result
                ],
            }
        )

        return response, 200


@enumerators_bp.route("/<int:enumerator_uid>", methods=["GET"])
@logged_in_active_user_required
def get_enumerator(enumerator_uid):
    """
    Method to retrieve an enumerator from the database
    """

    # Check if the logged in user has permission to fetch the enumerator

    enumerator = Enumerator.query.filter_by(enumerator_uid=enumerator_uid).first()

    if enumerator is None:
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "message": "Enumerator not found",
                }
            ),
            404,
        )

    response = jsonify({"success": True, "data": enumerator.to_dict()})

    return response, 200


@enumerators_bp.route("/<int:enumerator_uid>", methods=["PUT"])
@logged_in_active_user_required
def update_enumerator(enumerator_uid):
    """
    Method to update an enumerator in the database
    """

    payload = request.get_json()
    payload_validator = UpdateEnumerator.from_json(payload)

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if payload_validator.validate():
        enumerator = Enumerator.query.filter_by(enumerator_uid=enumerator_uid).first()
        if enumerator is None:
            return jsonify({"error": "Enumerator not found"}), 404

        # The payload needs to pass in the same custom field keys as are in the database
        # This is because this method is used to update values but not add/remove/modify columns
        custom_fields_in_db = getattr(enumerator, "custom_fields", None)
        custom_fields_in_payload = payload.get("custom_fields")

        keys_in_db = []
        keys_in_payload = []

        if custom_fields_in_db is not None:
            keys_in_db = custom_fields_in_db.keys()

        if custom_fields_in_payload is not None:
            keys_in_payload = custom_fields_in_payload.keys()

        for payload_key in keys_in_payload:
            if payload_key not in keys_in_db:
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
            if db_key not in keys_in_payload:
                return (
                    jsonify(
                        {
                            "success": False,
                            "errors": f"The payload is missing a custom key with field label {db_key} that exists in the database. This method can only be used to update values for existing fields, not to add/remove/modify fields",
                        }
                    ),
                    422,
                )

        try:
            Enumerator.query.filter_by(enumerator_uid=enumerator_uid).update(
                {
                    Enumerator.enumerator_id: payload_validator.enumerator_id.data,
                    Enumerator.name: payload_validator.name.data,
                    Enumerator.email: payload_validator.email.data,
                    Enumerator.mobile_primary: payload_validator.mobile_primary.data,
                    Enumerator.language: payload_validator.language.data,
                    Enumerator.home_address: payload_validator.home_address.data,
                    Enumerator.gender: payload_validator.gender.data,
                    Enumerator.custom_fields: payload["custom_fields"],
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


@enumerators_bp.route("/<int:enumerator_uid>", methods=["DELETE"])
@logged_in_active_user_required
def delete_enumerator(enumerator_uid):
    """
    Method to delete an enumerator from the database
    """

    if Enumerator.query.filter_by(enumerator_uid=enumerator_uid).first() is None:
        return jsonify({"error": "Enumerator not found"}), 404

    SurveyorForm.query.filter_by(enumerator_uid=enumerator_uid).delete()
    SurveyorLocation.query.filter_by(enumerator_uid=enumerator_uid).delete()
    MonitorForm.query.filter_by(enumerator_uid=enumerator_uid).delete()
    MonitorLocation.query.filter_by(enumerator_uid=enumerator_uid).delete()
    Enumerator.query.filter_by(enumerator_uid=enumerator_uid).delete()

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify({"success": True}), 200


# @enumerators_bp.route("/<int:enumerator_uid>/roles", methods=["POST"])
# def create_enumerator_role(enumerator_uid):
#     """
#     Method to create an enumerator role in the database
#     """

#     payload_validator = CreateEnumeratorRole.from_json(request.get_json())

#     # Add the CSRF token to be checked by the validator
#     if "X-CSRF-Token" in request.headers:
#         payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
#     else:
#         return jsonify(message="X-CSRF-Token required in header"), 403

#     if not payload_validator.validate():
#         return jsonify({"success": False, "errors": payload_validator.errors}), 422

#     if Enumerator.query.filter_by(enumerator_uid=enumerator_uid).first() is None:
#         return jsonify({"error": "Enumerator not found"}), 404

#     form = ParentForm.query.filter_by(form_uid=payload_validator.form_uid.data).first()
#     if form is None:
#         return jsonify({"error": "Form not found"}), 404

#     if payload_validator.enumerator_type.data == "surveyor":
#         # Check if the surveyor form already exists
#         if (
#             SurveyorForm.query.filter_by(
#                 enumerator_uid=enumerator_uid,
#                 form_uid=payload_validator.form_uid.data,
#             ).first()
#             is not None
#         ):
#             return (
#                 jsonify(
#                     {
#                         "error": "The enumerator is already assigned as a surveyor for the given form"
#                     }
#                 ),
#                 409,
#             )

#         surveyor_form = SurveyorForm(
#             enumerator_uid=enumerator_uid,
#             form_uid=payload_validator.form_uid.data,
#         )

#         db.session.add(surveyor_form)

#         if payload_validator.location_uid.data is not None:
#             # Check if the surveyor location mapping already exists
#             if (
#                 SurveyorLocation.query.filter_by(
#                     enumerator_uid=enumerator_uid,
#                     form_uid=payload_validator.form_uid.data,
#                 ).first()
#                 is not None
#             ):
#                 return (
#                     jsonify(
#                         {
#                             "error": "Surveyor location mapping for the form already exists for the given enumerator"
#                         }
#                     ),
#                     409,
#                 )

#             # Check if the prime geo level is configured for the survey
#             prime_geo_level_uid = (
#                 Survey.query.filter_by(survey_uid=form.survey_uid)
#                 .first()
#                 .prime_geo_level_uid
#             )
#             if prime_geo_level_uid is None:
#                 return (
#                     jsonify(
#                         {
#                             "error": "Prime geo level not configured for the survey. Cannot map surveyor to location"
#                         }
#                     ),
#                     400,
#                 )

#             # Check if the location exists for the form's survey
#             location = Location.query.filter_by(
#                 location_uid=payload_validator.location_uid.data,
#                 survey_uid=form.survey_uid,
#             ).first()
#             if location is None:
#                 return (
#                     jsonify({"error": "Location does not exist for the survey"}),
#                     404,
#                 )

#             # Check if the location is of the correct geo level
#             if location.geo_level_uid != prime_geo_level_uid:
#                 return (
#                     jsonify(
#                         {
#                             "error": "Location geo level does not match the prime geo level configured for the survey"
#                         }
#                     ),
#                     400,
#                 )

#             # Add the surveyor location mapping
#             surveyor_location = SurveyorLocation(
#                 enumerator_uid=enumerator_uid,
#                 form_uid=payload_validator.form_uid.data,
#                 location_uid=payload_validator.location_uid.data,
#             )

#             db.session.add(surveyor_location)

#     if payload_validator.enumerator_type.data == "monitor":
#         # Check if the monitor form already exists
#         if (
#             MonitorForm.query.filter_by(
#                 enumerator_uid=enumerator_uid,
#                 form_uid=payload_validator.form_uid.data,
#             ).first()
#             is not None
#         ):
#             return (
#                 jsonify(
#                     {
#                         "error": "The enumerator is already assigned as a monitor for the given form"
#                     }
#                 ),
#                 409,
#             )

#         monitor_form = MonitorForm(
#             enumerator_uid=enumerator_uid,
#             form_uid=payload_validator.form_uid.data,
#         )

#         db.session.add(monitor_form)

#         if payload_validator.location_uid.data is not None:
#             # Check if the monitor location mapping already exists
#             if (
#                 MonitorLocation.query.filter_by(
#                     enumerator_uid=enumerator_uid,
#                     form_uid=payload_validator.form_uid.data,
#                 ).first()
#                 is not None
#             ):
#                 return (
#                     jsonify(
#                         {
#                             "error": "Monitor location mapping for the form already exists for the given enumerator"
#                         }
#                     ),
#                     409,
#                 )

#             # Check if the prime geo level is configured for the survey
#             prime_geo_level_uid = (
#                 Survey.query.filter_by(survey_uid=form.survey_uid)
#                 .first()
#                 .prime_geo_level_uid
#             )
#             if prime_geo_level_uid is None:
#                 return (
#                     jsonify(
#                         {
#                             "error": "Prime geo level not configured for the survey. Cannot map monitor to location"
#                         }
#                     ),
#                     400,
#                 )

#             # Check if the location exists for the form's survey
#             location = Location.query.filter_by(
#                 location_uid=payload_validator.location_uid.data,
#                 survey_uid=form.survey_uid,
#             ).first()
#             if location is None:
#                 return (
#                     jsonify({"error": "Location does not exist for the survey"}),
#                     404,
#                 )

#             # Check if the location is of the correct geo level
#             if location.geo_level_uid != prime_geo_level_uid:
#                 return (
#                     jsonify(
#                         {
#                             "error": "Location geo level does not match the prime geo level configured for the survey"
#                         }
#                     ),
#                     400,
#                 )

#             # Add the monitor location mapping
#             monitor_location = MonitorLocation(
#                 enumerator_uid=enumerator_uid,
#                 form_uid=payload_validator.form_uid.data,
#                 location_uid=payload_validator.location_uid.data,
#             )

#             db.session.add(monitor_location)

#     try:
#         db.session.commit()
#     except IntegrityError as e:
#         db.session.rollback()
#         return jsonify(message=str(e)), 500

#     return jsonify({"success": True}), 200


@enumerators_bp.route("/<int:enumerator_uid>/roles/locations", methods=["PUT"])
@logged_in_active_user_required
def update_enumerator_role(enumerator_uid):
    """
    Method to update an existing enumerator's role-location in the database
    Only the location mapping can be updated
    """

    payload_validator = UpdateEnumeratorRole.from_json(request.get_json())

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if not payload_validator.validate():
        return jsonify({"success": False, "errors": payload_validator.errors}), 422

    if Enumerator.query.filter_by(enumerator_uid=enumerator_uid).first() is None:
        return jsonify({"error": "Enumerator not found"}), 404

    form = ParentForm.query.filter_by(form_uid=payload_validator.form_uid.data).first()
    if form is None:
        return jsonify({"error": "Form not found"}), 404

    model_lookup = {
        "surveyor": {"form_model": SurveyorForm, "location_model": SurveyorLocation},
        "monitor": {"form_model": MonitorForm, "location_model": MonitorLocation},
    }

    # Check if the form-role already exists
    if (
        db.session.query(
            model_lookup[payload_validator.enumerator_type.data]["form_model"]
        )
        .filter_by(
            enumerator_uid=enumerator_uid,
            form_uid=payload_validator.form_uid.data,
        )
        .first()
        is None
    ):
        return (
            jsonify(
                {
                    "error": f"The enumerator is not assigned as a {payload_validator.enumerator_type.data} for the given form. Use the create endpoint to assign the enumerator as a {payload_validator.enumerator_type.data}.",
                    "success": False,
                }
            ),
            409,
        )

    if payload_validator.location_uid.data is not None:
        # Check if the prime geo level is configured for the survey
        prime_geo_level_uid = (
            Survey.query.filter_by(survey_uid=form.survey_uid)
            .first()
            .prime_geo_level_uid
        )
        if prime_geo_level_uid is None:
            return (
                jsonify(
                    {
                        "error": f"Prime geo level not configured for the survey. Cannot map {payload_validator.enumerator_type.data} to location"
                    }
                ),
                400,
            )

        # Check if the location exists for the form's survey
        location = Location.query.filter_by(
            location_uid=payload_validator.location_uid.data,
            survey_uid=form.survey_uid,
        ).first()
        if location is None:
            return (
                jsonify({"error": "Location does not exist for the survey"}),
                404,
            )

        # Check if the location is of the correct geo level
        if location.geo_level_uid != prime_geo_level_uid:
            return (
                jsonify(
                    {
                        "error": "Location geo level does not match the prime geo level configured for the survey"
                    }
                ),
                400,
            )

        # Do an upsert of the surveyor location mapping
        statement = (
            pg_insert(
                model_lookup[payload_validator.enumerator_type.data]["location_model"]
            )
            .values(
                enumerator_uid=enumerator_uid,
                form_uid=payload_validator.form_uid.data,
                location_uid=payload_validator.location_uid.data,
            )
            .on_conflict_do_update(
                constraint=f"{payload_validator.enumerator_type.data}_location_pkey",
                set_={
                    "location_uid": payload_validator.location_uid.data,
                },
            )
        )

        db.session.execute(statement)

    else:
        db.session.query(
            model_lookup[payload_validator.enumerator_type.data]["location_model"]
        ).filter_by(
            enumerator_uid=enumerator_uid,
            form_uid=payload_validator.form_uid.data,
        ).delete()

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"success": True}), 200


# @enumerators_bp.route("/<int:enumerator_uid>/roles", methods=["DELETE"])
# def delete_enumerator_role(enumerator_uid):
#     """
#     Method to delete an enumerator role from the database
#     """

#     payload_validator = DeleteEnumeratorRole.from_json(request.get_json())

#     # Add the CSRF token to be checked by the validator
#     if "X-CSRF-Token" in request.headers:
#         payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
#     else:
#         return jsonify(message="X-CSRF-Token required in header"), 403

#     if not payload_validator.validate():
#         return jsonify({"success": False, "errors": payload_validator.errors}), 422

#     if Enumerator.query.filter_by(enumerator_uid=enumerator_uid).first() is None:
#         return jsonify({"error": "Enumerator not found"}), 404

#     if (
#         ParentForm.query.filter_by(form_uid=payload_validator.form_uid.data).first()
#         is None
#     ):
#         return jsonify({"error": "Form not found"}), 404

#     if payload_validator.enumerator_type.data == "surveyor":
#         if (
#             SurveyorForm.query.filter_by(
#                 enumerator_uid=enumerator_uid,
#                 form_uid=payload_validator.form_uid.data,
#             ).first()
#             is None
#         ):
#             return (
#                 jsonify(
#                     {
#                         "error": "The enumerator is not assigned as a surveyor for the given form. Nothing to delete.",
#                         "success": False,
#                     }
#                 ),
#                 404,
#             )

#         SurveyorForm.query.filter_by(enumerator_uid=enumerator_uid).delete()
#         SurveyorLocation.query.filter_by(enumerator_uid=enumerator_uid).delete()

#     elif payload_validator.enumerator_type.data == "monitor":
#         if (
#             MonitorForm.query.filter_by(
#                 enumerator_uid=enumerator_uid,
#                 form_uid=payload_validator.form_uid.data,
#             ).first()
#             is None
#         ):
#             return (
#                 jsonify(
#                     {
#                         "error": "The enumerator is not assigned as a monitor for the given form. Nothing to delete.",
#                         "success": False,
#                     }
#                 ),
#                 404,
#             )

#         MonitorForm.query.filter_by(enumerator_uid=enumerator_uid).delete()
#         MonitorLocation.query.filter_by(enumerator_uid=enumerator_uid).delete()

#     try:
#         db.session.commit()
#     except IntegrityError as e:
#         db.session.rollback()
#         return jsonify(message=str(e)), 500

#     return jsonify({"success": True}), 200


# Patch method to update an enumerator's status
@enumerators_bp.route("/<int:enumerator_uid>/roles/status", methods=["PATCH"])
@logged_in_active_user_required
def update_enumerator_status(enumerator_uid):
    """
    Method to update an enumerator's status
    """

    payload_validator = UpdateEnumeratorRoleStatus.from_json(request.get_json())

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if not payload_validator.validate():
        return jsonify({"success": False, "errors": payload_validator.errors}), 422

    if Enumerator.query.filter_by(enumerator_uid=enumerator_uid).first() is None:
        return jsonify({"error": "Enumerator not found"}), 404

    if (
        ParentForm.query.filter_by(form_uid=payload_validator.form_uid.data).first()
        is None
    ):
        return jsonify({"error": "Form not found"}), 404

    model_lookup = {
        "surveyor": SurveyorForm,
        "monitor": MonitorForm,
    }

    result = (
        db.session.query(model_lookup[payload_validator.enumerator_type.data])
        .filter_by(
            enumerator_uid=enumerator_uid, form_uid=payload_validator.form_uid.data
        )
        .first()
    )

    if result is None:
        return (
            jsonify(
                {
                    "error": f"The enumerator is not assigned as a {payload_validator.enumerator_type.data} for the given form. Nothing to update.",
                    "success": False,
                }
            ),
            404,
        )

    result.status = payload_validator.status.data

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"success": True}), 200


@enumerators_bp.route("/<int:enumerator_uid>/roles", methods=["GET"])
@logged_in_active_user_required
def get_enumerator_roles(enumerator_uid):
    """
    Method to get an enumerator's roles from the database
    """

    payload_validator = GetEnumeratorRolesQueryParamValidator.from_json(request.args)

    if not payload_validator.validate():
        return jsonify({"success": False, "errors": payload_validator.errors}), 422

    if Enumerator.query.filter_by(enumerator_uid=enumerator_uid).first() is None:
        return jsonify({"error": "Enumerator not found"}), 404

    roles = []

    if (
        payload_validator.enumerator_type.data == "surveyor"
        or payload_validator.enumerator_type.data is None
    ):
        surveyor_result = (
            db.session.query(SurveyorForm, SurveyorLocation)
            .join(
                SurveyorLocation,
                (SurveyorForm.enumerator_uid == SurveyorLocation.enumerator_uid)
                & (SurveyorForm.form_uid == SurveyorLocation.form_uid),
                isouter=True,
            )
            .filter(
                SurveyorForm.enumerator_uid == enumerator_uid,
                SurveyorForm.form_uid == payload_validator.form_uid.data,
            )
            .all()
        )

        surveyor_nested_result = {}
        for surveyor_form, surveyor_location in surveyor_result:
            if len(surveyor_nested_result.keys()) == 0:
                surveyor_nested_result["enumerator_type"] = "surveyor"
                surveyor_nested_result["status"] = surveyor_form.status
                surveyor_nested_result["locations"] = None
                if surveyor_location is not None:
                    surveyor_nested_result["locations"] = [
                        {"location_uid": surveyor_location.location_uid}
                    ]
            else:
                if surveyor_location.location_uid is not None:
                    # The surveyor has multiple locations - this is the only way we can have multiple rows for a given form-role for an enumerator
                    surveyor_nested_result["locations"].append(
                        {"location_uid": surveyor_location.location_uid}
                    )
        if len(surveyor_nested_result) > 0:
            roles.append(surveyor_nested_result)

    if (
        payload_validator.enumerator_type.data == "monitor"
        or payload_validator.enumerator_type.data is None
    ):
        monitor_result = (
            db.session.query(MonitorForm, MonitorLocation)
            .join(
                MonitorLocation,
                (MonitorForm.enumerator_uid == MonitorLocation.enumerator_uid)
                & (MonitorForm.form_uid == MonitorLocation.form_uid),
                isouter=True,
            )
            .filter(
                MonitorForm.enumerator_uid == enumerator_uid,
                MonitorForm.form_uid == payload_validator.form_uid.data,
            )
            .all()
        )

        monitor_nested_result = {}
        for monitor_form, monitor_location in monitor_result:
            if len(monitor_nested_result.keys()) == 0:
                monitor_nested_result["enumerator_type"] = "monitor"
                monitor_nested_result["status"] = monitor_form.status
                monitor_nested_result["locations"] = None
                if monitor_location is not None:
                    monitor_nested_result["locations"] = [
                        {"location_uid": monitor_location.location_uid}
                    ]
            else:
                if monitor_location.location_uid is not None:
                    # The monitor has multiple locations - this is the only way we can have multiple rows for a given form-role for an enumerator
                    monitor_nested_result["locations"].append(
                        {"location_uid": monitor_location.location_uid}
                    )
        if len(monitor_nested_result) > 0:
            roles.append(monitor_nested_result)

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "form_uid": payload_validator.form_uid.data,
                    "roles": roles,
                },
            }
        ),
        200,
    )


# Patch method to bulk update enumerator details
@enumerators_bp.route("", methods=["PATCH"])
@logged_in_active_user_required
def bulk_update_enumerators_custom_fields():
    """
    Method to bulk update enumerators
    """

    payload = request.get_json()
    payload_validator = BulkUpdateEnumeratorsValidator.from_json(payload)

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if not payload_validator.validate():
        return jsonify({"success": False, "errors": payload_validator.errors}), 422

    column_config = EnumeratorColumnConfig.query.filter(
        EnumeratorColumnConfig.form_uid == payload_validator.form_uid.data,
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
        if key not in ("enumerator_uids", "form_uid", "csrf_token"):
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

    bulk_editable_fields = {
        "personal_details": [],
        "custom_fields": [],
    }

    for column in column_config:
        if column.column_type != "location" and column.bulk_editable is True:
            bulk_editable_fields[column.column_type].append(column.column_name)

    for key in payload.keys():
        if key not in ("enumerator_uids", "form_uid", "csrf_token"):
            if key == "location_uid":
                return (
                    jsonify(
                        {
                            "success": False,
                            "errors": "Location UID can only be bulk updated via the 'PUT /enumerators/roles/locations' method",
                        }
                    ),
                    422,
                )
            elif (
                key
                not in bulk_editable_fields["personal_details"]
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

    personal_details_patch_keys = [
        key
        for key in payload.keys()
        if key not in ("enumerator_uids", "form_uid", "csrf_token")
        and key in bulk_editable_fields["personal_details"]
    ]

    custom_fields_patch_keys = [
        key
        for key in payload.keys()
        if key not in ("enumerator_uids", "form_uid", "csrf_token")
        and key in bulk_editable_fields["custom_fields"]
    ]

    if len(personal_details_patch_keys) > 0:
        Enumerator.query.filter(
            Enumerator.enumerator_uid.in_(payload_validator.enumerator_uids.data)
        ).update(
            {key: payload[key] for key in personal_details_patch_keys},
            synchronize_session=False,
        )

    if len(custom_fields_patch_keys) > 0:
        for custom_field in custom_fields_patch_keys:
            db.session.execute(
                update(Enumerator)
                .values(
                    custom_fields=func.jsonb_set(
                        Enumerator.custom_fields,
                        "{%s}" % custom_field,
                        cast(
                            payload[custom_field],
                            JSONB,
                        ),
                    )
                )
                .where(
                    Enumerator.enumerator_uid.in_(
                        payload_validator.enumerator_uids.data
                    )
                )
            )

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"success": True}), 200


@enumerators_bp.route("/roles/locations", methods=["PUT"])
@logged_in_active_user_required
def bulk_update_enumerators_role_locations():
    """
    Method to bulk update enumerators' locations for a given role
    """

    payload_validator = BulkUpdateEnumeratorsRoleLocationValidator.from_json(
        request.get_json()
    )

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if not payload_validator.validate():
        return jsonify({"success": False, "errors": payload_validator.errors}), 422

    column_config = EnumeratorColumnConfig.query.filter(
        EnumeratorColumnConfig.form_uid == payload_validator.form_uid.data,
        EnumeratorColumnConfig.column_name == "prime_geo_level_location",
        EnumeratorColumnConfig.column_type == "location",
    ).first()

    if column_config is None:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": "No location column found in the column configuration for form",
                }
            ),
            404,
        )

    if column_config.bulk_editable is False:
        return (
            jsonify(
                {"success": False, "errors": "Location column is not bulk editable"}
            ),
            400,
        )

    # Check if the location UIDs are valid
    if (
        payload_validator.data["location_uids"] is not None
        and len(payload_validator.data["location_uids"]) > 0
    ):
        returned_location_uids = [
            location.location_uid
            for location in Location.query.filter(
                Location.location_uid.in_(payload_validator.data["location_uids"])
            ).all()
        ]

        for location_uid in payload_validator.data["location_uids"]:
            if location_uid not in returned_location_uids:
                return (
                    jsonify(
                        {
                            "success": False,
                            "errors": f"Location UID {location_uid} not found in the database",
                        }
                    ),
                    404,
                )

    returned_location_uids = [
        location.location_uid
        for location in Location.query.filter(
            Location.location_uid.in_(payload_validator.data["location_uids"])
        ).all()
    ]

    for location_uid in payload_validator.data["location_uids"]:
        if location_uid not in returned_location_uids:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": f"Location UID {location_uid} not found in the database",
                    }
                ),
                404,
            )
    model_lookup = {
        "surveyor": SurveyorLocation,
        "monitor": MonitorLocation,
    }

    model = model_lookup[payload_validator.enumerator_type.data]

    db.session.query(model).filter(
        model.enumerator_uid.in_(payload_validator.data["enumerator_uids"]),
        model.form_uid == payload_validator.form_uid.data,
    ).delete()

    if payload_validator.data["location_uids"] is not None:
        for enumerator_uid in payload_validator.data["enumerator_uids"]:
            for location_uid in payload_validator.data["location_uids"]:
                db.session.add(
                    model(
                        enumerator_uid=enumerator_uid,
                        form_uid=payload_validator.form_uid.data,
                        location_uid=location_uid,
                    )
                )

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"success": True}), 200


@enumerators_bp.route("/column-config", methods=["PUT"])
@logged_in_active_user_required
def update_enumerator_column_config():
    """
    Method to update enumerators' column configuration
    """

    payload = request.get_json()
    payload_validator = UpdateEnumeratorsColumnConfig.from_json(payload)

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

    EnumeratorColumnConfig.query.filter(
        EnumeratorColumnConfig.form_uid == payload_validator.form_uid.data,
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

        db.session.add(
            EnumeratorColumnConfig(
                form_uid=payload_validator.form_uid.data,
                column_name=column["column_name"],
                column_type=column["column_type"],
                bulk_editable=column["bulk_editable"],
            )
        )

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"success": True}), 200


@enumerators_bp.route("/column-config", methods=["GET"])
@logged_in_active_user_required
def get_enumerator_column_config():
    """
    Method to get enumerators' column configuration
    """

    payload_validator = EnumeratorColumnConfigQueryParamValidator(request.args)

    if not payload_validator.validate():
        return jsonify({"success": False, "errors": payload_validator.errors}), 422

    column_config = EnumeratorColumnConfig.query.filter(
        EnumeratorColumnConfig.form_uid == payload_validator.form_uid.data,
    ).all()

    return jsonify(
        {
            "success": True,
            "data": [
                {
                    "column_name": column.column_name,
                    "column_type": column.column_type,
                    "bulk_editable": column.bulk_editable,
                }
                for column in column_config
            ],
        }
    )
