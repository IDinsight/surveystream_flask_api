from flask import jsonify, request
from app.blueprints.assignments.models import SurveyorAssignment
from app.blueprints.targets.models import Target
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_query_params,
    validate_payload,
)
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
from app.blueprints.locations.models import Location
from .models import (
    Enumerator,
    SurveyorForm,
    SurveyorLocation,
    MonitorForm,
    MonitorLocation,
    EnumeratorColumnConfig,
    SurveyorStats,
)
from .routes import enumerators_bp
from .validators import (
    EnumeratorsFileUploadValidator,
    EnumeratorsQueryParamValidator,
    GetEnumeratorsQueryParamValidator,
    UpdateEnumerator,
    CreateEnumeratorRole,
    UpdateEnumeratorRole,
    UpdateEnumeratorRoleStatus,
    GetEnumeratorRolesQueryParamValidator,
    BulkUpdateEnumeratorsValidator,
    BulkUpdateEnumeratorsRoleLocationValidator,
    UpdateEnumeratorsColumnConfig,
    EnumeratorColumnConfigQueryParamValidator,
    UpdateSurveyorStats,
    SurveyorStatsQueryParamValidator,
)
from .utils import (
    EnumeratorsUpload,
    EnumeratorColumnMapping,
)
from .queries import build_prime_locations_with_location_hierarchy_subquery
from .errors import (
    HeaderRowEmptyError,
    InvalidEnumeratorRecordsError,
    InvalidFileStructureError,
    InvalidColumnMappingError,
)
import binascii


@enumerators_bp.route("", methods=["POST"])
@logged_in_active_user_required
@validate_query_params(EnumeratorsQueryParamValidator)
@validate_payload(EnumeratorsFileUploadValidator)
@custom_permissions_required("WRITE Enumerators", "query", "form_uid")
def upload_enumerators(validated_query_params, validated_payload):
    """
    Method to validate the uploaded enumerators file and save it to the database
    """

    form_uid = validated_query_params.form_uid.data

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

    # Get the prime geo level from the survey configuration
    prime_geo_level_uid = (
        Survey.query.filter_by(survey_uid=survey_uid).first().prime_geo_level_uid
    )

    optional_hardcoded_fields = ["language", "gender", "home_address"]

    try:
        column_mapping = EnumeratorColumnMapping(
            validated_payload.column_mapping.data,
            prime_geo_level_uid,
            optional_hardcoded_fields,
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

    # Create an EnumeratorsUpload object from the uploaded file
    try:
        enumerators_upload = EnumeratorsUpload(
            csv_string=base64.b64decode(
                validated_payload.file.data, validate=True
            ).decode("utf-8"),
            column_mapping=column_mapping,
            survey_uid=survey_uid,
            form_uid=form_uid,
            optional_hardcoded_fields=optional_hardcoded_fields,
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
            column_mapping,
            prime_geo_level_uid,
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

    try:
        enumerators_upload.save_records(
            column_mapping,
            validated_payload.mode.data,
        )

    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify(message="Success"), 200


@enumerators_bp.route("", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(GetEnumeratorsQueryParamValidator)
@custom_permissions_required("READ Enumerators", "query", "form_uid")
def get_enumerators(validated_query_params):
    """
    Method to retrieve the enumerators information from the database
    """

    form_uid = validated_query_params.form_uid.data
    enumerator_type = validated_query_params.enumerator_type.data
    user_uid = current_user.user_uid

    # Check if the logged in user has permission to access the given form

    survey_uid = ParentForm.query.filter_by(form_uid=form_uid).first().survey_uid

    # This will be used to join in the locations hierarchy for each enumerator
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
@custom_permissions_required("READ Enumerators", "path", "enumerator_uid")
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
@validate_payload(UpdateEnumerator)
@custom_permissions_required("WRITE Enumerators", "path", "enumerator_uid")
def update_enumerator(enumerator_uid, validated_payload):
    """
    Method to update an enumerator in the database
    """

    payload = request.get_json()

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
        # exclude column_mapping from these checks
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
        # exclude column_mapping from these checks
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
        Enumerator.query.filter_by(enumerator_uid=enumerator_uid).update(
            {
                Enumerator.enumerator_id: validated_payload.enumerator_id.data,
                Enumerator.name: validated_payload.name.data,
                Enumerator.email: validated_payload.email.data,
                Enumerator.mobile_primary: validated_payload.mobile_primary.data,
                Enumerator.language: validated_payload.language.data,
                Enumerator.home_address: validated_payload.home_address.data,
                Enumerator.gender: validated_payload.gender.data,
                Enumerator.custom_fields: payload["custom_fields"],
            },
            synchronize_session="fetch",
        )
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify({"success": True}), 200


@enumerators_bp.route("/<int:enumerator_uid>", methods=["DELETE"])
@logged_in_active_user_required
@custom_permissions_required("WRITE Enumerators", "path", "enumerator_uid")
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
@validate_payload(UpdateEnumeratorRole)
@custom_permissions_required("WRITE Enumerators", "path", "enumerator_uid")
def update_enumerator_role(enumerator_uid, validated_payload):
    """
    Method to update an existing enumerator's role-location in the database
    Only the location mapping can be updated
    """

    form_uid = validated_payload.form_uid.data
    enumerator_type = validated_payload.enumerator_type.data
    location_uid = validated_payload.location_uid.data

    if Enumerator.query.filter_by(enumerator_uid=enumerator_uid).first() is None:
        return jsonify({"error": "Enumerator not found"}), 404

    form = ParentForm.query.filter_by(form_uid=form_uid).first()
    if form is None:
        return jsonify({"error": "Form not found"}), 404

    model_lookup = {
        "surveyor": {"form_model": SurveyorForm, "location_model": SurveyorLocation},
        "monitor": {"form_model": MonitorForm, "location_model": MonitorLocation},
    }

    # Check if the form-role already exists
    if (
        db.session.query(model_lookup[enumerator_type]["form_model"])
        .filter_by(
            enumerator_uid=enumerator_uid,
            form_uid=form_uid,
        )
        .first()
        is None
    ):
        return (
            jsonify(
                {
                    "error": f"The enumerator is not assigned as a {enumerator_type} for the given form. Use the create endpoint to assign the enumerator as a {enumerator_type}.",
                    "success": False,
                }
            ),
            409,
        )

    if location_uid is not None:
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
                        "error": f"Prime geo level not configured for the survey. Cannot map {enumerator_type} to location"
                    }
                ),
                400,
            )

        # Check if the location exists for the form's survey
        location = Location.query.filter_by(
            location_uid=location_uid,
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
            pg_insert(model_lookup[enumerator_type]["location_model"])
            .values(
                enumerator_uid=enumerator_uid,
                form_uid=form_uid,
                location_uid=location_uid,
            )
            .on_conflict_do_update(
                constraint=f"pkey_{enumerator_type}_location",
                set_={
                    "location_uid": location_uid,
                },
            )
        )

        db.session.execute(statement)

    else:
        db.session.query(model_lookup[enumerator_type]["location_model"]).filter_by(
            enumerator_uid=enumerator_uid,
            form_uid=form_uid,
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
@validate_payload(UpdateEnumeratorRoleStatus)
@custom_permissions_required("WRITE Enumerators", "path", "enumerator_uid")
def update_enumerator_status(enumerator_uid, validated_payload):
    """
    Method to update an enumerator's status
    """

    form_uid = validated_payload.form_uid.data
    enumerator_type = validated_payload.enumerator_type.data
    status = validated_payload.status.data

    if Enumerator.query.filter_by(enumerator_uid=enumerator_uid).first() is None:
        return jsonify({"error": "Enumerator not found"}), 404

    if ParentForm.query.filter_by(form_uid=form_uid).first() is None:
        return jsonify({"error": "Form not found"}), 404

    model_lookup = {
        "surveyor": SurveyorForm,
        "monitor": MonitorForm,
    }

    result = (
        db.session.query(model_lookup[enumerator_type])
        .filter_by(enumerator_uid=enumerator_uid, form_uid=form_uid)
        .first()
    )

    if result is None:
        return (
            jsonify(
                {
                    "error": f"The enumerator is not assigned as a {enumerator_type} for the given form. Nothing to update.",
                    "success": False,
                }
            ),
            404,
        )

    result.status = status

    # Releasing the assignment on suryeyor dropout
    if status == "Dropout":
        subquery = db.session.query(SurveyorAssignment.target_uid).join(
            Target, Target.target_uid == SurveyorAssignment.target_uid
        ).filter(
            Target.form_uid == form_uid,
            SurveyorAssignment.enumerator_uid == enumerator_uid,
        ).subquery()

        # Use the subquery to delete the assignment
        db.session.query(SurveyorAssignment).filter(
            SurveyorAssignment.target_uid.in_(subquery)
        ).delete(synchronize_session=False)

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"success": True}), 200


@enumerators_bp.route("/<int:enumerator_uid>/roles", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(GetEnumeratorRolesQueryParamValidator)
@custom_permissions_required("READ Enumerators", "path", "enumerator_uid")
def get_enumerator_roles(enumerator_uid, validated_query_params):
    """
    Method to get an enumerator's roles from the database
    """

    enumerator_type = validated_query_params.enumerator_type.data
    form_uid = validated_query_params.form_uid.data

    if Enumerator.query.filter_by(enumerator_uid=enumerator_uid).first() is None:
        return jsonify({"error": "Enumerator not found"}), 404

    roles = []

    if enumerator_type == "surveyor" or enumerator_type is None:
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
                SurveyorForm.form_uid == form_uid,
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

    if enumerator_type == "monitor" or enumerator_type is None:
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
                MonitorForm.form_uid == form_uid,
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
                    "form_uid": form_uid,
                    "roles": roles,
                },
            }
        ),
        200,
    )


# Patch method to bulk update enumerator details
@enumerators_bp.route("", methods=["PATCH"])
@logged_in_active_user_required
@validate_payload(BulkUpdateEnumeratorsValidator)
@custom_permissions_required("WRITE Enumerators", "body", "form_uid")
def bulk_update_enumerators_custom_fields(validated_payload):
    """
    Method to bulk update enumerators
    """

    payload = request.get_json()

    form_uid = validated_payload.form_uid.data
    enumerator_uids = validated_payload.enumerator_uids.data

    column_config = EnumeratorColumnConfig.query.filter(
        EnumeratorColumnConfig.form_uid == form_uid,
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
        Enumerator.query.filter(Enumerator.enumerator_uid.in_(enumerator_uids)).update(
            {key: payload[key] for key in personal_details_patch_keys},
            synchronize_session=False,
        )

    if len(custom_fields_patch_keys) > 0:
        for custom_field in custom_fields_patch_keys:
            enumerator_records = Enumerator.query.filter(
                Enumerator.enumerator_uid.in_(enumerator_uids)
            ).all()

            for enumerator_record in enumerator_records:
                for custom_field in custom_fields_patch_keys:
                    # Update the custom_fields dictionary
                    enumerator_record.custom_fields[custom_field] = payload[
                        custom_field
                    ]

    # Commit changes
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"success": True}), 200


@enumerators_bp.route("/roles/locations", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(BulkUpdateEnumeratorsRoleLocationValidator)
@custom_permissions_required("WRITE Enumerators", "body", "form_uid")
def bulk_update_enumerators_role_locations(validated_payload):
    """
    Method to bulk update enumerators' locations for a given role
    """

    form_uid = validated_payload.form_uid.data
    enumerator_type = validated_payload.enumerator_type.data
    location_uids = validated_payload.data["location_uids"]
    enumerator_uids = validated_payload.data["enumerator_uids"]

    column_config = EnumeratorColumnConfig.query.filter(
        EnumeratorColumnConfig.form_uid == form_uid,
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
    if location_uids is not None and len(location_uids) > 0:
        returned_location_uids = [
            location.location_uid
            for location in Location.query.filter(
                Location.location_uid.in_(validated_payload.data["location_uids"])
            ).all()
        ]

        for location_uid in location_uids:
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
            Location.location_uid.in_(location_uids)
        ).all()
    ]

    for location_uid in location_uids:
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

    model = model_lookup[enumerator_type]
    db.session.query(model).filter(
        model.enumerator_uid.in_(enumerator_uids),
        model.form_uid == form_uid,
    ).delete()

    if location_uids is not None:
        for enumerator_uid in enumerator_uids:
            for location_uid in location_uids:
                db.session.add(
                    model(
                        enumerator_uid=enumerator_uid,
                        form_uid=form_uid,
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
@validate_payload(UpdateEnumeratorsColumnConfig)
@custom_permissions_required("WRITE Enumerators", "body", "form_uid")
def update_enumerator_column_config(validated_payload):
    """
    Method to update enumerators' column configuration
    """

    payload = request.get_json()
    form_uid = validated_payload.form_uid.data

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

    EnumeratorColumnConfig.query.filter(
        EnumeratorColumnConfig.form_uid == form_uid,
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
                form_uid=form_uid,
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
@validate_query_params(EnumeratorColumnConfigQueryParamValidator)
@custom_permissions_required("READ Enumerators", "query", "form_uid")
def get_enumerator_column_config(validated_query_params):
    """
    Method to get enumerators' column configuration
    """

    form_uid = validated_query_params.form_uid.data

    column_config = EnumeratorColumnConfig.query.filter(
        EnumeratorColumnConfig.form_uid == form_uid,
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


@enumerators_bp.route("/surveyor-stats", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(UpdateSurveyorStats)
@custom_permissions_required("WRITE Enumerators", "body", "form_uid")
def update_surveyor_stats(validated_payload):
    """
    Method to update surveyor stats
    """

    payload = request.get_json()
    form_uid = validated_payload.form_uid.data

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

    SurveyorStats.query.filter(
        SurveyorStats.form_uid == form_uid,
    ).delete()

    db.session.flush()

    for surveyor in payload["surveyor_stats"]:
        enumerator_id = surveyor["enumerator_id"]
        enumerator = Enumerator.query.filter(
            Enumerator.form_uid == form_uid,
            Enumerator.enumerator_id == enumerator_id,
        ).first()

        if enumerator is not None:
            db.session.add(
                SurveyorStats(
                    form_uid=form_uid,
                    enumerator_uid=enumerator.enumerator_uid,
                    avg_num_submissions_per_day=surveyor["avg_num_submissions_per_day"],
                    avg_num_completed_per_day=surveyor["avg_num_completed_per_day"],
                )
            )

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"success": True}), 200


@enumerators_bp.route("/surveyor-stats", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(SurveyorStatsQueryParamValidator)
@custom_permissions_required("READ Enumerators", "query", "form_uid")
def get_surveyor_stats(validated_query_params):
    """
    Method to get surveyor stats
    """

    form_uid = validated_query_params.form_uid.data

    surveyor_stats = (
        db.session.query(Enumerator, SurveyorStats)
        .join(
            SurveyorForm,
            (SurveyorForm.enumerator_uid == Enumerator.enumerator_uid)
            & (SurveyorForm.form_uid == Enumerator.form_uid),
            isouter=True,
        )
        .filter(
            Enumerator.enumerator_uid == SurveyorStats.enumerator_uid,
            Enumerator.form_uid == SurveyorStats.form_uid,
            SurveyorStats.form_uid == form_uid,
        )
        .all()
    )

    return jsonify(
        {
            "success": True,
            "data": [
                {
                    "enumerator_id": each_enumerator.enumerator_id,
                    "avg_num_submissions_per_day": each_surveyor_stats.avg_num_submissions_per_day,
                    "avg_num_completed_per_day": each_surveyor_stats.avg_num_completed_per_day,
                }
                for each_enumerator, each_surveyor_stats in surveyor_stats
            ],
        }
    )
