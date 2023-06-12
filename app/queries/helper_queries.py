from app import db
from app.models.data_models import (
    UserHierarchy,
    LocationHierarchy,
    Location,
    SamplingFrameGeoLevel,
    Survey,
    User,
    Role,
    LocationUserMapping,
    SurveyorForm,
    SurveyorAssignment,
    TargetStatus,
    Target,
)
from app.blueprints.forms.models import (
    ParentForm
)
from sqlalchemy.sql.functions import func, max
from sqlalchemy import cast, or_


def build_location_hierarchy_query(survey_query):
    """
    Build a query that returns the locations for the current survey
    joined to an array column that contains the location's own and parent
    location information

    This will be used as an input to other queries that need specific subsets
    of the location records with their location hierarchy information
    """

    # Assemble the first part of the recursive query
    # This returns all the top level locations for the survey and
    # a JSON object that will hold the accumulated location information
    top_query = (
        db.session.query(
            Location.location_uid.label("location_uid"),
            SamplingFrameGeoLevel.level.label("level"),
            func.jsonb_build_array(
                func.jsonb_build_object(
                    "level",
                    SamplingFrameGeoLevel.level,
                    "geo_level_name",
                    SamplingFrameGeoLevel.geo_level_name,
                    "location_name",
                    Location.location_name,
                    "location_id",
                    Location.location_id,
                )
            ).label("locations"),
        )
        .join(
            SamplingFrameGeoLevel,
            Location.geo_level_uid == SamplingFrameGeoLevel.geo_level_uid,
        )
        .join(
            Survey,
            SamplingFrameGeoLevel.sampling_frame_uid == Survey.sampling_frame_uid,
        )
        .filter(SamplingFrameGeoLevel.level == 1)
        .filter(Survey.survey_uid.in_(survey_query))
        .cte("location_hierarchy_cte", recursive=True)
    )

    # Assemble the second part of the recursive query
    # This will descend down the location hierarchy tree and accumulate
    # the location information in the locations JSON object
    bottom_query = (
        db.session.query(
            LocationHierarchy.location_uid.label("location_uid"),
            SamplingFrameGeoLevel.level.label("level"),
            top_query.c.locations.concat(
                func.jsonb_build_object(
                    "level",
                    SamplingFrameGeoLevel.level,
                    "geo_level_name",
                    SamplingFrameGeoLevel.geo_level_name,
                    "location_name",
                    Location.location_name,
                    "location_id",
                    Location.location_id,
                )
            ).label("locations"),
        )
        .join(Location, LocationHierarchy.location_uid == Location.location_uid)
        .join(
            SamplingFrameGeoLevel,
            Location.geo_level_uid == SamplingFrameGeoLevel.geo_level_uid,
        )
        .join(
            top_query, LocationHierarchy.parent_location_uid == top_query.c.location_uid
        )
    )

    location_hierarchy_query = top_query.union(bottom_query)

    return location_hierarchy_query


def build_prime_locations_with_location_hierarchy_subquery(survey_query):
    """
    Build a subquery that returns the prime geo level locations for the
    current survey joined to an array column that contains the location's
    own and parent region information

    This will be used to join with the enumerators data on prime location uid
    to get the enumerators' working locations
    """

    location_hierarchy_query = build_location_hierarchy_query(survey_query)

    # Get the prime geo level locations for the current survey
    # and join in the ancestors array from the recursive query result
    prime_locations_with_location_hierarchy_subquery = (
        db.session.query(
            Location.location_uid.label("location_uid"),
            Location.location_name.label("location_name"),
            location_hierarchy_query.c.locations.label("locations"),
        )
        .join(
            Survey,
            (Location.sampling_frame_uid == Survey.sampling_frame_uid)
            & (Location.geo_level_uid == Survey.prime_geo_level_uid),
        )
        .join(
            location_hierarchy_query,
            Location.location_uid == location_hierarchy_query.c.location_uid,
            isouter=True,
        )
        .filter(Survey.survey_uid.in_(survey_query))
        .subquery()
    )

    return prime_locations_with_location_hierarchy_subquery


def build_geo_level_n_locations_with_location_hierarchy_subquery(survey_query):
    """
    Build a subquery that returns the geo level n locations for the
    current survey joined to a JSON column that contains the location's
    own and parent location information

    This will be used to join with the targets data on geo level n location
    """

    location_hierarchy_query = build_location_hierarchy_query(survey_query)

    geo_level_n_subquery = (
        db.session.query(max(SamplingFrameGeoLevel.level).label("level_n"))
        .join(
            Survey,
            SamplingFrameGeoLevel.sampling_frame_uid == Survey.sampling_frame_uid,
        )
        .filter(Survey.survey_uid.in_(survey_query))
        .subquery()
    )

    # Get the geo level n locations for the current survey
    # and join in the locations array from the recursive query result
    geo_level_n_locations_with_location_hierarchy_subquery = (
        db.session.query(
            location_hierarchy_query.c.location_uid.label("location_uid"),
            location_hierarchy_query.c.locations.label("locations"),
        )
        .filter(location_hierarchy_query.c.level.in_(geo_level_n_subquery))
        .subquery()
    )

    return geo_level_n_locations_with_location_hierarchy_subquery


def build_user_hierarchy_query(user_uid, survey_query, is_core_user=False):
    """
    Build a subquery that returns the user hierarchy records of the given user
    and all their child users
    The survey_query param is a .query() object that contains the list of survey_uid's
    that we want to filter the user_hierarchy table on
    """

    if not is_core_user:
        top_query = (
            db.session.query(UserHierarchy)
            .filter(UserHierarchy.user_uid == user_uid)
            .filter(UserHierarchy.survey_uid.in_(survey_query))
            .cte("user_hierarchy_cte", recursive=True)
        )

        bottom_query = (
            db.session.query(UserHierarchy)
            .join(top_query, UserHierarchy.parent_user_uid == top_query.c.user_uid)
            .filter(UserHierarchy.survey_uid.in_(survey_query))
        )

        recursive_query = top_query.union(bottom_query)

        return recursive_query

    else:
        query = (
            db.session.query(UserHierarchy)
            .filter(UserHierarchy.survey_uid.in_(survey_query))
            .subquery()
        )

        return query


def build_prime_locations_with_child_supervisors_subquery(
    user_uid, survey_query, is_core_user=False
):
    """
    Build a subquery that returns the prime locations for the given user joined to a
    JSON object containing the user's child supervisors associated with that
    prime location

    The survey_query param is a .query() object that contains the list of survey_uid's
    that we want to filter the user_hierarchy table on

    This will be used to join with the targets and enumerators to get their supervisor
    information (restricted to the supervisors underneath the current user)
    """

    if not is_core_user:
        # Assemble the first part of the recursive query
        # This returns the current user's user hierarchy records
        # for the given survey

        top_query = (
            db.session.query(
                UserHierarchy.user_uid.label("user_uid"),
                func.jsonb_build_array().label("supervisors"),
            )
            .filter(UserHierarchy.user_uid == user_uid)
            .filter(UserHierarchy.survey_uid.in_(survey_query))
            .cte("supervisor_hierarchy_cte", recursive=True)
        )
    else:
        # Assemble the first part of the recursive query
        # This returns the level 1 users' user hierarchy records
        # for the given survey
        top_query = (
            db.session.query(
                UserHierarchy.user_uid.label("user_uid"),
                func.jsonb_build_array(
                    func.jsonb_build_object(
                        "role_name",
                        Role.role_name,
                        "level",
                        Role.level,
                        "supervisor_name",
                        func.coalesce(User.first_name.concat(" "), "")
                        .concat(func.coalesce(User.middle_name.concat(" "), ""))
                        .concat(func.coalesce(User.last_name, "")),
                        "supervisor_email",
                        User.email,
                    )
                ).label("supervisors"),
            )
            .join(User, UserHierarchy.user_uid == User.user_uid)
            .join(Role, UserHierarchy.role_uid == Role.role_uid)
            .filter(UserHierarchy.survey_uid.in_(survey_query))
            .filter(Role.level == 1)
            .cte("supervisor_hierarchy_cte", recursive=True)
        )

    # Assemble the second part of the recursive query
    # This will descend down the user hierarchy tree and accumulate
    # the child supervisor names in the supervisors array
    bottom_query = (
        db.session.query(
            UserHierarchy.user_uid.label("user_uid"),
            top_query.c.supervisors.concat(
                func.jsonb_build_object(
                    "role_name",
                    Role.role_name,
                    "level",
                    Role.level,
                    "supervisor_name",
                    func.coalesce(User.first_name.concat(" "), "")
                    .concat(func.coalesce(User.middle_name.concat(" "), ""))
                    .concat(func.coalesce(User.last_name, "")),
                    "supervisor_email",
                    User.email,
                )
            ),
        )
        .join(User, UserHierarchy.user_uid == User.user_uid)
        .join(Role, UserHierarchy.role_uid == Role.role_uid)
        .join(top_query, UserHierarchy.parent_user_uid == top_query.c.user_uid)
        .filter(UserHierarchy.survey_uid.in_(survey_query))
    )

    recursive_query = top_query.union(bottom_query)

    # Join the supervisor JSON field to the prime locations for the survey
    prime_locations_with_child_supervisors_subquery = (
        db.session.query(
            LocationUserMapping.location_uid.label("location_uid"),
            recursive_query.c.supervisors.label("supervisors"),
        )
        .join(
            recursive_query, LocationUserMapping.user_uid == recursive_query.c.user_uid
        )
        .filter(LocationUserMapping.survey_uid.in_(survey_query))
    ).subquery()

    return prime_locations_with_child_supervisors_subquery


def build_survey_query(form_uid):
    """
    Build a query that filters the parent_forms table down to the current form
    for purposes of getting the form's survey_uid
    """

    return db.session.query(ParentForm.survey_uid).filter(
        ParentForm.form_uid == form_uid
    )


def build_surveyor_forms_array_subquery(survey_query):
    """
    Build a subquery that returns data at the surveyor level
    with an array that contains each of the sureyor's forms
    for the given survey
    """

    surveyor_forms_array_subquery = (
        db.session.query(
            SurveyorForm.enumerator_uid.label("enumerator_uid"),
            func.array_agg(ParentForm.form_name).label("forms"),
        )
        .join(ParentForm, SurveyorForm.form_uid == ParentForm.form_uid)
        .filter(ParentForm.survey_uid.in_(survey_query))
        .group_by(SurveyorForm.enumerator_uid)
        .subquery()
    )

    return surveyor_forms_array_subquery


def build_surveyor_assigned_and_complete_targets_subquery(survey_query):

    """
    Build a subquery that returns data at the surveyor level
    with an array that contains the total targets assigned
    and total targets complete for each of the surveyors' forms
    """

    # Create a subquery at the enumerator-form level with assigned target counts
    assigned_target_count_subquery = (
        db.session.query(
            SurveyorForm.enumerator_uid,
            SurveyorForm.form_uid,
            func.count(SurveyorAssignment.target_uid).label("total_assigned"),
        )
        .join(ParentForm, SurveyorForm.form_uid == ParentForm.form_uid)
        .join(
            SurveyorAssignment,
            SurveyorForm.enumerator_uid == SurveyorAssignment.enumerator_uid,
        )
        .join(
            Target,
            (SurveyorForm.form_uid == Target.form_uid)
            & (SurveyorAssignment.target_uid == Target.target_uid),
        )
        .filter(ParentForm.survey_uid.in_(survey_query))
        .group_by(SurveyorForm.enumerator_uid, SurveyorForm.form_uid)
        .subquery()
    )

    # Create a subquery at the enumerator-form level with complete target counts
    completed_target_count_subquery = (
        db.session.query(
            SurveyorForm.enumerator_uid,
            SurveyorForm.form_uid,
            func.count(TargetStatus.target_assignable).label("total_complete"),
        )
        .join(ParentForm, SurveyorForm.form_uid == ParentForm.form_uid)
        .join(
            SurveyorAssignment,
            SurveyorForm.enumerator_uid == SurveyorAssignment.enumerator_uid,
        )
        .join(
            Target,
            (SurveyorForm.form_uid == Target.form_uid)
            & (SurveyorAssignment.target_uid == Target.target_uid),
        )
        .join(
            TargetStatus,
            SurveyorAssignment.target_uid == TargetStatus.target_uid,
        )
        .filter(ParentForm.survey_uid.in_(survey_query))
        .filter(TargetStatus.target_assignable.is_(False))
        .group_by(SurveyorForm.enumerator_uid, SurveyorForm.form_uid)
        .subquery()
    )

    # Create the final subquery at the enumerator level
    surveyor_assigned_and_complete_targets_subquery = (
        db.session.query(
            SurveyorForm.enumerator_uid,
            func.array_agg(
                func.jsonb_build_object(
                    "form_name",
                    ParentForm.form_name,
                    "scto_form_id",
                    ParentForm.scto_form_id,
                    "total_complete",
                    func.coalesce(completed_target_count_subquery.c.total_complete, 0),
                    "total_assigned",
                    func.coalesce(assigned_target_count_subquery.c.total_assigned, 0),
                )
            ).label("form_productivity"),
        )
        .join(ParentForm, SurveyorForm.form_uid == ParentForm.form_uid)
        .join(
            completed_target_count_subquery,
            (
                SurveyorForm.enumerator_uid
                == completed_target_count_subquery.c.enumerator_uid
            )
            & (SurveyorForm.form_uid == completed_target_count_subquery.c.form_uid),
            isouter=True,
        )
        .join(
            assigned_target_count_subquery,
            (
                SurveyorForm.enumerator_uid
                == assigned_target_count_subquery.c.enumerator_uid
            )
            & (SurveyorForm.form_uid == assigned_target_count_subquery.c.form_uid),
            isouter=True,
        )
        .filter(ParentForm.survey_uid.in_(survey_query))
        .group_by(SurveyorForm.enumerator_uid)
        .subquery()
    )

    return surveyor_assigned_and_complete_targets_subquery


def build_surveyor_pending_and_complete_targets_subquery(survey_query):

    """
    Build a subquery that returns data at the surveyor level
    with an array that contains the total pending targets
    for each of the surveyors forms in the given survey
    """

    # Create a subquery at the enumerator-form level with pending target counts
    pending_target_count_subquery = (
        db.session.query(
            SurveyorForm.enumerator_uid,
            SurveyorForm.form_uid,
            func.count(TargetStatus.target_assignable).label("total_pending"),
        )
        .join(ParentForm, SurveyorForm.form_uid == ParentForm.form_uid)
        .join(
            SurveyorAssignment,
            SurveyorForm.enumerator_uid == SurveyorAssignment.enumerator_uid,
        )
        .join(
            Target,
            (SurveyorForm.form_uid == Target.form_uid)
            & (SurveyorAssignment.target_uid == Target.target_uid),
        )
        .join(
            TargetStatus,
            SurveyorAssignment.target_uid == TargetStatus.target_uid,
            isouter=True,
        )
        .filter(ParentForm.survey_uid.in_(survey_query))
        .filter(
            or_(
                TargetStatus.target_assignable.is_(True),
                TargetStatus.target_assignable.is_(None),
            )
        )
        .group_by(SurveyorForm.enumerator_uid, SurveyorForm.form_uid)
        .subquery()
    )

    # Create a subquery at the enumerator-form level with complete target counts
    completed_target_count_subquery = (
        db.session.query(
            SurveyorForm.enumerator_uid,
            SurveyorForm.form_uid,
            func.count(TargetStatus.target_assignable).label("total_complete"),
        )
        .join(ParentForm, SurveyorForm.form_uid == ParentForm.form_uid)
        .join(
            SurveyorAssignment,
            SurveyorForm.enumerator_uid == SurveyorAssignment.enumerator_uid,
        )
        .join(
            Target,
            (SurveyorForm.form_uid == Target.form_uid)
            & (SurveyorAssignment.target_uid == Target.target_uid),
        )
        .join(
            TargetStatus,
            SurveyorAssignment.target_uid == TargetStatus.target_uid,
        )
        .filter(ParentForm.survey_uid.in_(survey_query))
        .filter(TargetStatus.target_assignable.is_(False))
        .group_by(SurveyorForm.enumerator_uid, SurveyorForm.form_uid)
        .subquery()
    )

    # Create the final subquery at the enumerator level
    surveyor_pending_and_complete_targets_subquery = (
        db.session.query(
            SurveyorForm.enumerator_uid,
            func.array_agg(
                func.jsonb_build_object(
                    "form_name",
                    ParentForm.form_name,
                    "scto_form_id",
                    ParentForm.scto_form_id,
                    "total_pending",
                    func.coalesce(pending_target_count_subquery.c.total_pending, 0),
                    "total_complete",
                    func.coalesce(completed_target_count_subquery.c.total_complete, 0),
                )
            ).label("form_productivity"),
            func.coalesce(
                cast(
                    func.sum(pending_target_count_subquery.c.total_pending),
                    db.Integer(),
                ),
                0,
            ).label("total_pending_targets"),
            func.coalesce(
                cast(
                    func.sum(completed_target_count_subquery.c.total_complete),
                    db.Integer(),
                ),
                0,
            ).label("total_complete_targets"),
        )
        .join(ParentForm, SurveyorForm.form_uid == ParentForm.form_uid)
        .join(
            pending_target_count_subquery,
            (
                SurveyorForm.enumerator_uid
                == pending_target_count_subquery.c.enumerator_uid
            )
            & (SurveyorForm.form_uid == pending_target_count_subquery.c.form_uid),
            isouter=True,
        )
        .join(
            completed_target_count_subquery,
            (
                SurveyorForm.enumerator_uid
                == completed_target_count_subquery.c.enumerator_uid
            )
            & (SurveyorForm.form_uid == completed_target_count_subquery.c.form_uid),
            isouter=True,
        )
        .filter(ParentForm.survey_uid.in_(survey_query))
        .group_by(SurveyorForm.enumerator_uid)
        .subquery()
    )

    return surveyor_pending_and_complete_targets_subquery


def build_user_level_query(user_uid, survey_query):
    """
    Build a query that gets the user hierarchy level
    of the given user on the given survey
    """

    query = (
        db.session.query(Role.level.label("level"))
        .join(UserHierarchy, Role.role_uid == UserHierarchy.role_uid)
        .filter(UserHierarchy.user_uid == user_uid)
        .filter(UserHierarchy.survey_uid.in_(survey_query))
    )

    return query
