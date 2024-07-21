from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_payload,
)
from flask import jsonify
from .models import db, Module, ModuleStatus
from .routes import module_selection_bp
from .validators import UpdateModuleStatusValidator, AddModuleStatusValidator


@module_selection_bp.route("/modules", methods=["GET"])
@logged_in_active_user_required
def list_modules():
    """
    Function to list all the modules available in the system
    """
    modules = (
        db.session.query(Module)
        .filter(
            Module.module_id.notin_(
                [16]
            )  # Excluding the module with id 16: Assignments column configuration
        )
        .all()
    )

    if not modules:
        return jsonify({"success": False, "message": "No modules found."}), 404
    return (
        jsonify({"success": True, "data": [module.to_dict() for module in modules]}),
        200,
    )


@module_selection_bp.route("/module-status", methods=["POST"])
@logged_in_active_user_required
@validate_payload(AddModuleStatusValidator)
@custom_permissions_required("ADMIN", "body", "survey_uid")
def add_module_status(validated_payload):
    """
    Function to add the module selection results to module status table for a survey

    """
    survey_uid = validated_payload.survey_uid.data
    modules = validated_payload.modules.data

    # If '9: Assignments' is selected, automatically select '16: Assignments column configuration'
    if "9" in modules:
        if "16" not in modules:
            modules.append("16")

    existing_modules_status = ModuleStatus.query.filter_by(survey_uid=survey_uid).all()
    deselected_modules_status = filter(
        lambda module: str(module.module_id) not in modules, existing_modules_status
    )

    for module_id in modules:
        module = Module.query.get(module_id)
        if not module:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Module with id {module_id} does not exist.",
                    }
                ),
                404,
            )

        module_status = ModuleStatus.query.filter_by(
            survey_uid=survey_uid, module_id=module_id
        ).first()
        if not module_status:
            module_status = ModuleStatus(
                survey_uid=survey_uid, module_id=module_id, config_status="Not Started"
            )
            db.session.add(module_status)

    # Removing the modules if user deselect the card
    for module_status in list(deselected_modules_status):
        if module_status.config_status == "Not Started":
            db.session.delete(module_status)
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": 'Only modules with "Not Started" status can be deselected.',
                    }
                ),
                422,
            )

    db.session.commit()
    return (
        jsonify(
            {"success": True, "message": "Module status added/updated successfully."}
        ),
        200,
    )


@module_selection_bp.route("/module-status/<int:survey_uid>", methods=["GET"])
@logged_in_active_user_required
def get_module_status(survey_uid):
    """
    Get the status of all the modules for a survey
    """
    module_status = (
        db.session.query(ModuleStatus)
        .filter(
            ModuleStatus.survey_uid == survey_uid,
            ModuleStatus.module_id.notin_(
                [16]
            ),  # Excluding the module with id 16: Assignments column configuration
        )
        .all()
    )
    return (
        jsonify(
            {"success": True, "data": [status.to_dict() for status in module_status]}
        ),
        200,
    )


@module_selection_bp.route(
    "/modules/<int:module_id>/status/<int:survey_uid>", methods=["PUT"]
)
@logged_in_active_user_required
@validate_payload(UpdateModuleStatusValidator)
@custom_permissions_required("ADMIN", "path", "survey_uid")
def update_module_status(module_id, survey_uid, validated_payload):
    module_status = ModuleStatus.query.filter_by(
        module_id=module_id, survey_uid=survey_uid
    ).first()

    module_status.config_status = validated_payload.config_status.data

    db.session.commit()

    return jsonify({"success": True, "data": module_status.to_dict()}), 200
