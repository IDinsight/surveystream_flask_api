from flask import Blueprint, jsonify, request
from sqlalchemy.dialects.postgresql import insert as pg_insert

from flask_app.database import db
from flask_app.models.form_models import ModuleQuestionnaireForm

from .models import ModuleQuestionnaire
from .routes import module_questionnaire_bp


@module_questionnaire_bp.route(
    "/module-questionnaire/<int:survey_uid>", methods=["GET"]
)
def get_survey_module_questionnaire(survey_uid):
    module_questionnaire = ModuleQuestionnaire.query.filter_by(
        survey_uid=survey_uid
    ).first()

    if not module_questionnaire:
        return jsonify({"success": False, "error": "No surveys found"}), 404

    data = module_questionnaire.to_dict()
    response = {"success": True, "data": data}

    return jsonify(response), 200


@module_questionnaire_bp.route(
    "/module-questionnaire/<int:survey_uid>", methods=["PUT"]
)
def update_survey_module_questionnaire(survey_uid):

    form = ModuleQuestionnaireForm.from_json(request.get_json())

    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():

        # do upsert
        statement = (
            pg_insert(ModuleQuestionnaire)
            .values(
                survey_uid=form.survey_uid.data,
                target_assignment_criteria=form.target_assignment_criteria.data,
                supervisor_assignment_criteria=form.supervisor_assignment_criteria.data,
                supervisor_hierarchy_exists=form.supervisor_hierarchy_exists.data,
                reassignment_required=form.reassignment_required.data,
                assignment_process=form.assignment_process.data,
                supervisor_enumerator_relation=form.supervisor_enumerator_relation.data,
                language_lacation_mapping=form.language_lacation_mapping.data,
            )
            .on_conflict_do_update(
                constraint="module_questionnaire_pkey",
                set_={
                    "target_assignment_criteria": form.target_assignment_criteria.data,
                    "supervisor_assignment_criteria": form.supervisor_assignment_criteria.data,
                    "supervisor_hierarchy_exists": form.supervisor_hierarchy_exists.data,
                    "reassignment_required": form.reassignment_required.data,
                    "assignment_process": form.assignment_process.data,
                    "supervisor_enumerator_relation": form.supervisor_enumerator_relation.data,
                    "language_lacation_mapping": form.language_lacation_mapping.data,
                },
            )
        )

        db.session.execute(statement)
        db.session.commit()

        return jsonify(message="Success"), 200

    else:
        return jsonify(message=form.errors), 422
