from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError
from app import db
from .models import Survey
from .routes import surveys_blueprint


@surveys_blueprint.route("", methods=["GET"])
def get_all_surveys():
    # /surveys will return all surveys
    # /surveys?user_uid=1 will return surveys created by user with user_uid=1

    user_uid = request.args.get("user_uid")
    if user_uid:
        surveys = Survey.query.filter_by(created_by_user_uid=user_uid).all()
    else:
        surveys = Survey.query.all()

    if not surveys:
        return jsonify({"success": False, "error": "No surveys found"}), 404

    data = [survey.to_dict() for survey in surveys]
    response = {"success": True, "data": data}

    return jsonify(response), 200


@surveys_blueprint.route("", methods=["POST"])
def create_survey():
    data = request.get_json()
    survey = Survey(**data)
    errors = survey.validate()
    if errors:
        return jsonify({"errors": errors}), 400
    try:
        db.session.add(survey)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Survey already exists"}), 400
    return (
        jsonify(
            {
                "success": True,
                "data": {"message": "success", "survey": survey.to_dict()},
            }
        ),
        201,
    )


@surveys_blueprint.route("/<survey_id>", methods=["GET"])
def get_survey(survey_id):
    survey = Survey.query.filter_by(survey_id=survey_id).first()
    if survey is None:
        return jsonify({"error": "Survey not found"}), 404
    return jsonify(survey.to_dict())


@surveys_blueprint.route("/<survey_id>", methods=["PUT"])
def update_survey(survey_id):
    survey = Survey.query.filter_by(survey_id=survey_id).first()
    if survey is None:
        return jsonify({"error": "Survey not found"}), 404
    data = request.get_json()
    survey.update(**data)
    db.session.commit()
    return jsonify(survey.to_dict())


@surveys_blueprint.route("/<survey_id>", methods=["DELETE"])
def delete_survey(survey_id):
    survey = Survey.query.filter_by(survey_id=survey_id).first()
    if survey is None:
        return jsonify({"error": "Survey not found"}), 404
    db.session.delete(survey)
    db.session.commit()
    return "", 204
