from . import assignments_bp
from app.utils import concat_names, safe_get_dict_value, logged_in_active_user_required
from flask import jsonify, request
from flask_login import current_user
from app import db
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.queries.method_level_queries import (
    build_get_assignments_query,
    build_get_assignment_surveyors_query,
)
from app.models.data_models import SurveyorAssignment
from .validators import UpdateSurveyorAssignmentsValidator


@assignments_bp.route("", methods=["GET"])
@logged_in_active_user_required
def view_assignments():
    """
    Returns assignment information for a user
    """

    form_uid = request.args.get("form_uid")
    user_uid = current_user.user_uid

    assignment_result = build_get_assignments_query(user_uid, form_uid).all()
    surveyor_result = build_get_assignment_surveyors_query(user_uid, form_uid).all()

    final_result = {"assignments": [], "surveyors": []}

    for (
        target,
        target_status,
        enumerator,
        locations,
        supervisors,
    ) in assignment_result:
        final_result["assignments"].append(
            {
                "assigned_enumerator_uid": getattr(enumerator, "enumerator_uid", None),
                "assigned_enumerator_id": getattr(enumerator, "enumerator_id", None),
                "assigned_enumerator_name": concat_names(
                    (
                        getattr(enumerator, "first_name", None),
                        getattr(enumerator, "middle_name", None),
                        getattr(enumerator, "last_name", None),
                    )
                ),
                "home_state": safe_get_dict_value(
                    getattr(enumerator, "home_address", None), "home_state"
                ),
                "home_district": safe_get_dict_value(
                    getattr(enumerator, "home_address", None), "home_district"
                ),
                "home_block": safe_get_dict_value(
                    getattr(enumerator, "home_address", None), "home_block"
                ),
                "locations": locations,
                "supervisors": supervisors,
                "target_id": target.target_id,
                "target_uid": target.target_uid,
                "respondent_names": target.respondent_names,
                "respondent_phone_primary": target.respondent_phone_primary,
                "respondent_phone_secondary": target.respondent_phone_secondary,
                "address": target.address,
                "gps_latitude": target.gps_latitude,
                "gps_longitude": target.gps_longitude,
                "custom_fields": target.custom_fields,
                "target_assignable": getattr(target_status, "target_assignable", None),
                "last_attempt_survey_status": getattr(
                    target_status, "last_attempt_survey_status", None
                ),
                "last_attempt_survey_status_label": getattr(
                    target_status, "last_attempt_survey_status_label", None
                ),
                "attempts": getattr(target_status, "num_attempts", None),
                "webapp_tag_color": getattr(target_status, "webapp_tag_color", None),
                "revisit_sections": getattr(target_status, "revisit_sections", None),
            }
        )

    for (
        enumerator,
        surveyor_form,
        locations,
        form_productivity,
        total_pending_targets,
        total_complete_targets,
    ) in surveyor_result:
        final_result["surveyors"].append(
            {
                "enumerator_uid": enumerator.enumerator_uid,
                "enumerator_id": enumerator.enumerator_id,
                "enumerator_name": concat_names(
                    (
                        enumerator.first_name,
                        enumerator.middle_name,
                        enumerator.last_name,
                    )
                ),
                "email": enumerator.email,
                "language": enumerator.language,
                "gender": enumerator.gender,
                "phone_primary": enumerator.phone_primary,
                "phone_secondary": enumerator.phone_secondary,
                "locations": locations,
                "home_state": enumerator.home_address["home_state"],
                "home_district": enumerator.home_address["home_district"],
                "home_block": enumerator.home_address["home_block"],
                "surveyor_status": surveyor_form.status,
                "total_pending_targets": total_pending_targets,
                "total_complete_targets": total_complete_targets,
                "form_productivity": form_productivity,
            }
        )

    return jsonify(final_result)


@assignments_bp.route("", methods=["PUT"])
@logged_in_active_user_required
def update_assignments():
    """
    Updates assignment mapping
    """
    form = UpdateSurveyorAssignmentsValidator.from_json(request.get_json())

    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        for assignment in form.assignments.data:
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
                        constraint="surveyor_assignments_pkey",
                        set_={
                            "enumerator_uid": assignment["enumerator_uid"],
                            "user_uid": current_user.user_uid,
                        },
                    )
                )

                db.session.execute(statement)
                db.session.commit()
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
                db.session.commit()

        return jsonify(message="Success"), 200

    else:
        return jsonify(message=form.errors), 422
