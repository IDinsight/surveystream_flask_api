from flask import jsonify

from app.blueprints.surveys.models import Survey
from app.blueprints.surveys.utils import ModuleStatusCalculator, get_final_module_status
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    update_module_status_after_request,
    validate_payload,
)

from .models import Module, ModuleDependency, ModuleStatus, db
from .routes import module_selection_bp
from .validators import AddModuleStatusValidator


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
@update_module_status_after_request(2, "survey_uid")
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
                survey_uid=survey_uid,
                module_id=module_id,
                config_status="Not Started",  # Default status, we are updating it later
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
    Get the modules along with their stored status for a survey
    """
    survey_state = Survey.query.filter_by(survey_uid=survey_uid).first().state

    module_status = (
        db.session.query(ModuleStatus)
        .filter(
            ModuleStatus.survey_uid == survey_uid,
        )
        .all()
    )
    data = []

    for module in module_status:
        final_status = get_final_module_status(
            survey_uid,
            module.module_id,
            survey_state,
            module.config_status,
        )

        data.append(
            {
                "survey_uid": module.survey_uid,
                "module_id": module.module_id,
                "config_status": final_status,
            }
        )

    return (
        jsonify({"success": True, "data": data}),
        200,
    )


@module_selection_bp.route(
    "/module-status/<int:survey_uid>/<int:module_id>", methods=["PUT"]
)
@logged_in_active_user_required
@custom_permissions_required("ADMIN", "path", "survey_uid")
def update_module_status(survey_uid, module_id):
    """

    Function to update the status of a module for a survey

    """

    module = Module.query.get(module_id).first()
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

    module_status_calculator = ModuleStatusCalculator(survey_uid)
    module_status = module_status_calculator.get_status(module_id)

    ModuleStatus.query.filter_by(survey_uid=survey_uid, module_id=module_id).update(
        {"config_status": module_status}
    )

    db.session.flush()

    # Mapping of which other modules are affected by this change
    effected_modules_dict = {
        1: [14, 17],
        2: [
            4,
            5,
            7,
            8,
            9,
            11,
            12,
            14,
            15,
            16,
            17,
            18,
        ],  # Since module selection is adding modules
        3: [7, 8, 9, 11, 12, 14, 15, 16, 17],
        4: [17],
        5: [17],
        7: [9, 17],
        8: [9, 17],
    }

    for effected_module_id in effected_modules_dict.get(module_id, []):
        # Check if module is in the list of active modules for the survey
        module_status = ModuleStatus.query.filter_by(
            survey_uid=survey_uid, module_id=effected_module_id
        ).first()

        if module_status:
            calculated_module_status = module_status_calculator.get_status(
                effected_module_id
            )

            ModuleStatus.query.filter_by(
                survey_uid=survey_uid, module_id=effected_module_id
            ).update({"config_status": calculated_module_status})

    db.session.commit()

    return (
        jsonify({"success": True, "message": "Module status updated successfully."}),
        200,
    )
