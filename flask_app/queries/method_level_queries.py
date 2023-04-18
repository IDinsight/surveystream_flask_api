from flask_app.database import db
from flask_app.models.data_models import (
    ParentForm,
    UserHierarchy,
    LocationHierarchy,
    Location,
    SamplingFrameGeoLevel,
    Survey,
    User,
    Role,
    Enumerator,
    Target,
    LocationUserMapping,
    LocationSurveyorMapping,
    SurveyorForm,
    SurveyorAssignment,
    TargetStatus,
)
from flask_app.queries.helper_queries import (
    build_user_hierarchy_query,
    build_prime_locations_with_location_hierarchy_subquery,
    build_geo_level_n_locations_with_location_hierarchy_subquery,
    build_prime_locations_with_child_supervisors_subquery,
    build_survey_query,
    build_surveyor_forms_array_subquery,
    build_surveyor_assigned_and_complete_targets_subquery,
    build_surveyor_pending_and_complete_targets_subquery,
)
from flask_app.utils import get_core_user_status


def build_get_enumerators_query(user_uid, form_uid):
    """
    Build query for the get enumerators method
    """

    #########################################################
    # Assemble helper queries and values for the main query
    #########################################################

    survey_query = build_survey_query(form_uid)

    # Core users (Role.level == 0) need to be handled differently in the
    # user hierarchy queries because they are not listed as anyone's parent user
    is_core_user = get_core_user_status(user_uid, survey_query)

    # This will be used to filter the result based on the user's subordinates
    user_hierarchy_query = build_user_hierarchy_query(
        user_uid, survey_query, is_core_user
    )

    # This will be used to join in the locations hierarchy for each surveyor
    prime_locations_with_location_hierarchy_subquery = (
        build_prime_locations_with_location_hierarchy_subquery(survey_query)
    )

    # This will be used to join in the user's subordinate supervisors for each surveyor
    prime_locations_with_child_supervisors_subquery = (
        build_prime_locations_with_child_supervisors_subquery(
            user_uid, survey_query, is_core_user
        )
    )

    # This will be used to join in each surveyor's productivity info
    # for each form in the survey
    surveyor_forms_array_subquery = build_surveyor_forms_array_subquery(survey_query)

    # This will be used to join in each surveyor's survey-level productivity info
    surveyor_assigned_and_complete_targets_subquery = (
        build_surveyor_assigned_and_complete_targets_subquery(survey_query)
    )

    #########################################################
    # Build the main query
    #########################################################

    result = (
        db.session.query(
            Enumerator,
            SurveyorForm,
            prime_locations_with_location_hierarchy_subquery.c.locations,
            prime_locations_with_child_supervisors_subquery.c.supervisors,
            surveyor_forms_array_subquery.c.forms,
            surveyor_assigned_and_complete_targets_subquery.c.form_productivity,
        )
        .join(SurveyorForm, Enumerator.enumerator_uid == SurveyorForm.enumerator_uid)
        .join(
            LocationSurveyorMapping,
            (SurveyorForm.enumerator_uid == LocationSurveyorMapping.enumerator_uid)
            & (SurveyorForm.form_uid == LocationSurveyorMapping.form_uid),
        )
        .join(
            LocationUserMapping,
            LocationSurveyorMapping.location_uid == LocationUserMapping.location_uid,
        )
        .join(
            user_hierarchy_query,
            (LocationUserMapping.user_uid == user_hierarchy_query.c.user_uid)
            & (LocationUserMapping.survey_uid == user_hierarchy_query.c.survey_uid),
        )
        .join(
            prime_locations_with_location_hierarchy_subquery,
            LocationSurveyorMapping.location_uid
            == prime_locations_with_location_hierarchy_subquery.c.location_uid,
            isouter=True,
        )
        .join(
            prime_locations_with_child_supervisors_subquery,
            LocationSurveyorMapping.location_uid
            == prime_locations_with_child_supervisors_subquery.c.location_uid,
            isouter=True,
        )
        .join(
            surveyor_forms_array_subquery,
            Enumerator.enumerator_uid == surveyor_forms_array_subquery.c.enumerator_uid,
            isouter=True,
        )
        .join(
            surveyor_assigned_and_complete_targets_subquery,
            Enumerator.enumerator_uid
            == surveyor_assigned_and_complete_targets_subquery.c.enumerator_uid,
            isouter=True,
        )
        .filter(SurveyorForm.form_uid == form_uid)
        .filter(LocationUserMapping.survey_uid.in_(survey_query.subquery()))
    )

    return result


def build_get_targets_query(user_uid, form_uid):
    """
    Build query for the get targets method
    """

    #########################################################
    # Assemble helper queries and values for the main query
    #########################################################

    survey_query = build_survey_query(form_uid)

    # Core users (Role.level == 0) need to be handled differently in the
    # user hierarchy queries because they are not listed as anyone's parent user
    is_core_user = get_core_user_status(user_uid, survey_query)

    # This will be used to filter the result based on the user's subordinates
    user_hierarchy_query = build_user_hierarchy_query(
        user_uid, survey_query, is_core_user
    )

    # This will be used to join in the user's subordinate supervisors for each target
    prime_locations_with_child_supervisors_subquery = (
        build_prime_locations_with_child_supervisors_subquery(
            user_uid, survey_query, is_core_user
        )
    )

    # This will be used to join in the locations hierarchy for each target
    geo_level_n_locations_with_location_hierarchy_subquery = (
        build_geo_level_n_locations_with_location_hierarchy_subquery(survey_query)
    )

    result = (
        db.session.query(
            Target,
            TargetStatus,
            prime_locations_with_child_supervisors_subquery.c.supervisors,
            geo_level_n_locations_with_location_hierarchy_subquery.c.locations,
        )
        .join(
            LocationUserMapping,
            Target.prime_location_uid == LocationUserMapping.location_uid,
        )
        .join(
            user_hierarchy_query,
            (LocationUserMapping.user_uid == user_hierarchy_query.c.user_uid)
            & (LocationUserMapping.survey_uid == user_hierarchy_query.c.survey_uid),
        )
        .join(
            prime_locations_with_child_supervisors_subquery,
            Target.prime_location_uid
            == prime_locations_with_child_supervisors_subquery.c.location_uid,
            isouter=True,
        )
        .join(
            geo_level_n_locations_with_location_hierarchy_subquery,
            Target.geo_level_n_location_uid
            == geo_level_n_locations_with_location_hierarchy_subquery.c.location_uid,
            isouter=True,
        )
        .join(TargetStatus, Target.target_uid == TargetStatus.target_uid, isouter=True)
        .filter(LocationUserMapping.survey_uid.in_(survey_query.subquery()))
        .filter(Target.form_uid == form_uid, Target.active.is_(True))
    )

    return result


def build_get_assignments_query(user_uid, form_uid):
    """
    Build assignments query for the get assignments method
    """

    #########################################################
    # Assemble helper queries and values for the main query
    #########################################################

    survey_query = build_survey_query(form_uid)

    # Core users (Role.level == 0) need to be handled differently in the
    # user hierarchy queries because they are not listed as anyone's parent user
    is_core_user = get_core_user_status(user_uid, survey_query)

    # This will be used to filter the result based on the user's subordinates
    user_hierarchy_query = build_user_hierarchy_query(
        user_uid, survey_query, is_core_user
    )

    # This will be used to join in the user's subordinate supervisors for each target
    prime_locations_with_child_supervisors_subquery = (
        build_prime_locations_with_child_supervisors_subquery(
            user_uid, survey_query, is_core_user
        )
    )

    # This will be used to join in the locations hierarchy for each target
    geo_level_n_locations_with_location_hierarchy_subquery = (
        build_geo_level_n_locations_with_location_hierarchy_subquery(survey_query)
    )

    result = (
        db.session.query(
            Target,
            TargetStatus,
            Enumerator,
            geo_level_n_locations_with_location_hierarchy_subquery.c.locations,
            prime_locations_with_child_supervisors_subquery.c.supervisors,
        )
        .join(
            LocationUserMapping,
            Target.prime_location_uid == LocationUserMapping.location_uid,
        )
        .join(
            user_hierarchy_query,
            (LocationUserMapping.user_uid == user_hierarchy_query.c.user_uid)
            & (LocationUserMapping.survey_uid == user_hierarchy_query.c.survey_uid),
        )
        .join(
            SurveyorAssignment,
            Target.target_uid == SurveyorAssignment.target_uid,
            isouter=True,
        )
        .join(
            Enumerator,
            SurveyorAssignment.enumerator_uid == Enumerator.enumerator_uid,
            isouter=True,
        )
        .join(TargetStatus, Target.target_uid == TargetStatus.target_uid, isouter=True)
        .join(
            geo_level_n_locations_with_location_hierarchy_subquery,
            Target.geo_level_n_location_uid
            == geo_level_n_locations_with_location_hierarchy_subquery.c.location_uid,
            isouter=True,
        )
        .join(
            prime_locations_with_child_supervisors_subquery,
            Target.prime_location_uid
            == prime_locations_with_child_supervisors_subquery.c.location_uid,
            isouter=True,
        )
        .filter(LocationUserMapping.survey_uid.in_(survey_query.subquery()))
        .filter(Target.form_uid == form_uid, Target.active.is_(True))
    )

    return result


def build_get_assignment_surveyors_query(user_uid, form_uid):
    """
    Build surveyors query for the get assignments method
    """

    #########################################################
    # Assemble helper queries and values for the main query
    #########################################################

    survey_query = build_survey_query(form_uid)

    # Core users (Role.level == 0) need to be handled differently in the
    # user hierarchy queries because they are not listed as anyone's parent user
    is_core_user = get_core_user_status(user_uid, survey_query)

    # This will be used to filter the result based on the user's subordinates
    user_hierarchy_query = build_user_hierarchy_query(
        user_uid, survey_query, is_core_user
    )

    # This will be used to join in the locations hierarchy for each surveyor
    prime_locations_with_location_hierarchy_subquery = (
        build_prime_locations_with_location_hierarchy_subquery(survey_query)
    )

    # This will be used to join in each surveyor's pending targets for each
    # form on the survey
    surveyor_pending_and_complete_targets_subquery = (
        build_surveyor_pending_and_complete_targets_subquery(survey_query)
    )

    result = (
        db.session.query(
            Enumerator,
            SurveyorForm,
            prime_locations_with_location_hierarchy_subquery.c.locations,
            surveyor_pending_and_complete_targets_subquery.c.form_productivity,
            surveyor_pending_and_complete_targets_subquery.c.total_pending_targets,
            surveyor_pending_and_complete_targets_subquery.c.total_complete_targets,
        )
        .join(SurveyorForm, Enumerator.enumerator_uid == SurveyorForm.enumerator_uid)
        .join(
            LocationSurveyorMapping,
            (SurveyorForm.enumerator_uid == LocationSurveyorMapping.enumerator_uid)
            & (SurveyorForm.form_uid == LocationSurveyorMapping.form_uid),
        )
        .join(
            LocationUserMapping,
            LocationSurveyorMapping.location_uid == LocationUserMapping.location_uid,
        )
        .join(
            user_hierarchy_query,
            (LocationUserMapping.user_uid == user_hierarchy_query.c.user_uid)
            & (LocationUserMapping.survey_uid == user_hierarchy_query.c.survey_uid),
        )
        .join(
            prime_locations_with_location_hierarchy_subquery,
            LocationSurveyorMapping.location_uid
            == prime_locations_with_location_hierarchy_subquery.c.location_uid,
            isouter=True,
        )
        .join(
            surveyor_pending_and_complete_targets_subquery,
            Enumerator.enumerator_uid
            == surveyor_pending_and_complete_targets_subquery.c.enumerator_uid,
            isouter=True,
        )
        .filter(LocationUserMapping.survey_uid.in_(survey_query.subquery()))
        .filter(
            SurveyorForm.form_uid == form_uid,
            SurveyorForm.status.in_(["Active", "Temp. Inactive"]),
        )
    )

    return result
