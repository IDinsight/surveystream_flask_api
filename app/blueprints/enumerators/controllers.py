from flask import jsonify, request
from app.utils.utils import logged_in_active_user_required
from flask_login import current_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
    InvalidEnumeratorsError,
    InvalidColumnMappingError,
)
import binascii


@enumerators_bp.route("", methods=["POST"])
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

    # Get the geo levels for the survey
    geo_levels = GeoLevel.query.filter_by(survey_uid=survey_uid).all()

    try:
        GeoLevelHierarchy(geo_levels)
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

    # Get the prime geo level from the survey configuration
    prime_geo_level_uid = (
        Survey.query.filter_by(survey_uid=survey_uid).first().prime_geo_level_uid
    )

    try:
        column_mapping = EnumeratorColumnMapping(
            payload_validator.column_mapping.data, prime_geo_level_uid, geo_levels
        )
    except InvalidColumnMappingError as e:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "column_mapping": e.column_mapping_errors,
                        "file": [],
                    },
                }
            ),
            422,
        )

    # Get the expected columns from the mapped column names
    expected_columns = [
        column_mapping.enumerator_id,
        column_mapping.first_name,
        column_mapping.middle_name,
        column_mapping.last_name,
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
                        "file": ["File data has invalid base64 encoding"],
                        "column_mapping": [],
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
                        "column_mapping": [],
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
                        "column_mapping": [],
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
    except InvalidEnumeratorsError as e:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "file": e.enumerators_errors,
                        "column_mapping": [],
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

    # Insert the enumerators into the database
    for i, row in enumerate(
        enumerators_upload.enumerators_df[expected_columns]
        .drop_duplicates()
        .itertuples()
    ):
        enumerator = Enumerator(
            form_uid=form_uid,
            enumerator_id=row[1],
            first_name=row[2],
            middle_name=row[3],
            last_name=row[4],
            email=row[5],
            mobile_primary=row[6],
            language=row[7],
            home_address=row[8],
            gender=row[9],
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

        enumerator_types = [item.lower().strip() for item in row[10].split(";")]

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
                    col_index = enumerators_upload.enumerators_df.columns.get_loc(
                        getattr(column_mapping, "location_id_column")
                    )
                    monitor_location = MonitorLocation(
                        enumerator_uid=enumerator.enumerator_uid,
                        form_uid=form_uid,
                        location_uid=location_uid_lookup.get(row[col_index]),
                    )

                    db.session.add(monitor_location)

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify(message="Success"), 200


@enumerators_bp.route("", methods=["GET"])
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

    # Get the enumerators for the given form
    if enumerator_type is None:
        result = (
            db.session.query(
                Enumerator,
                SurveyorForm.status.label("surveyor_status"),
                MonitorForm.status.label("monitor_status"),
                surveyor_locations_subquery.c.locations.label("surveyor_locations"),
                monitor_locations_subquery.c.locations.label("monitor_locations"),
            )
            .join(
                SurveyorForm,
                (Enumerator.enumerator_uid == SurveyorForm.enumerator_uid)
                & (Enumerator.form_uid == SurveyorForm.form_uid),
                isouter=True,
            )
            .join(
                SurveyorLocation,
                (Enumerator.enumerator_uid == SurveyorLocation.enumerator_uid)
                & (Enumerator.form_uid == SurveyorLocation.form_uid),
                isouter=True,
            )
            .join(
                MonitorForm,
                (Enumerator.enumerator_uid == MonitorForm.enumerator_uid)
                & (Enumerator.form_uid == MonitorForm.form_uid),
                isouter=True,
            )
            .join(
                MonitorLocation,
                (Enumerator.enumerator_uid == MonitorLocation.enumerator_uid)
                & (Enumerator.form_uid == MonitorLocation.form_uid),
                isouter=True,
            )
            .join(
                surveyor_locations_subquery,
                SurveyorLocation.location_uid
                == surveyor_locations_subquery.c.location_uid,
                isouter=True,
            )
            .join(
                monitor_locations_subquery,
                MonitorLocation.location_uid
                == monitor_locations_subquery.c.location_uid,
                isouter=True,
            )
            .filter(Enumerator.form_uid == form_uid)
        ).all()

        for (
            enumerator,
            surveyor_status,
            monitor_status,
            surveyor_locations,
            monitor_locations,
        ) in result:
            enumerator.surveyor_status = surveyor_status
            enumerator.monitor_status = monitor_status
            enumerator.surveyor_locations = surveyor_locations
            enumerator.monitor_locations = monitor_locations

        response = jsonify(
            {
                "success": True,
                "data": [
                    enumerator.to_dict(
                        joined_keys=(
                            "surveyor_status",
                            "monitor_status",
                            "surveyor_locations",
                            "monitor_locations",
                        )
                    )
                    for enumerator, surveyor_status, monitor_status, surveyor_locations, monitor_locations in result
                ],
            }
        )

        return response, 200

    elif enumerator_type == "surveyor":
        result = (
            db.session.query(
                Enumerator,
                SurveyorForm.status.label("surveyor_status"),
                surveyor_locations_subquery.c.locations.label("surveyor_locations"),
            )
            .join(
                SurveyorForm,
                (Enumerator.enumerator_uid == SurveyorForm.enumerator_uid)
                & (Enumerator.form_uid == SurveyorForm.form_uid),
                isouter=True,
            )
            .join(
                SurveyorLocation,
                (Enumerator.enumerator_uid == SurveyorLocation.enumerator_uid)
                & (Enumerator.form_uid == SurveyorLocation.form_uid),
                isouter=True,
            )
            .join(
                surveyor_locations_subquery,
                SurveyorLocation.location_uid
                == surveyor_locations_subquery.c.location_uid,
                isouter=True,
            )
            .filter(Enumerator.form_uid == form_uid)
        ).all()

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
                    enumerator.to_dict(
                        joined_keys=(
                            "surveyor_status",
                            "surveyor_locations",
                        )
                    )
                    for enumerator, surveyor_status, surveyor_locations in result
                ],
            }
        )

        return response, 200

    elif enumerator_type == "monitor":
        result = (
            db.session.query(
                Enumerator,
                MonitorForm.status.label("monitor_status"),
                monitor_locations_subquery.c.locations.label("monitor_locations"),
            )
            .join(
                MonitorForm,
                (Enumerator.enumerator_uid == MonitorForm.enumerator_uid)
                & (Enumerator.form_uid == MonitorForm.form_uid),
                isouter=True,
            )
            .join(
                MonitorLocation,
                (Enumerator.enumerator_uid == MonitorLocation.enumerator_uid)
                & (Enumerator.form_uid == MonitorLocation.form_uid),
                isouter=True,
            )
            .join(
                monitor_locations_subquery,
                MonitorLocation.location_uid
                == monitor_locations_subquery.c.location_uid,
                isouter=True,
            )
            .filter(Enumerator.form_uid == form_uid)
        ).all()

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
                    enumerator.to_dict(
                        joined_keys=(
                            "monitor_status",
                            "monitor_locations",
                        )
                    )
                    for enumerator, monitor_status, monitor_locations in result
                ],
            }
        )

        return response, 200

    else:
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "message": "Invalid enumerator type",
                }
            ),
            400,
        )


@enumerators_bp.route("/<int:enumerator_uid>", methods=["GET"])
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
        if Enumerator.query.filter_by(enumerator_uid=enumerator_uid).first() is None:
            return jsonify({"error": "Enumerator not found"}), 404

        try:
            Enumerator.query.filter_by(enumerator_uid=enumerator_uid).update(
                {
                    Enumerator.enumerator_id: payload_validator.enumerator_id.data,
                    Enumerator.first_name: payload_validator.first_name.data,
                    Enumerator.middle_name: payload_validator.middle_name.data,
                    Enumerator.last_name: payload_validator.last_name.data,
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
def delete_enumerator(enumerator_uid):
    """
    Method to delete an enumerator from the database
    """

    payload_validator = UpdateEnumerator.from_json(request.get_json())

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if not payload_validator.validate():
        return jsonify({"success": False, "errors": payload_validator.errors}), 422

    if Enumerator.query.filter_by(enumerator_uid=enumerator_uid).first() is None:
        return jsonify({"error": "Enumerator not found"}), 404

    SurveyorForm.query.filter_by(enumerator_uid=enumerator_uid).delete()
    SurveyorLocation.query.filter_by(enumerator_uid=enumerator_uid).delete()
    MonitorForm.query.filter_by(enumerator_uid=enumerator_uid).delete()
    MonitorLocation.query.filter_by(enumerator_uid=enumerator_uid).delete()
    Enumerator.query.filter_by(enumerator_uid=enumerator_uid).delete()
    db.session.commit()

    return jsonify({"success": True}), 200


@enumerators_bp.route("/<int:enumerator_uid>/roles", methods=["POST"])
def create_enumerator_role(enumerator_uid):
    """
    Method to create an enumerator role in the database
    """

    payload_validator = CreateEnumeratorRole.from_json(request.get_json())

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

    if payload_validator.enumerator_type.data == "surveyor":
        # Check if the surveyor form already exists
        if (
            SurveyorForm.query.filter_by(
                enumerator_uid=enumerator_uid,
                form_uid=payload_validator.form_uid.data,
            ).first()
            is not None
        ):
            return (
                jsonify(
                    {
                        "error": "The enumerator is already assigned as a surveyor for the given form"
                    }
                ),
                409,
            )

        surveyor_form = SurveyorForm(
            enumerator_uid=enumerator_uid,
            form_uid=payload_validator.form_uid.data,
        )

        db.session.add(surveyor_form)

        if payload_validator.location_uid.data is not None:
            # Check if the surveyor location mapping already exists
            if (
                SurveyorLocation.query.filter_by(
                    enumerator_uid=enumerator_uid,
                    form_uid=payload_validator.form_uid.data,
                ).first()
                is not None
            ):
                return (
                    jsonify(
                        {
                            "error": "Surveyor location mapping for the form already exists for the given enumerator"
                        }
                    ),
                    409,
                )

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
                            "error": "Prime geo level not configured for the survey. Cannot map surveyor to location"
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

            # Add the surveyor location mapping
            surveyor_location = SurveyorLocation(
                enumerator_uid=enumerator_uid,
                form_uid=payload_validator.form_uid.data,
                location_uid=payload_validator.location_uid.data,
            )

            db.session.add(surveyor_location)

    if payload_validator.enumerator_type.data == "monitor":
        # Check if the monitor form already exists
        if (
            MonitorForm.query.filter_by(
                enumerator_uid=enumerator_uid,
                form_uid=payload_validator.form_uid.data,
            ).first()
            is not None
        ):
            return (
                jsonify(
                    {
                        "error": "The enumerator is already assigned as a monitor for the given form"
                    }
                ),
                409,
            )

        monitor_form = MonitorForm(
            enumerator_uid=enumerator_uid,
            form_uid=payload_validator.form_uid.data,
        )

        db.session.add(monitor_form)

        if payload_validator.location_uid.data is not None:
            # Check if the monitor location mapping already exists
            if (
                MonitorLocation.query.filter_by(
                    enumerator_uid=enumerator_uid,
                    form_uid=payload_validator.form_uid.data,
                ).first()
                is not None
            ):
                return (
                    jsonify(
                        {
                            "error": "Monitor location mapping for the form already exists for the given enumerator"
                        }
                    ),
                    409,
                )

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
                            "error": "Prime geo level not configured for the survey. Cannot map monitor to location"
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

            # Add the monitor location mapping
            monitor_location = MonitorLocation(
                enumerator_uid=enumerator_uid,
                form_uid=payload_validator.form_uid.data,
                location_uid=payload_validator.location_uid.data,
            )

            db.session.add(monitor_location)

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"success": True}), 200


@enumerators_bp.route("/<int:enumerator_uid>/roles", methods=["PUT"])
def update_enumerator_role(enumerator_uid):
    """
    Method to update an existing enumerator role in the database
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

    if payload_validator.enumerator_type.data == "surveyor":
        # Check if the surveyor form already exists
        if (
            SurveyorForm.query.filter_by(
                enumerator_uid=enumerator_uid,
                form_uid=payload_validator.form_uid.data,
            ).first()
            is None
        ):
            return (
                jsonify(
                    {
                        "error": "The enumerator is not assigned as a surveyor for the given form. Use the create endpoint to assign the enumerator as a surveyor.",
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
                            "error": "Prime geo level not configured for the survey. Cannot map surveyor to location"
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

            # Add the surveyor location mapping
            surveyor_location = SurveyorLocation(
                enumerator_uid=enumerator_uid,
                form_uid=payload_validator.form_uid.data,
                location_uid=payload_validator.location_uid.data,
            )

            # Do an upsert of the surveyor location mapping
            statement = (
                pg_insert(SurveyorLocation)
                .values(
                    enumerator_uid=enumerator_uid,
                    form_uid=payload_validator.form_uid.data,
                    location_uid=payload_validator.location_uid.data,
                )
                .on_conflict_do_update(
                    constraint="surveyor_location_pkey",
                    set_={
                        "location_uid": payload_validator.location_uid.data,
                    },
                )
            )

            db.session.execute(statement)

        else:
            SurveyorLocation.query.filter_by(
                enumerator_uid=enumerator_uid,
                form_uid=payload_validator.form_uid.data,
            ).delete()

    if payload_validator.enumerator_type.data == "monitor":
        # Check if the monitor form already exists
        if (
            MonitorForm.query.filter_by(
                enumerator_uid=enumerator_uid,
                form_uid=payload_validator.form_uid.data,
            ).first()
            is None
        ):
            return (
                jsonify(
                    {
                        "error": "The enumerator is not assigned as a monitor for the given form. Use the create endpoint to assign the enumerator as a monitor.",
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
                            "error": "Prime geo level not configured for the survey. Cannot map surveyor to location"
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

            # Add the monitor location mapping
            monitor_location = MonitorLocation(
                enumerator_uid=enumerator_uid,
                form_uid=payload_validator.form_uid.data,
                location_uid=payload_validator.location_uid.data,
            )

            # Do an upsert of the monitor location mapping
            statement = (
                pg_insert(MonitorLocation)
                .values(
                    enumerator_uid=enumerator_uid,
                    form_uid=payload_validator.form_uid.data,
                    location_uid=payload_validator.location_uid.data,
                )
                .on_conflict_do_update(
                    constraint="monitor_location_pkey",
                    set_={
                        "location_uid": payload_validator.location_uid.data,
                    },
                )
            )

            db.session.execute(statement)

        else:
            MonitorLocation.query.filter_by(
                enumerator_uid=enumerator_uid,
                form_uid=payload_validator.form_uid.data,
            ).delete()

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"success": True}), 200


@enumerators_bp.route("/<int:enumerator_uid>/roles", methods=["DELETE"])
def delete_enumerator_role(enumerator_uid):
    """
    Method to delete an enumerator role from the database
    """

    payload_validator = DeleteEnumeratorRole.from_json(request.get_json())

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

    if payload_validator.enumerator_type.data == "surveyor":
        if (
            SurveyorForm.query.filter_by(
                enumerator_uid=enumerator_uid,
                form_uid=payload_validator.form_uid.data,
            ).first()
            is None
        ):
            return (
                jsonify(
                    {
                        "error": "The enumerator is not assigned as a surveyor for the given form. Nothing to delete.",
                        "success": False,
                    }
                ),
                404,
            )

        SurveyorForm.query.filter_by(enumerator_uid=enumerator_uid).delete()
        SurveyorLocation.query.filter_by(enumerator_uid=enumerator_uid).delete()

    elif payload_validator.enumerator_type.data == "monitor":
        if (
            MonitorForm.query.filter_by(
                enumerator_uid=enumerator_uid,
                form_uid=payload_validator.form_uid.data,
            ).first()
            is None
        ):
            return (
                jsonify(
                    {
                        "error": "The enumerator is not assigned as a monitor for the given form. Nothing to delete.",
                        "success": False,
                    }
                ),
                404,
            )

        MonitorForm.query.filter_by(enumerator_uid=enumerator_uid).delete()
        MonitorLocation.query.filter_by(enumerator_uid=enumerator_uid).delete()

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"success": True}), 200


# Patch method to update an enumerator's status
@enumerators_bp.route("/<int:enumerator_uid>/roles/status", methods=["PATCH"])
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

    if payload_validator.enumerator_type.data == "surveyor":
        surveyor_form = SurveyorForm.query.filter_by(
            enumerator_uid=enumerator_uid, form_uid=payload_validator.form_uid.data
        ).first()
        if surveyor_form is None:
            return (
                jsonify(
                    {
                        "error": "The enumerator is not assigned as a surveyor for the given form. Nothing to update.",
                        "success": False,
                    }
                ),
                404,
            )

        surveyor_form.status = payload_validator.status.data

    elif payload_validator.enumerator_type.data == "monitor":
        monitor_form = MonitorForm.query.filter_by(
            enumerator_uid=enumerator_uid, form_uid=payload_validator.form_uid.data
        ).first()
        if monitor_form is None:
            return (
                jsonify(
                    {
                        "error": "The enumerator is not assigned as a monitor for the given form. Nothing to update.",
                        "success": False,
                    }
                ),
                404,
            )
        monitor_form.status = payload_validator.status.data

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"success": True}), 200


# @enumerators_bp.route("/<int:enumerator_uid>/roles", methods=["GET"])
# def get_enumerator_roles(enumerator_uid):
#     """
#     Method to get an enumerator's roles from the database
#     """

#     payload_validator = GetEnumeratorRolesQueryParamValidator.from_json(
#         request.get_json()
#     )

#     if not payload_validator.validate():
#         return jsonify({"success": False, "errors": payload_validator.errors}), 422

#     if Enumerator.query.filter_by(enumerator_uid=enumerator_uid).first() is None:
#         return jsonify({"error": "Enumerator not found"}), 404

#     if (
#         ParentForm.query.filter_by(form_uid=payload_validator.form_uid.data).first()
#         is None
#     ):
#         return jsonify({"error": "Form not found"}), 404

#     if payload_validator.enumerator_type.data is None:
#         result = (
#             db.query(
#                 Enumerator,
#                 MonitorForm.status.label("monitor_status"),
#                 MonitorLocation.location_uid.label("monitor_location_uid"),
#             )
#             .join(
#                 MonitorForm,
#                 Enumerator.enumerator_uid == MonitorForm.enumerator_uid,
#                 Enumerator.form_uid == MonitorForm.form_uid,
#                 isouter=True,
#             )
#             .join(
#                 MonitorLocation,
#                 Enumerator.enumerator_uid == MonitorLocation.enumerator_uid,
#                 Enumerator.form_uid == MonitorLocation.form_uid,
#                 isouter=True,
#             )
#             .filter(
#                 Enumerator.form_uid == payload_validator.form_uid.data,
#                 Enumerator.enumerator_uid == enumerator_uid,
#             )
#             .all()
#         )

#         for enumerator, monitor_status, monitor_location_uid in result:
#             enumerator.monitor_status = monitor_status
#             enumerator.monitor_location_uid = monitor_location_uid

#         response = jsonify(
#             {
#                 "success": True,
#                 "data": [
#                     enumerator.to_dict(
#                         joined_keys=(monitor_status, monitor_location_uid)
#                     )
#                     for enumerator in result
#                 ],
#             }
#         )
#         {
#             "form_uid"
#             "roles": [
#                 {
#                     "enumerator_type": "surveyor",
#                     "status": "active",
#                     "location_uid": "1234",
#                 },
#             ]
#         }

#     return jsonify({"success": True}), 200
