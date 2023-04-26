from . import targets_blueprint
from app.utils import logged_in_active_user_required
from flask import jsonify, request
from flask_login import current_user
from app.queries.method_level_queries import build_get_targets_query


##############################################################################
# TARGETS
##############################################################################


@targets_blueprint.route("/api/targets", methods=["GET"])
@logged_in_active_user_required
def view_targets():
    """
    Returns list of targets for a user
    """
    form_uid = request.args.get("form_uid")
    user_uid = current_user.user_uid

    result = build_get_targets_query(user_uid, form_uid).all()

    final_result = []

    for target, target_status, supervisors, locations in result:
        final_result.append(
            {
                "supervisors": supervisors,
                "locations": locations,
                "target_id": target.target_id,
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

    return jsonify(final_result)
