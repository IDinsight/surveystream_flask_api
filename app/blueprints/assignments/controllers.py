from datetime import datetime
from sqlalchemy import and_, Date, func, alias, DateTime
from . import assignments_bp
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_query_params,
    validate_payload,
)
from flask import jsonify
from flask_login import current_user
from app import db
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.sql.expression import cast
from .models import SurveyorAssignment
from .validators import (
    AssignmentsEmailValidator,
    AssignmentsQueryParamValidator,
    UpdateSurveyorAssignmentsValidator,
)
from .queries import (
    build_surveyor_formwise_productivity_subquery,
)
from app.blueprints.surveys.models import Survey
from app.blueprints.forms.models import Form
from app.blueprints.targets.models import Target, TargetStatus
from app.blueprints.targets.queries import (
    build_bottom_level_locations_with_location_hierarchy_subquery,
)
from app.blueprints.locations.models import GeoLevel
from app.blueprints.locations.utils import GeoLevelHierarchy
from app.blueprints.locations.errors import InvalidGeoLevelHierarchyError
from app.blueprints.enumerators.models import Enumerator, SurveyorForm, SurveyorLocation
from app.blueprints.enumerators.queries import (
    build_prime_locations_with_location_hierarchy_subquery,
)
from app.blueprints.emails.models import (
    ManualEmailTrigger,
    EmailSchedule,
    EmailConfig,
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

    assignments_query = (
        db.session.query(
            Target,
            TargetStatus,
            Enumerator,
            target_locations_subquery.c.locations,
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
                    },
                    "target_locations": target_locations,
                }
                for target, target_status, enumerator, target_locations in assignments_query.all()
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

    prime_geo_level_uid = (
        Survey.query.filter_by(survey_uid=survey_uid).first().prime_geo_level_uid
    )

    prime_locations_with_location_hierarchy_subquery = (
        build_prime_locations_with_location_hierarchy_subquery(
            survey_uid, prime_geo_level_uid
        )
    )

    surveyor_formwise_productivity_subquery = (
        build_surveyor_formwise_productivity_subquery(survey_uid)
    )

    assignment_enumerators_query = (
        db.session.query(
            Enumerator,
            SurveyorForm,
            prime_locations_with_location_hierarchy_subquery.c.locations,
            surveyor_formwise_productivity_subquery.c.form_productivity,
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
        .filter(
            SurveyorForm.form_uid == form_uid,
            SurveyorForm.status.in_(["Active", "Temp. Inactive"]),
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
                }
                for enumerator, surveyor_form, locations, form_productivity in assignment_enumerators_query.all()
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

    # Run database-backed validations on the assignment inputs
    dropout_enumerator_uids = []
    not_found_enumerator_uids = []
    not_found_target_uids = []
    unassignable_target_uids = []
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

    if len(dropout_enumerator_uids) > 0:
        return (
            jsonify(
                message=f'The following enumerator_uid\'s have status "Dropout" and are ineligible for assignment: {", ".join(str(enumerator_uid) for enumerator_uid in dropout_enumerator_uids)}'
            ),
            422,
        )

    if len(unassignable_target_uids) > 0:
        return (
            jsonify(
                message=f"The following target_uid's are not assignable for this form (most likely because they are complete): {', '.join(str(target_uid) for target_uid in unassignable_target_uids)}"
            ),
            422,
        )

    if len(not_found_enumerator_uids) > 0:
        return (
            jsonify(
                message=f"The following enumerator_uid's were not found for this form: {', '.join(str(enumerator_uid) for enumerator_uid in not_found_enumerator_uids)}"
            ),
            404,
        )

    if len(not_found_target_uids) > 0:
        return (
            jsonify(
                message=f"The following target_uid's were not found for this form: {', '.join(str(target_uid) for target_uid in not_found_target_uids)}"
            ),
            404,
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

    # Get current datetime and current time
    current_datetime = datetime.now()
    current_time = datetime.now().strftime("%H:%M")

    # a subquery to unnest the array of dates and filter dates less than current date
    subquery = (
        db.session.query(
            cast(func.unnest(EmailSchedule.dates) + EmailSchedule.time, Date).label(
                "schedule_date"
            ),
            EmailSchedule.email_schedule_uid,
        )
        .filter(
            func.DATE(current_datetime) <= func.ANY(EmailSchedule.dates),
        )
        .correlate(EmailSchedule)
        .subquery()
    )

    # Alias the subquery
    schedule_dates_subquery = alias(subquery)

    # join schedule_dates_subquery and filter dates only greater than current date time
    email_schedule_res = (
        db.session.query(EmailSchedule, EmailConfig, schedule_dates_subquery)
        .select_from(EmailSchedule)
        .join(
            schedule_dates_subquery,
            and_(
                schedule_dates_subquery.c.email_schedule_uid
                == EmailSchedule.email_schedule_uid,
                cast(
                    schedule_dates_subquery.c.schedule_date + EmailSchedule.time,
                    DateTime,
                )
                >= current_datetime,
            ),
        )
        .join(
            EmailConfig, EmailSchedule.email_config_uid == EmailConfig.email_config_uid
        )
        .filter(
            EmailConfig.form_uid == form_uid,
            func.lower(EmailConfig.config_type) == "assignments",
        )
        .order_by(schedule_dates_subquery.c.schedule_date.asc())
        .first()
    )

    if email_schedule_res:
        email_schedule, email_config, schedule_date, email_schedule_uid = (
            email_schedule_res
        )
        response_data["email_schedule"] = {
            "email_config_uid": email_config.email_config_uid,
            "config_type": email_config.config_type,
            "dates": email_schedule.dates,
            "time": str(email_schedule.time),
            "current_time": str(current_time),
            "email_schedule_uid": email_schedule_uid,
            "schedule_date": schedule_date,
        }

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
        func.lower(EmailConfig.config_type) == "assignments",
        EmailConfig.form_uid == form_uid,
    ).first()

    if email_config is None:
        try:
            email_config = EmailConfig(config_type="assignments", form_uid=form_uid)
            db.session.add(email_config)
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            email_config = EmailConfig.query.filter(
                func.lower(EmailConfig.config_type) == "assignments", form_uid=form_uid
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
