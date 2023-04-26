from . import survey_forms_blueprint
from app.utils import safe_isoformat, logged_in_active_user_required
from flask import jsonify
from flask_login import current_user
from app import db
from app.models.data_models import (
    Survey,
    AdminForm,
    ParentForm,
    ChildForm,
    UserHierarchy,
)


##############################################################################
# SURVEYS AND FORMS
##############################################################################


@survey_forms_blueprint.route("/api/surveys_list", methods=["GET"])
@logged_in_active_user_required
def view_surveys():
    """
    Returns survey details for a user
    """
    result = (
        db.session.query(Survey, ParentForm)
        .join(ParentForm, Survey.survey_uid == ParentForm.survey_uid, isouter=True)
        .join(UserHierarchy, Survey.survey_uid == UserHierarchy.survey_uid)
        .filter(UserHierarchy.user_uid == current_user.user_uid)
        .all()  # Switch to distinct in case a user has multiple roles for a single survey
    )

    nested_results = []
    for survey, parent_form in result:
        # Find the index of the given survey in our nested_results list
        survey_index = next(
            (
                i
                for i, item in enumerate(nested_results)
                if item["survey_id"] == survey.survey_id
            ),
            None,
        )

        if survey_index is None:
            nested_results.append(
                {
                    "survey_id": survey.survey_id,
                    "survey_name": survey.survey_name,
                    "active": survey.active,
                    "forms": [],
                }
            )

            survey_index = -1

        # We did a left join so we have to check that this survey has parent forms before appending
        if parent_form is not None:
            # Find the index of the given parent_form in our nested_results list
            parent_form_index = next(
                (
                    i
                    for i, item in enumerate(nested_results[survey_index]["forms"])
                    if item["form_name"] == parent_form.form_name
                ),
                None,
            )

            if parent_form_index is None:
                nested_results[survey_index]["forms"].append(
                    {
                        "form_uid": parent_form.form_uid,
                        "form_name": parent_form.form_name,
                        "scto_form_id": parent_form.scto_form_id,
                        "planned_start_date": safe_isoformat(
                            parent_form.planned_start_date
                        ),
                        "planned_end_date": safe_isoformat(
                            parent_form.planned_end_date
                        ),
                    }
                )

                parent_form_index = -1

    return jsonify(nested_results)


@survey_forms_blueprint.route("/api/forms/<form_uid>", methods=["GET"])
@logged_in_active_user_required
def view_form(form_uid):
    """
    Returns details for a parent form
    """
    parent_form_result = (
        db.session.query(ParentForm, ChildForm, Survey)
        .join(ChildForm, ParentForm.form_uid == ChildForm.parent_form_uid, isouter=True)
        .join(Survey, Survey.survey_uid == ParentForm.survey_uid, isouter=True)
        .join(UserHierarchy, Survey.survey_uid == UserHierarchy.survey_uid)
        .filter(
            ParentForm.form_uid == form_uid,
            UserHierarchy.user_uid == current_user.user_uid,
        )
        .all()
    )

    admin_form_result = (
        db.session.query(AdminForm, Survey)
        .join(Survey, Survey.survey_uid == AdminForm.survey_uid)
        .join(UserHierarchy, Survey.survey_uid == UserHierarchy.survey_uid)
        .filter(
            UserHierarchy.user_uid == current_user.user_uid,
        )
        .all()
    )

    nested_results = {}
    for parent_form, child_form, survey in parent_form_result:
        # The first time through the loop we need to populate the parent form information
        if not nested_results:
            nested_results = {
                "survey_id": survey.survey_id,
                "survey_name": survey.survey_name,
                "form_uid": parent_form.form_uid,
                "form_name": parent_form.form_name,
                "scto_form_id": parent_form.scto_form_id,
                "planned_start_date": safe_isoformat(parent_form.planned_start_date),
                "planned_end_date": safe_isoformat(parent_form.planned_end_date),
                "last_ingested_at": safe_isoformat(parent_form.last_ingested_at),
                "child_forms": [],
            }

        # We did a left join so we have to check that this parent form has child forms before appending
        if child_form is not None:
            nested_results["child_forms"].append(
                {
                    "form_type": child_form.form_type,
                    "scto_form_id": child_form.scto_form_id,
                }
            )

    for admin_form, survey in admin_form_result:
        nested_results["child_forms"].append(
            {
                "form_type": admin_form.form_type,
                "scto_form_id": admin_form.scto_form_id,
            }
        )
    return jsonify(nested_results)
