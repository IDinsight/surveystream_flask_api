from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_payload,
)
from flask import jsonify
from .models import db, Module, ModuleStatus, ModuleDependency
from .routes import module_selection_bp
from .validators import UpdateModuleStatusValidator, AddModuleStatusValidator
from app.blueprints.surveys.utils import ModuleStatusCalculator


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

    # Get mandatory modules
    mandatory_modules = (
        db.session.query(Module.module_id).filter(Module.optional.is_(False)).all()
    )

    # Add mandatory modules to the selected modules list
    for module in mandatory_modules:
        if module.module_id not in modules:
            modules.append(module.module_id)

    # Get the dependencies for each selected module
    dependencies = (
        db.session.query(ModuleDependency.requires_module_id)
        .filter(ModuleDependency.module_id.in_(modules))
        .distinct()
        .all()
    )

    # Add the dependencies to the selected modules list
    for dependency in dependencies:
        if dependency.requires_module_id not in modules:
            modules.append(dependency.requires_module_id)

    existing_modules_status = ModuleStatus.query.filter_by(survey_uid=survey_uid).all()
    deselected_modules_status = list(
        filter(lambda module: module.module_id not in modules, existing_modules_status)
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

    # Removing the deselected modules
    for module_status in deselected_modules_status:
        db.session.delete(module_status)

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
        )
        .all()
    )
    data = []
    for module in module_status:
        module_status_calculator = ModuleStatusCalculator(survey_uid, module.module_id)
        status = module_status_calculator.get_status()

        data.append(
            {
                "survey_uid": module.survey_uid,
                "module_id": module.module_id,
                "config_status": status,
            }
        )

    return (
        jsonify({"success": True, "data": data}),
        200,
    )


@module_selection_bp.route(
    "/modules/<int:module_id>/status/<int:survey_uid>", methods=["PUT"]
)
@logged_in_active_user_required
@validate_payload(UpdateModuleStatusValidator)
@custom_permissions_required("ADMIN", "path", "survey_uid")
def update_module_status(validated_payload):
    """

    Function to update the status of a module for a survey

    """
    module_id = validate_payload.module_id.data
    survey_uid = validate_payload.survey_uid.data

    module_status = ModuleStatus.query.filter_by(
        module_id=module_id, survey_uid=survey_uid
    ).first()

    module_status.config_status = validated_payload.config_status.data
    db.session.commit()

    return jsonify({"success": True, "data": module_status.to_dict()}), 200
