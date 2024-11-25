from sqlalchemy import case, cast, or_
from sqlalchemy.sql.functions import func

from app import db
from app.blueprints.auth.models import User
from app.blueprints.enumerators.models import SurveyorForm, SurveyorStats
from app.blueprints.forms.models import Form
from app.blueprints.roles.models import Role, UserHierarchy
from app.blueprints.targets.models import TargetStatus

from .models import SurveyorAssignment


def build_surveyor_formwise_productivity_subquery(survey_uid):
    """
    Build a subquery at the enumerator level with assignment status counts for each form in the survey:
    total pending, total complete, total assigned

    The result will only include enumerators that have been assigned a target on the given forms
    """

    assignment_status_subquery = (
        db.session.query(
            SurveyorForm.enumerator_uid,
            SurveyorForm.form_uid,
            func.count(
                case(
                    [
                        (
                            or_(
                                TargetStatus.target_assignable.is_(True),
                                TargetStatus.target_assignable.is_(None),
                            ),
                            1,
                        )
                    ]
                )
            ).label("total_pending_targets"),
            func.count(
                case(
                    [
                        (
                            TargetStatus.target_assignable.is_(False),
                            1,
                        )
                    ]
                )
            ).label("total_completed_targets"),
            func.count(
                case(
                    [
                        (
                            or_(
                                TargetStatus.target_assignable.is_(True),
                                TargetStatus.target_assignable.is_(False),
                                TargetStatus.target_assignable.is_(None),
                            ),
                            1,
                        )
                    ]
                )
            ).label("total_assigned_targets"),
        )
        .join(
            Form,
            SurveyorForm.form_uid == Form.form_uid,
        )
        .join(
            SurveyorAssignment,
            SurveyorForm.enumerator_uid == SurveyorAssignment.enumerator_uid,
        )
        .outerjoin(
            TargetStatus, SurveyorAssignment.target_uid == TargetStatus.target_uid
        )
        .filter(Form.survey_uid == survey_uid)
        .group_by(SurveyorForm.enumerator_uid, SurveyorForm.form_uid)
        .subquery()
    )

    # Create the final subquery at the enumerator level
    surveyor_formwise_productivity_subquery = (
        db.session.query(
            SurveyorForm.enumerator_uid,
            func.jsonb_object_agg(
                Form.scto_form_id,
                func.jsonb_build_object(
                    "form_name",
                    Form.form_name,
                    "scto_form_id",
                    Form.scto_form_id,
                    "total_assigned_targets",
                    func.coalesce(
                        cast(
                            assignment_status_subquery.c.total_assigned_targets,
                            db.Integer(),
                        ),
                        0,
                    ),
                    "total_pending_targets",
                    func.coalesce(
                        cast(
                            assignment_status_subquery.c.total_pending_targets,
                            db.Integer(),
                        ),
                        0,
                    ),
                    "total_completed_targets",
                    func.coalesce(
                        cast(
                            assignment_status_subquery.c.total_completed_targets,
                            db.Integer(),
                        ),
                        0,
                    ),
                    "avg_num_submissions_per_day",
                    func.coalesce(SurveyorStats.avg_num_submissions_per_day, 0),
                    "avg_num_completed_per_day",
                    func.coalesce(SurveyorStats.avg_num_completed_per_day, 0),
                ),
            ).label("form_productivity"),
        )
        .join(Form, SurveyorForm.form_uid == Form.form_uid)
        .outerjoin(
            assignment_status_subquery,
            (SurveyorForm.enumerator_uid == assignment_status_subquery.c.enumerator_uid)
            & (SurveyorForm.form_uid == assignment_status_subquery.c.form_uid),
        )
        .outerjoin(
            SurveyorStats,
            (SurveyorForm.enumerator_uid == SurveyorStats.enumerator_uid)
            & (SurveyorForm.form_uid == SurveyorStats.form_uid),
        )
        .filter(Form.survey_uid == survey_uid)
        .group_by(SurveyorForm.enumerator_uid)
        .subquery()
    )

    return surveyor_formwise_productivity_subquery


def build_child_users_with_supervisors_query(
    user_uid,
    survey_uid,
    bottom_level_role_uid,
    user_role=None,
    is_survey_admin=False,
    is_super_admin=False,
):
    """
    Build a subquery that returns all the FSLn child supervisors for the given user
    joined to a JSON object containing the parent supervisors (in descending order)
    of the given child supervisor. Note that the current user is excluded from the
    JSON object of parent supervisors. For survey admins, the subquery will return
    all the FSLn users and their supervisors.

    This will be used to join with the targets and enumerators to get their supervisor
    information (restricted to the supervisors underneath the current user)
    """

    # Fetch all users if the user is a survey admin
    # or if user is super admin not having a specific role in the survey
    is_admin = is_survey_admin or (is_super_admin and not user_role)

    if not is_admin:
        # Assemble the first part of the recursive query
        # This returns the user uid with an empty array for the
        # user's supervisors to start the recursive query
        top_query = (
            db.session.query(
                User.user_uid,
                Role.role_uid,
                func.jsonb_build_array().label("supervisors"),
            )
            .join(
                Role,
                (Role.role_uid == func.any(User.roles))
                & (Role.survey_uid == survey_uid),
            )
            .filter(User.user_uid == user_uid)
            .cte("supervisor_hierarchy_cte", recursive=True)
        )

        # Assemble the second part of the recursive query
        # This will descend down the user hierarchy tree and accumulate
        # the child supervisor names in the supervisors array
        bottom_query = (
            db.session.query(
                UserHierarchy.user_uid,
                Role.role_uid,
                func.jsonb_build_object(
                    "role_uid",
                    Role.role_uid,
                    "role_name",
                    Role.role_name,
                    "supervisor_name",
                    func.coalesce(User.first_name.concat(" "), "")
                    .concat(func.coalesce(User.middle_name.concat(" "), ""))
                    .concat(func.coalesce(User.last_name, "")),
                    "supervisor_email",
                    User.email,
                )
                .concat(top_query.c.supervisors)
                .label("supervisors"),
            )
            .join(User, UserHierarchy.user_uid == User.user_uid)
            .join(Role, UserHierarchy.role_uid == Role.role_uid)
            .join(top_query, UserHierarchy.parent_user_uid == top_query.c.user_uid)
            .filter(UserHierarchy.survey_uid == survey_uid)
        )

        recursive_query = top_query.union(bottom_query)

        # Filter the recursive query to only include the FSLn child supervisors
        fsln_supervisors_query = (
            db.session.query(
                recursive_query.c.user_uid,
                recursive_query.c.role_uid,
                recursive_query.c.supervisors,
            )
            .filter(recursive_query.c.role_uid == bottom_level_role_uid)
            .subquery()
        )

    else:
        # Assemble the first part of the recursive query
        # This returns the FSLn users with their own detains in the supervisors array
        top_query = (
            db.session.query(
                User.user_uid,
                Role.role_uid,
                User.user_uid.label("next_user_uid"),
                Role.reporting_role_uid,
                func.jsonb_build_array(
                    func.jsonb_build_object(
                        "role_uid",
                        Role.role_uid,
                        "role_name",
                        Role.role_name,
                        "supervisor_name",
                        func.coalesce(User.first_name.concat(" "), "")
                        .concat(func.coalesce(User.middle_name.concat(" "), ""))
                        .concat(func.coalesce(User.last_name, "")),
                        "supervisor_email",
                        User.email,
                    )
                ).label("supervisors"),
            )
            .join(
                Role,
                (Role.role_uid == func.any(User.roles))
                & (Role.role_uid == bottom_level_role_uid)
                & (Role.survey_uid == survey_uid),
            )
            .cte("supervisor_hierarchy_cte", recursive=True)
        )

        # Assemble the second part of the recursive query
        # This will accumulate immediate parent supervisor names in the supervisors array
        bottom_query = (
            db.session.query(
                top_query.c.user_uid,
                Role.role_uid,
                User.user_uid.label("next_user_uid"),
                Role.reporting_role_uid,
                top_query.c.supervisors.concat(
                    func.jsonb_build_object(
                        "role_uid",
                        Role.role_uid,
                        "role_name",
                        Role.role_name,
                        "supervisor_name",
                        func.coalesce(User.first_name.concat(" "), "")
                        .concat(func.coalesce(User.middle_name.concat(" "), ""))
                        .concat(func.coalesce(User.last_name, "")),
                        "supervisor_email",
                        User.email,
                    )
                ).label("supervisors"),
            )
            .join(
                Role,
                (top_query.c.reporting_role_uid == Role.role_uid)
                & (Role.survey_uid == survey_uid),
            )
            .outerjoin(
                UserHierarchy,
                (top_query.c.next_user_uid == UserHierarchy.user_uid)
                & (top_query.c.role_uid == UserHierarchy.role_uid)
                & (UserHierarchy.survey_uid == survey_uid),
            )
            .outerjoin(User, UserHierarchy.parent_user_uid == User.user_uid)
        )

        recursive_query = top_query.union(bottom_query)

        # Filter the recursive query to only include the rows with no reporting role which
        # are the rows with all the supervisors for the FSLn users
        fsln_supervisors_query = (
            db.session.query(
                recursive_query.c.user_uid,
                recursive_query.c.role_uid,
                recursive_query.c.supervisors,
            )
            .filter(recursive_query.c.reporting_role_uid.is_(None))
            .subquery()
        )

    return fsln_supervisors_query
