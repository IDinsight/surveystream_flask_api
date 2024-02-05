from app.utils.utils import custom_permissions_required, validate_payload
from flask import jsonify, request
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app import db
from .models import ModuleQuestionnaire
from .routes import module_questionnaire_bp
from .validators import ModuleQuestionnaireForm


@module_questionnaire_bp.route("/<int:survey_uid>", methods=["GET"])
def get_survey_module_questionnaire(survey_uid):
    module_questionnaire = ModuleQuestionnaire.query.filter_by(
        survey_uid=survey_uid
    ).first()

    if not module_questionnaire:
        return jsonify({"success": False, "error": "No surveys found"}), 404

    data = module_questionnaire.to_dict()
    response = {"success": True, "data": data}

    return jsonify(response), 200


@module_questionnaire_bp.route("/<int:survey_uid>", methods=["PUT"])
@validate_payload(ModuleQuestionnaireForm)
@custom_permissions_required("ADMIN")
def update_survey_module_questionnaire(survey_uid, validated_payload):
    # do upsert
    statement = (
        pg_insert(ModuleQuestionnaire)
        .values(
            survey_uid=survey_uid,
            target_assignment_criteria=validated_payload.target_assignment_criteria.data,
            supervisor_assignment_criteria=validated_payload.supervisor_assignment_criteria.data,
            supervisor_hierarchy_exists=validated_payload.supervisor_hierarchy_exists.data,
            reassignment_required=validated_payload.reassignment_required.data,
            assignment_process=validated_payload.assignment_process.data,
            supervisor_surveyor_relation=validated_payload.supervisor_surveyor_relation.data,
            language_location_mapping=validated_payload.language_location_mapping.data,
        )
        .on_conflict_do_update(
            constraint="pk_module_questionnaire",
            set_={
                "target_assignment_criteria": validated_payload.target_assignment_criteria.data,
                "supervisor_assignment_criteria": validated_payload.supervisor_assignment_criteria.data,
                "supervisor_hierarchy_exists": validated_payload.supervisor_hierarchy_exists.data,
                "reassignment_required": validated_payload.reassignment_required.data,
                "assignment_process": validated_payload.assignment_process.data,
                "supervisor_surveyor_relation": validated_payload.supervisor_surveyor_relation.data,
                "language_location_mapping": validated_payload.language_location_mapping.data,
            },
        )
    )

    db.session.execute(statement)
    db.session.commit()

    return jsonify(message="Success"), 200
