import base64
import binascii
from datetime import datetime

from flask import jsonify
from flask_login import current_user
from sqlalchemy import Integer, column, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import Values

from app import db
from app.blueprints.emails.models import EmailConfig, ManualEmailTrigger
from app.blueprints.enumerators.models import Enumerator, SurveyorForm, SurveyorLocation
from app.blueprints.enumerators.queries import (
    build_prime_locations_with_location_hierarchy_subquery,
)
from app.blueprints.forms.models import Form
from app.blueprints.locations.errors import InvalidGeoLevelHierarchyError
from app.blueprints.locations.models import GeoLevel
from app.blueprints.locations.utils import GeoLevelHierarchy
from app.blueprints.mapping.errors import MappingError
from app.blueprints.mapping.utils import SurveyorMapping, TargetMapping
from app.blueprints.roles.utils import check_if_survey_admin
from app.blueprints.surveys.models import Survey
from app.blueprints.targets.models import Target, TargetStatus
from app.blueprints.targets.queries import (
    build_bottom_level_locations_with_location_hierarchy_subquery,
)
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_payload,
    validate_query_params,
)

from . import assignments_bp
from .errors import (
    HeaderRowEmptyError,
    InvalidAssignmentRecordsError,
    InvalidColumnMappingError,
    InvalidFileStructureError,
)
from .models import SurveyorAssignment
from .queries import (
    build_child_users_with_supervisors_query,
    build_surveyor_formwise_productivity_subquery,
)
from .utils import (
    AssignmentsColumnMapping,
    AssignmentsUpload,
    get_next_assignment_email_schedule,
)
from .validators import (
    AssignmentsEmailValidator,
    AssignmentsFileUploadValidator,
    AssignmentsQueryParamValidator,
    UpdateSurveyorAssignmentsValidator,
)


@assignments_bp.route("", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(AssignmentsQueryParamValidator)
@custom_permissions_required("READ Assignments", "query", "form_uid")
def view_assignments(validated_query_params):
    """
    Returns assignment information for a form and user
    """

    form_uid = validated_query_params.form_uid.data
    user_uid = current_user.user_uid

    survey_uid = Form.query.filter_by(form_uid=form_uid).first().survey_uid

    # We need to get the bottom level geo level UID for the survey in order to join in the location information
    # Only do this if the targets have locations
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

    # Get the mapping of targets to the smallest supervisor level
    # This is used filter out targets mapped to the current user
    # or to their child supervisors
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
    mappings = target_mapping.generate_mappings()
    mappings_query = select(
        Values(
            column("target_uid", Integer),
            column("supervisor_uid", Integer),
            name="mappings",
        ).data(
            [(mapping["target_uid"], mapping["supervisor_uid"]) for mapping in mappings]
            if len(mappings) > 0
            else [
                (0, 0)
            ]  # If there are no mappings, we still need to return a row with 0 values
        )
    ).subquery()

    # Get the child supervisors for the current logged in user
    is_survey_admin = check_if_survey_admin(user_uid, survey_uid)
    child_users_with_supervisors_query = build_child_users_with_supervisors_query(
        user_uid, survey_uid, target_mapping.bottom_level_role_uid, is_survey_admin
    )

    assignments_query = (
        db.session.query(
            Target,
            TargetStatus,
            Enumerator,
            target_locations_subquery.c.locations,
            child_users_with_supervisors_query.c.supervisors,
        )
        .outerjoin(
            SurveyorAssignment,
            Target.target_uid == SurveyorAssignment.target_uid,
        )
        .outerjoin(
            Enumerator,
            SurveyorAssignment.enumerator_uid == Enumerator.enumerator_uid,
        )
        .outerjoin(
            TargetStatus,
            Target.target_uid == TargetStatus.target_uid,
        )
        .outerjoin(
            target_locations_subquery,
            Target.location_uid == target_locations_subquery.c.location_uid,
        )
    )

    # If the user is a survey admin, we want to show all targets, even if they are not assigned
    if is_survey_admin:
        assignments_query = (
            assignments_query.outerjoin(
                mappings_query,
                Target.target_uid == mappings_query.c.target_uid,
            )
            .outerjoin(
                child_users_with_supervisors_query,
                mappings_query.c.supervisor_uid
                == child_users_with_supervisors_query.c.user_uid,
            )
            .filter(Target.form_uid == form_uid)
        )
    else:
        # If the user is not a survey admin, we only want to show targets that are assigned to them or their child supervisors
        assignments_query = (
            assignments_query.join(
                mappings_query,
                Target.target_uid == mappings_query.c.target_uid,
            )
            .join(
                child_users_with_supervisors_query,
                mappings_query.c.supervisor_uid
                == child_users_with_supervisors_query.c.user_uid,
            )
            .filter(Target.form_uid == form_uid)
        )

    # Note that we use gettatr() here because we are joining in models that may not have a joined row for a given target, so the row's object corresponding to that model will be None
    response = jsonify(
        {
            "success": True,
            "data": [
                {
                    **target.to_dict(),
                    **{
                        "assigned_enumerator_uid": getattr(
                            enumerator, "enumerator_uid", None
                        ),
                        "assigned_enumerator_id": getattr(
                            enumerator, "enumerator_id", None
                        ),
                        "assigned_enumerator_name": getattr(enumerator, "name", None),
                        "assigned_enumerator_home_address": getattr(
                            enumerator, "home_address", None
                        ),
                        "assigned_enumerator_language": getattr(
                            enumerator, "language", None
                        ),
                        "assigned_enumerator_gender": getattr(
                            enumerator, "gender", None
                        ),
                        "assigned_enumerator_email": getattr(enumerator, "email", None),
                        "assigned_enumerator_mobile_primary": getattr(
                            enumerator, "mobile_primary", None
                        ),
                        "assigned_enumerator_custom_fields": getattr(
                            enumerator, "custom_fields", None
                        ),
                    },
                    **{
                        "completed_flag": getattr(
                            target_status, "completed_flag", None
                        ),
                        "refusal_flag": getattr(target_status, "refusal_flag", None),
                        "num_attempts": getattr(target_status, "num_attempts", 0),
                        "last_attempt_survey_status": getattr(
                            target_status, "last_attempt_survey_status", None
                        ),
                        "last_attempt_survey_status_label": getattr(
                            target_status,
                            "last_attempt_survey_status_label",
                            "Not Attempted",
                        ),
                        "final_survey_status": getattr(
                            target_status, "final_survey_status", None
                        ),
                        "final_survey_status_label": getattr(
                            target_status,
                            "final_survey_status_label",
                            "Not Attempted",
                        ),
                        "target_assignable": getattr(
                            target_status,
                            "target_assignable",
                            True,  # If the target_status is None, the target is new and hence, assignable
                        ),
                        "webapp_tag_color": getattr(
                            target_status, "webapp_tag_color", None
                        ),
                        "revisit_sections": getattr(
                            target_status, "revisit_sections", None
                        ),
                        "scto_fields": getattr(target_status, "scto_fields", None),
                    },
                    "target_locations": target_locations,
                    "supervisors": supervisors,
                }
                for target, target_status, enumerator, target_locations, supervisors in assignments_query.all()
            ],
        }
    )

    return response, 200


@assignments_bp.route("/enumerators", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(AssignmentsQueryParamValidator)
@custom_permissions_required("READ Assignments", "query", "form_uid")
def view_assignments_enumerators(validated_query_params):
    """
    Returns enumerators eligible to be assigned for a form and user
    """

    form_uid = validated_query_params.form_uid.data
    user_uid = current_user.user_uid

    survey_uid = Form.query.filter_by(form_uid=form_uid).first().survey_uid

    # Get the mapping of surveyors to the smallest supervisor level
    # This is used filter out surveyors mapped to the current user
    # or to their child supervisors
    try:
        surveyor_mapping = SurveyorMapping(form_uid)
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
    surveyor_mappings = surveyor_mapping.generate_mappings()
    surveyor_mappings_query = select(
        Values(
            column("enumerator_uid", Integer),
            column("supervisor_uid", Integer),
            name="mappings",
        ).data(
            [
                (mapping["enumerator_uid"], mapping["supervisor_uid"])
                for mapping in surveyor_mappings
            ]
            if len(surveyor_mappings) > 0
            else [
                (0, 0)
            ]  # If there are no mappings, we still need to return a row with 0 values
        )
    ).subquery()

    prime_geo_level_uid = surveyor_mapping.prime_geo_level_uid
    prime_locations_with_location_hierarchy_subquery = (
        build_prime_locations_with_location_hierarchy_subquery(
            survey_uid, prime_geo_level_uid
        )
    )
    surveyor_formwise_productivity_subquery = (
        build_surveyor_formwise_productivity_subquery(survey_uid)
    )

    # Get the child supervisors for the current logged in user
    is_survey_admin = check_if_survey_admin(user_uid, survey_uid)
    child_users_with_supervisors_query = build_child_users_with_supervisors_query(
        user_uid, survey_uid, surveyor_mapping.bottom_level_role_uid, is_survey_admin
    )

    assignment_enumerators_query = (
        db.session.query(
            Enumerator,
            SurveyorForm,
            prime_locations_with_location_hierarchy_subquery.c.locations,
            surveyor_formwise_productivity_subquery.c.form_productivity,
            child_users_with_supervisors_query.c.supervisors,
        )
        .join(SurveyorForm, Enumerator.enumerator_uid == SurveyorForm.enumerator_uid)
        .outerjoin(
            SurveyorLocation,
            (SurveyorForm.enumerator_uid == SurveyorLocation.enumerator_uid)
            & (SurveyorForm.form_uid == SurveyorLocation.form_uid),
        )
        .outerjoin(
            prime_locations_with_location_hierarchy_subquery,
            SurveyorLocation.location_uid
            == prime_locations_with_location_hierarchy_subquery.c.location_uid,
        )
        .outerjoin(
            surveyor_formwise_productivity_subquery,
            Enumerator.enumerator_uid
            == surveyor_formwise_productivity_subquery.c.enumerator_uid,
        )
    )

    if is_survey_admin:
        assignment_enumerators_query = (
            assignment_enumerators_query.outerjoin(
                surveyor_mappings_query,
                Enumerator.enumerator_uid == surveyor_mappings_query.c.enumerator_uid,
            )
            .outerjoin(
                child_users_with_supervisors_query,
                surveyor_mappings_query.c.supervisor_uid
                == child_users_with_supervisors_query.c.user_uid,
            )
            .filter(
                SurveyorForm.form_uid == form_uid,
            )
        )
    else:
        assignment_enumerators_query = (
            assignment_enumerators_query.join(
                surveyor_mappings_query,
                Enumerator.enumerator_uid == surveyor_mappings_query.c.enumerator_uid,
            )
            .join(
                child_users_with_supervisors_query,
                surveyor_mappings_query.c.supervisor_uid
                == child_users_with_supervisors_query.c.user_uid,
            )
            .filter(
                SurveyorForm.form_uid == form_uid,
            )
        )

    response = jsonify(
        {
            "success": True,
            "data": [
                {
                    **enumerator.to_dict(),
                    "surveyor_status": surveyor_form.status,
                    "surveyor_locations": locations,
                    "form_productivity": form_productivity,
                    "supervisors": supervisors,
                }
                for enumerator, surveyor_form, locations, form_productivity, supervisors in assignment_enumerators_query.all()
            ],
        }
    )

    return response, 200


@assignments_bp.route("/targets", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(AssignmentsQueryParamValidator)
@custom_permissions_required("READ Assignments", "query", "form_uid")
def view_assignments_targets(validated_query_params):
    """
    Returns targets eligible to be assigned for a form and user
    """

    form_uid = validated_query_params.form_uid.data
    user_uid = current_user.user_uid

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

    # Get the mapping of targets to the smallest supervisor level
    # This is used filter out targets mapped to the current user
    # or to their child supervisors
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

    target_mappings = target_mapping.generate_mappings()
    mappings_query = select(
        Values(
            column("target_uid", Integer),
            column("supervisor_uid", Integer),
            name="mappings",
        ).data(
            [
                (mapping["target_uid"], mapping["supervisor_uid"])
                for mapping in target_mappings
            ]
            if len(target_mappings) > 0
            else [
                (0, 0)
            ]  # If there are no mappings, we still need to return a row with 0 values
        )
    ).subquery()

    # Get the child supervisors for the current logged in user
    is_survey_admin = check_if_survey_admin(user_uid, survey_uid)
    child_users_with_supervisors_query = build_child_users_with_supervisors_query(
        user_uid, survey_uid, target_mapping.bottom_level_role_uid, is_survey_admin
    )

    assignment_targets_query = (
        db.session.query(
            Target,
            TargetStatus,
            target_locations_subquery.c.locations.label("target_locations"),
            child_users_with_supervisors_query.c.supervisors,
        )
        .outerjoin(
            TargetStatus,
            Target.target_uid == TargetStatus.target_uid,
        )
        .outerjoin(
            target_locations_subquery,
            Target.location_uid == target_locations_subquery.c.location_uid,
        )
    )

    if is_survey_admin:
        assignment_targets_query = (
            assignment_targets_query.outerjoin(
                mappings_query,
                Target.target_uid == mappings_query.c.target_uid,
            )
            .outerjoin(
                child_users_with_supervisors_query,
                mappings_query.c.supervisor_uid
                == child_users_with_supervisors_query.c.user_uid,
            )
            .filter(Target.form_uid == form_uid)
        )
    else:
        assignment_targets_query = (
            assignment_targets_query.join(
                mappings_query,
                Target.target_uid == mappings_query.c.target_uid,
            )
            .join(
                child_users_with_supervisors_query,
                mappings_query.c.supervisor_uid
                == child_users_with_supervisors_query.c.user_uid,
            )
            .filter(Target.form_uid == form_uid)
        )

    response = jsonify(
        {
            "success": True,
            "data": [
                {
                    **target.to_dict(),
                    "completed_flag": getattr(target_status, "completed_flag", None),
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
                    "supervisors": supervisors,
                }
                for target, target_status, target_locations, supervisors in assignment_targets_query.all()
            ],
        }
    )

    return response, 200


@assignments_bp.route("", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(UpdateSurveyorAssignmentsValidator)
@custom_permissions_required("WRITE Assignments", "body", "form_uid")
def update_assignments(validated_payload):
    """
    Updates assignment mapping
    """
    form_uid = validated_payload.form_uid.data
    assignments = validated_payload.assignments.data
    validate_mapping = validated_payload.validate_mapping.data

    user_uid = current_user.user_uid
    survey_uid = Form.query.filter_by(form_uid=form_uid).first().survey_uid

    if validate_mapping:
        try:
            target_mapping = TargetMapping(form_uid)
            surveyor_mapping = SurveyorMapping(form_uid)
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

        target_mappings = target_mapping.generate_mappings()
        surveyor_mappings = surveyor_mapping.generate_mappings()

        target_mappings_query = select(
            Values(
                column("target_uid", Integer),
                column("supervisor_uid", Integer),
                name="mappings",
            ).data(
                [
                    (mapping["target_uid"], mapping["supervisor_uid"])
                    for mapping in target_mappings
                ]
                if len(target_mappings) > 0
                else [
                    (0, 0)
                ]  # If there are no mappings, we still need to return a row with 0 values
            )
        ).subquery()
        surveyor_mappings_query = select(
            Values(
                column("enumerator_uid", Integer),
                column("supervisor_uid", Integer),
                name="mappings",
            ).data(
                [
                    (mapping["enumerator_uid"], mapping["supervisor_uid"])
                    for mapping in surveyor_mappings
                ]
                if len(surveyor_mappings) > 0
                else [
                    (0, 0)
                ]  # If there are no mappings, we still need to return a row with 0 values
            )
        ).subquery()

        # Get the child supervisors for the current logged in user
        is_survey_admin = check_if_survey_admin(user_uid, survey_uid)
        child_users_with_supervisors_query = build_child_users_with_supervisors_query(
            user_uid, survey_uid, target_mapping.bottom_level_role_uid, is_survey_admin
        )

    # Run database-backed validations on the assignment inputs
    dropout_enumerator_uids = []
    not_found_enumerator_uids = []
    not_found_target_uids = []
    unassignable_target_uids = []
    not_mapped_target_uids = []
    incorrect_mapping_target_uids = []

    for assignment in assignments:
        if assignment["enumerator_uid"] is not None:
            enumerator_result = (
                db.session.query(Enumerator, SurveyorForm)
                .join(
                    SurveyorForm,
                    Enumerator.enumerator_uid == SurveyorForm.enumerator_uid,
                )
                .filter(
                    Enumerator.enumerator_uid == assignment["enumerator_uid"],
                    SurveyorForm.form_uid == form_uid,
                )
                .first()
            )
            if enumerator_result is None:
                not_found_enumerator_uids.append(assignment["enumerator_uid"])
            elif enumerator_result[1].status == "Dropout":
                dropout_enumerator_uids.append(assignment["enumerator_uid"])

        target_result = (
            db.session.query(Target, TargetStatus)
            .outerjoin(TargetStatus, Target.target_uid == TargetStatus.target_uid)
            .filter(
                Target.target_uid == assignment["target_uid"],
                Target.form_uid == form_uid,
            )
            .first()
        )
        if target_result is None:
            not_found_target_uids.append(assignment["target_uid"])
        elif (
            len(target_result) == 2
            and target_result[1] is not None
            and getattr(target_result[1], "target_assignable", True) is not True
        ):
            unassignable_target_uids.append(assignment["target_uid"])

        if validate_mapping:
            target_supervisor_uid = (
                db.session.query(target_mappings_query.c.supervisor_uid)
                .filter(target_mappings_query.c.target_uid == assignment["target_uid"])
                .first()
            )
            if target_supervisor_uid is not None:
                # Check if current user is eligible to assign the target
                supervisors = (
                    db.session.query(
                        child_users_with_supervisors_query.c.user_uid,
                        child_users_with_supervisors_query.c.supervisors,
                    )
                    .filter(
                        child_users_with_supervisors_query.c.user_uid
                        == target_supervisor_uid.supervisor_uid
                    )
                    .first()
                )

                if supervisors is None:
                    not_mapped_target_uids.append(assignment["target_uid"])

            if assignment["enumerator_uid"] is not None:
                # Check if the target and enumerator are mapped to the same supervisor
                enumerator_supervisor_uid = (
                    db.session.query(surveyor_mappings_query.c.supervisor_uid)
                    .filter(
                        surveyor_mappings_query.c.enumerator_uid
                        == assignment["enumerator_uid"]
                    )
                    .first()
                )

                if target_supervisor_uid is None or enumerator_supervisor_uid is None:
                    incorrect_mapping_target_uids.append(assignment["target_uid"])
                elif (
                    target_supervisor_uid.supervisor_uid
                    != enumerator_supervisor_uid.supervisor_uid
                ):
                    incorrect_mapping_target_uids.append(assignment["target_uid"])

    if len(dropout_enumerator_uids) > 0:
        enumerator_ids = (
            db.session.query(Enumerator.enumerator_id)
            .filter(Enumerator.enumerator_uid.in_(dropout_enumerator_uids))
            .all()
        )
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "message": f"The following enumerator ID's have status 'Dropout' and are ineligible for assignment: {', '.join(str(enumerator_id.enumerator_id) for enumerator_id in enumerator_ids)}",
                        "dropout_enumerator_uids": dropout_enumerator_uids,
                    },
                }
            ),
            422,
        )

    if len(unassignable_target_uids) > 0:
        target_ids = (
            db.session.query(Target.target_id)
            .filter(Target.target_uid.in_(unassignable_target_uids))
            .all()
        )
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "message": f"The following target ID's are not assignable for this form (most likely because they are complete): {', '.join(str(target_id.target_id) for target_id in target_ids)}",
                        "unassignable_target_uids": unassignable_target_uids,
                    },
                }
            ),
            422,
        )

    if len(not_found_enumerator_uids) > 0:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "message": f"Some of the enumerator ID's provided were not found for this form. Kindly refresh and try again.",
                        "not_found_enumerator_uids": not_found_enumerator_uids,
                    },
                }
            ),
            404,
        )

    if len(not_found_target_uids) > 0:
        return (
            jsonify(
                {
                    "success": False,
                    "errors": {
                        "message": f"Some of the target ID's provided were not found for this form. Kindly refresh and try again.",
                        "not_found_target_uids": not_found_target_uids,
                    },
                }
            ),
            404,
        )

    if validate_mapping:
        if len(incorrect_mapping_target_uids) > 0:
            target_ids = (
                db.session.query(Target.target_id)
                .filter(Target.target_uid.in_(incorrect_mapping_target_uids))
                .all()
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": {
                            "message": f"The following target ID's are assigned to enumerators mapped to a different supervisor: {', '.join(str(target_id.target_id) for target_id in target_ids)}. Please ensure that the target and assigned enumerator are mapped to the same supervisor.",
                            "incorrect_mapping_target_uids": incorrect_mapping_target_uids,
                        },
                    }
                ),
                422,
            )

        if len(not_mapped_target_uids) > 0:
            target_ids = (
                db.session.query(Target.target_id)
                .filter(Target.target_uid.in_(not_mapped_target_uids))
                .all()
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": {
                            "message": f"The following target ID's are not assignable by the current user: {', '.join(str(target_id.target_id) for target_id in target_ids)}. Kindly refresh and try again.",
                            "not_mapped_target_uids": not_mapped_target_uids,
                        },
                    }
                ),
                422,
            )

    re_assignments_count = 0
    new_assignments_count = 0
    no_changes_count = 0

    for assignment in assignments:
        # query reassignments
        assignment_res = (
            db.session.query(SurveyorAssignment)
            .filter(
                SurveyorAssignment.target_uid == assignment["target_uid"],
            )
            .first()
        )

        if assignment_res is None:
            # update new_assignments - no record was found for the target
            new_assignments_count += 1
        elif assignment_res.enumerator_uid == assignment["enumerator_uid"]:
            # update no_changes - the enumerator_uid has not changed for the target found
            no_changes_count += 1
        else:
            # update re_assignment - the enumerator_uid has changed
            re_assignments_count += 1

        if assignment["enumerator_uid"] is not None:
            # do upsert
            statement = (
                pg_insert(SurveyorAssignment)
                .values(
                    target_uid=assignment["target_uid"],
                    enumerator_uid=assignment["enumerator_uid"],
                    user_uid=current_user.user_uid,
                )
                .on_conflict_do_update(
                    constraint="pk_surveyor_assignments",
                    set_={
                        "enumerator_uid": assignment["enumerator_uid"],
                        "user_uid": current_user.user_uid,
                    },
                )
            )

            db.session.execute(statement)
        else:
            db.session.query(SurveyorAssignment).filter(
                SurveyorAssignment.target_uid == assignment["target_uid"]
            ).update(
                {
                    SurveyorAssignment.user_uid: current_user.user_uid,
                    SurveyorAssignment.to_delete: 1,
                },
                synchronize_session=False,
            )

            db.session.query(SurveyorAssignment).filter(
                SurveyorAssignment.target_uid == assignment["target_uid"]
            ).delete()

    response_data = {
        "re_assignments_count": re_assignments_count,
        "new_assignments_count": new_assignments_count,
        "no_changes_count": no_changes_count,
        "assignments_count": len(assignments),
    }

    # Get the next assignment email schedule and add it to the response
    email_schedule = get_next_assignment_email_schedule(form_uid)

    if email_schedule:
        response_data["email_schedule"] = email_schedule

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify(message="Success", data=response_data), 200


@assignments_bp.route("/schedule-email", methods=["POST"])
@logged_in_active_user_required
@validate_payload(AssignmentsEmailValidator)
@custom_permissions_required("WRITE Assignments", "body", "form_uid")
def schedule_assignments_email(validated_payload):
    """Function to schedule assignment emails"""

    form_uid = validated_payload.form_uid.data

    # Find the assignments email_config_uid using the form_uid - if none create one

    email_config = EmailConfig.query.filter(
        func.lower(EmailConfig.config_name) == "assignments",
        EmailConfig.form_uid == form_uid,
    ).first()

    if email_config is None:
        try:
            email_config = EmailConfig(
                config_name="assignments",
                form_uid=form_uid,
                email_source="SurveyStream Data",
            )
            db.session.add(email_config)
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            email_config = EmailConfig.query.filter(
                func.lower(EmailConfig.config_name) == "assignments", form_uid=form_uid
            ).first()

    time_str = validated_payload.time.data
    time_obj = datetime.strptime(time_str, "%H:%M").time()

    new_trigger = ManualEmailTrigger(
        email_config_uid=email_config.email_config_uid,
        date=validated_payload.date.data,
        time=time_obj,
        recipients=validated_payload.recipients.data,
        status=validated_payload.status.data,
    )

    try:
        db.session.add(new_trigger)
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return (
        jsonify(
            {"message": "Manual email trigger created successfully", "success": True}
        ),
        201,
    )


@assignments_bp.route("", methods=["POST"])
@logged_in_active_user_required
@validate_query_params(AssignmentsQueryParamValidator)
@validate_payload(AssignmentsFileUploadValidator)
@custom_permissions_required("WRITE Assignments Upload", "query", "form_uid")
def upload_assignments(validated_query_params, validated_payload):
    """
    Method to validate the uploaded assignments file and save it to the database
    """

    form_uid = validated_query_params.form_uid.data
    user_uid = current_user.user_uid

    # Get the survey UID from the form UID
    form = Form.query.filter_by(form_uid=form_uid).first()

    if form is None:
        return (
            jsonify(
                message=f"The form 'form_uid={form_uid}' could not be found. Cannot upload assignments for an undefined form."
            ),
            404,
        )

    survey_uid = form.survey_uid

    try:
        column_mapping = AssignmentsColumnMapping(
            validated_payload.column_mapping.data,
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

    # Create an AssignmentsUpload object from the uploaded file
    try:
        assignments_upload = AssignmentsUpload(
            csv_string=base64.b64decode(
                validated_payload.file.data, validate=True
            ).decode("utf-8"),
            column_mapping=column_mapping,
            survey_uid=survey_uid,
            form_uid=form_uid,
            user_uid=user_uid,
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

    # Validate the assignments data
    try:
        assignments_upload.validate_records(
            column_mapping,
            validated_payload.mode.data,
            validated_payload.validate_mapping.data,
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
    except InvalidAssignmentRecordsError as e:
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
        response_data = assignments_upload.save_records(
            column_mapping,
            validated_payload.mode.data,
        )

    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    # Get the next assignment email schedule if present and add it to the response
    email_schedule = get_next_assignment_email_schedule(form_uid)
    if email_schedule:
        response_data["email_schedule"] = email_schedule

    return jsonify(message="Success", data=response_data), 200
