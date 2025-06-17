from app import db
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    update_module_status_after_request,
    validate_payload,
)
from flask import jsonify
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .models import ModuleQuestionnaire
from .routes import module_questionnaire_bp
from .validators import ModuleQuestionnaireForm


@module_questionnaire_bp.route("/<int:survey_uid>", methods=["GET"])
@logged_in_active_user_required
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
@logged_in_active_user_required
@validate_payload(ModuleQuestionnaireForm)
@custom_permissions_required("ADMIN", "path", "survey_uid")
@update_module_status_after_request(1, "survey_uid")
def update_survey_module_questionnaire(survey_uid, validated_payload):

    # check if mapping criteria is changed
    existing_module_questionnaire = ModuleQuestionnaire.query.filter_by(
        survey_uid=survey_uid
    ).first()
    if existing_module_questionnaire:
        from app.blueprints.forms.models import Form
        from app.blueprints.mapping.models import UserMappingConfig

        # Delete all user mapping configs for this survey
        main_form = Form.query.filter_by(
            survey_uid=survey_uid, form_type="parent"
        ).first()

        if main_form:
            main_form_uid = main_form.form_uid
            if (
                existing_module_questionnaire.target_mapping_criteria
                != validated_payload.target_mapping_criteria.data
            ):
                UserMappingConfig.query.filter_by(
                    form_uid=main_form_uid, mapping_type="target"
                ).delete(synchronize_session=False)

            if (
                existing_module_questionnaire.surveyor_mapping_criteria
                != validated_payload.surveyor_mapping_criteria.data
            ):
                UserMappingConfig.query.filter_by(
                    form_uid=main_form_uid, mapping_type="surveyor"
                ).delete(synchronize_session=False)

    # do upsert
    statement = (
        pg_insert(ModuleQuestionnaire)
        .values(
            survey_uid=survey_uid,
            target_assignment_criteria=validated_payload.target_assignment_criteria.data,
            target_mapping_criteria=validated_payload.target_mapping_criteria.data,
            surveyor_mapping_criteria=validated_payload.surveyor_mapping_criteria.data,
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
                "target_mapping_criteria": validated_payload.target_mapping_criteria.data,
                "surveyor_mapping_criteria": validated_payload.surveyor_mapping_criteria.data,
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
