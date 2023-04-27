from . import forms_bp
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


@forms_bp.route("/<form_uid>", methods=["GET"])
@logged_in_active_user_required
def get_form(form_uid):
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
