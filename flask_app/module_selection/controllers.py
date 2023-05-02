from flask import jsonify, request
from .models import db, Module, ModuleStatus
from .routes import module_selection_bp
from .validators import UpdateModuleStatusValidator, AddModuleStatusValidator
import json


@module_selection_bp.route('/modules', methods=['GET'])
def list_modules():
    modules = Module.query.all()
    if not modules:
        return jsonify({'success': False, 'message': 'No modules found.'}), 404
    return jsonify({'success': True, 'data': [module.to_dict() for module in modules]}), 200

@module_selection_bp.route('/module-status', methods=['POST'])
def add_module_status():
    validator = AddModuleStatusValidator.from_json(request.get_json())

    if "X-CSRF-Token" in request.headers:
        validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if not validator.validate():
        return jsonify({'success': False, 'errors': validator.errors}), 422

    survey_uid = validator.survey_uid.data
    modules = validator.modules.data

    for module_id in modules:
        module = Module.query.get(module_id)
        if not module:
            return jsonify({'success': False, 'message': f'Module with id {module_id} does not exist.'}), 404

        module_status = ModuleStatus.query.filter_by(survey_uid=survey_uid, module_id=module_id).first()
        if not module_status:
            module_status = ModuleStatus(survey_uid=survey_uid, module_id=module_id, config_status='Not Started')
            db.session.add(module_status)

    db.session.commit()
    return jsonify({'success': True, 'message': 'Module status added successfully.'}), 200

@module_selection_bp.route('/module-status/<int:survey_uid>', methods=['GET'])
def get_module_status(survey_uid):
    module_status = ModuleStatus.query.filter_by(survey_uid=survey_uid).all()
    return jsonify({'success': True, 'data': [status.to_dict() for status in module_status]}), 200

@module_selection_bp.route('/modules/<int:module_id>/status/<int:survey_uid>', methods=['PUT'])
def update_module_status(module_id, survey_uid):
    module_status = ModuleStatus.query.filter_by(module_id=module_id, survey_uid=survey_uid).first()
    validator = UpdateModuleStatusValidator.from_json(request.get_json())

    if "X-CSRF-Token" in request.headers:
        validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if not validator.validate(module_status):
        return jsonify({'success': False, 'message': validator.errors}), 422

    module_status.config_status = validator.config_status.data

    db.session.commit()

    return jsonify({'success': True, 'data': module_status.to_dict()}), 200


