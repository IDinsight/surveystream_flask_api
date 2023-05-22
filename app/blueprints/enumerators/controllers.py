from . import enumerators_bp
from app.utils import concat_names, logged_in_active_user_required
from flask import jsonify, request
from flask_login import current_user
from app import db
from app.queries.helper_queries import build_survey_query
from app.queries.method_level_queries import build_get_enumerators_query
from app.models.data_models import (
    SurveyorAssignment,
    Target,
    TargetStatus,
    SurveyorForm,
)
from app.blueprints.forms.models import (
    ParentForm
)
from .validators import UpdateSurveyorFormStatusValidator
from sqlalchemy import or_


@enumerators_bp.route("", methods=["GET"])
@logged_in_active_user_required
def get_enumerators():
    """
    Returns list of enumerators for a user
    """
    form_uid = request.args.get("form_uid")
    user_uid = current_user.user_uid

    result = build_get_enumerators_query(user_uid, form_uid).all()

    final_result = []

    for (
        enumerator,
        surveyor_form,
        locations,
        supervisors,
        forms,
        form_productivity,
    ) in result:
        final_result.append(
            {
                "enumerator_id": enumerator.enumerator_id,
                "enumerator_uid": enumerator.enumerator_uid,
                "name": concat_names(
                    (
                        enumerator.first_name,
                        enumerator.middle_name,
                        enumerator.last_name,
                    )
                ),
                "email": enumerator.email,
                "language": enumerator.language,
                "gender": enumerator.gender,
                "home_state": enumerator.home_address["home_state"],
                "home_district": enumerator.home_address["home_district"],
                "home_block": enumerator.home_address["home_block"],
                "home_address": enumerator.home_address["address"],
                "phone_primary": enumerator.phone_primary,
                "phone_secondary": enumerator.phone_secondary,
                "locations": locations,
                "status": surveyor_form.status,
                "supervisors": supervisors,
                "forms": forms,
                "form_productivity": form_productivity,
            }
        )

    return jsonify(final_result)


@enumerators_bp.route("/<int:enumerator_uid>", methods=["PATCH"])
@logged_in_active_user_required
def update_enumerator_status(enumerator_uid):
    """
    Updates the status of an enumerator
    """
    form = UpdateSurveyorFormStatusValidator.from_json(request.get_json())

    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        surveyor_form = (
            db.session.query(SurveyorForm)
            .filter(
                SurveyorForm.enumerator_uid == enumerator_uid,
                SurveyorForm.form_uid == form.form_uid.data,
            )
            .first()
        )

        if surveyor_form:
            survey_query = build_survey_query(form.form_uid.data)

            forms_in_survey_query = db.session.query(ParentForm.form_uid).filter(
                ParentForm.survey_uid.in_(survey_query.subquery())
            )

            # added user_id to show who is performing the action
            db.session.query(SurveyorForm).filter(
                SurveyorForm.enumerator_uid == enumerator_uid,
                SurveyorForm.form_uid.in_(forms_in_survey_query.subquery()),
            ).update(
                {
                    SurveyorForm.status: form.status.data,
                    SurveyorForm.user_uid: current_user.user_uid,
                },
                synchronize_session=False,
            )

            # This is special logic that says to release the surveyor's assignments
            # for all the forms in the survey if the surveyor is marked as a dropout.
            # This should be restricted to the assignable targets (i.e. not completed)
            # assignments for the surveyor

            if form.status.data == "Dropout":
                survey_query = build_survey_query(form.form_uid.data)

                # Add this query so as to capture who is deleting the Assignment
                db.session.query(SurveyorAssignment).filter(
                    SurveyorAssignment.enumerator_uid == enumerator_uid,
                    SurveyorAssignment.target_uid == Target.target_uid,
                ).update(
                    {
                        SurveyorAssignment.user_uid: current_user.user_uid,
                        SurveyorAssignment.to_delete: 1,
                    },
                    synchronize_session=False,
                )

                db.session.query(SurveyorAssignment).filter(
                    SurveyorAssignment.target_uid == Target.target_uid,
                    Target.form_uid == ParentForm.form_uid,
                    TargetStatus.target_uid == SurveyorAssignment.target_uid,
                    ParentForm.survey_uid.in_(survey_query.subquery()),
                    SurveyorAssignment.enumerator_uid == enumerator_uid,
                    or_(
                        TargetStatus.target_assignable.is_(True),
                        TargetStatus.target_assignable.is_(None),
                    ),
                ).delete(synchronize_session=False)

            db.session.commit()

            return jsonify(message="Record updated"), 200

        else:
            return jsonify(message="Record not found"), 404

    else:
        return jsonify(message=form.errors), 422
