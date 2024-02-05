from app.utils.utils import custom_permissions_required, validate_payload
from flask import jsonify, request
from .models import db, Module, ModuleStatus
from .routes import module_selection_bp
from .validators import UpdateModuleStatusValidator, AddModuleStatusValidator


@module_selection_bp.route("/modules", methods=["GET"])
def list_modules():
    modules = Module.query.all()
    if not modules:
        return jsonify({"success": False, "message": "No modules found."}), 404
    return (
        jsonify({"success": True, "data": [module.to_dict() for module in modules]}),
        200,
    )


@module_selection_bp.route("/module-status", methods=["POST"])
@validate_payload(AddModuleStatusValidator)
@custom_permissions_required("ADMIN")
def add_module_status(validated_payload):
    survey_uid = validated_payload.survey_uid.data
    modules = validated_payload.modules.data
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
def get_module_status(survey_uid):
    module_status = ModuleStatus.query.filter_by(survey_uid=survey_uid).all()
    return (
        jsonify(
            {"success": True, "data": [status.to_dict() for status in module_status]}
        ),
        200,
    )


@module_selection_bp.route(
    "/modules/<int:module_id>/status/<int:survey_uid>", methods=["PUT"]
)
@validate_payload(UpdateModuleStatusValidator)
@custom_permissions_required("ADMIN")
def update_module_status(module_id, survey_uid, validated_payload):
    module_status = ModuleStatus.query.filter_by(
        module_id=module_id, survey_uid=survey_uid
    ).first()

    module_status.config_status = validated_payload.config_status.data

    db.session.commit()

    return jsonify({"success": True, "data": module_status.to_dict()}), 200
