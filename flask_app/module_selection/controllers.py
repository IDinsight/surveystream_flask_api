from flask import Blueprint, jsonify, request
from .models import db, Module, ModuleStatus
from .routes import module_selection_bp

@module_selection_bp.route('/modules', methods=['GET'])
def list_modules():
    modules = Module.query.all()
    if not modules:
        return jsonify({'success': False, 'message': 'No modules found.'}), 404
    return jsonify({'success': True, 'data': [module.to_dict() for module in modules]}), 200

@module_selection_bp.route('/module_status', methods=['POST'])
def add_module_status():
    survey_uid = request.json.get('survey_uid')
    modules = request.json.get('modules')

    if not survey_uid or not modules:
        return jsonify({'success': False, 'message': 'Both survey_id and modules are required.'}), 400

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

@module_selection_bp.route('/module_status/<int:survey_id>', methods=['GET'])
def get_module_status(survey_id):
    module_status = ModuleStatus.query.filter_by(survey_uid=survey_id).all()
    return jsonify({'success': True, 'data': [status.to_dict() for status in module_status]}), 200

@module_selection_bp.route('/modules/<int:module_id>/status/<int:survey_uid>', methods=['PUT'])
def update_module_status(module_id, survey_uid):
    status = ModuleStatus.query.filter_by(module_id=module_id, survey_uid=survey_uid).first()

    if status is None:
        return jsonify({'success': False, 'error': 'Module status not found.'}), 404

    data = request.get_json()
    status.config_status = data.get('config_status', status.config_status)

    db.session.commit()

    return jsonify({'success': True, 'data': status.to_dict()}), 200


