from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError
from flask_app.database import db
from .models import Survey
from .routes import survey_bp

@survey_bp.route('', methods=['GET'])
def get_all_surveys():
    surveys = Survey.query.all()
    return jsonify([survey.to_dict() for survey in surveys])


@survey_bp.route('', methods=['POST'])
def create_survey():
    data = request.get_json()
    survey = Survey(**data)
    try:
        db.session.add(survey)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Survey already exists'}), 400
    return jsonify(survey.to_dict()), 201


@survey_bp.route('/<survey_id>', methods=['GET'])
def get_survey(survey_id):
    survey = Survey.query.filter_by(survey_id=survey_id).first()
    if survey is None:
        return jsonify({'error': 'Survey not found'}), 404
    return jsonify(survey.to_dict())


@survey_bp.route('/<survey_id>', methods=['PUT'])
def update_survey(survey_id):
    survey = Survey.query.filter_by(survey_id=survey_id).first()
    if survey is None:
        return jsonify({'error': 'Survey not found'}), 404
    data = request.get_json()
    survey.update(**data)
    db.session.commit()
    return jsonify(survey.to_dict())


@survey_bp.route('/<survey_id>', methods=['DELETE'])
def delete_survey(survey_id):
    survey = Survey.query.filter_by(survey_id=survey_id).first()
    if survey is None:
        return jsonify({'error': 'Survey not found'}), 404
    db.session.delete(survey)
    db.session.commit()
    return '', 204
