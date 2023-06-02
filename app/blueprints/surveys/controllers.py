from flask import jsonify, request
from sqlalchemy.exc import IntegrityError
from app import db
from .models import Survey
from .routes import surveys_bp
from .validators import (
    GetSurveyQueryParamValidator,
    CreateSurveyValidator,
    UpdateSurveyValidator,
)
from app.utils.utils import logged_in_active_user_required


@surveys_bp.route("", methods=["GET"])
@logged_in_active_user_required
def get_all_surveys():
    # /surveys will return all surveys
    # /surveys?user_uid=1 will return surveys created by user with user_uid=1

    user_uid = request.args.get("user_uid")
    if user_uid:
        # Validate the query parameter
        query_param_validator = GetSurveyQueryParamValidator.from_json(request.args)
        if not query_param_validator.validate():
            return (
                jsonify(
                    {
                        "success": False,
                        "data": None,
                        "message": query_param_validator.errors,
                    }
                ),
                400,
            )
        surveys = Survey.query.filter_by(created_by_user_uid=user_uid).all()
    else:
        surveys = Survey.query.all()

    data = [survey.to_dict() for survey in surveys]
    response = {"success": True, "data": data}

    return jsonify(response), 200


@surveys_bp.route("", methods=["POST"])
@logged_in_active_user_required
def create_survey():
    payload = request.get_json()

    # Import the request body payload validator
    payload_validator = CreateSurveyValidator.from_json(payload)

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    # Validate the request body payload
    if payload_validator.validate():
        survey = Survey(**payload)
        try:
            db.session.add(survey)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return jsonify({"error": "survey_id already exists"}), 400
        return (
            jsonify(
                {
                    "success": True,
                    "data": {"message": "success", "survey": survey.to_dict()},
                }
            ),
            201,
        )

    else:
        return jsonify({"success": False, "errors": payload_validator.errors}), 422


@surveys_bp.route("/<int:survey_uid>", methods=["GET"])
@logged_in_active_user_required
def get_survey(survey_uid):
    survey = Survey.query.filter_by(survey_uid=survey_uid).first()
    if survey is None:
        return jsonify({"error": "Survey not found"}), 404
    return jsonify(survey.to_dict())


@surveys_bp.route("/<int:survey_uid>", methods=["PUT"])
@logged_in_active_user_required
def update_survey(survey_uid):
    payload = request.get_json()

    # Import the request body payload validator
    payload_validator = UpdateSurveyValidator.from_json(payload)

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    # Validate the request body payload
    if payload_validator.validate():
        if Survey.query.filter_by(survey_uid=survey_uid).first() is None:
            return jsonify({"error": "Survey not found"}), 404

        Survey.query.filter_by(survey_uid=survey_uid).update(
            {
                Survey.survey_uid: payload_validator.survey_uid.data,
                Survey.survey_id: payload_validator.survey_id.data,
                Survey.survey_name: payload_validator.survey_name.data,
                Survey.survey_description: payload_validator.survey_description.data,
                Survey.project_name: payload_validator.project_name.data,
                Survey.surveying_method: payload_validator.surveying_method.data,
                Survey.irb_approval: payload_validator.irb_approval.data,
                Survey.planned_start_date: payload_validator.planned_start_date.data,
                Survey.planned_end_date: payload_validator.planned_end_date.data,
                Survey.state: payload_validator.state.data,
                Survey.config_status: payload_validator.config_status.data,
            },
            synchronize_session="fetch",
        )
        db.session.commit()
        survey = Survey.query.filter_by(survey_uid=survey_uid).first()
        return jsonify(survey.to_dict()), 200

    else:
        return jsonify({"success": False, "errors": payload_validator.errors}), 422


@surveys_bp.route("/<int:survey_uid>", methods=["DELETE"])
@logged_in_active_user_required
def delete_survey(survey_uid):
    survey = Survey.query.filter_by(survey_uid=survey_uid).first()
    if survey is None:
        return jsonify({"error": "Survey not found"}), 404
    db.session.delete(survey)
    db.session.commit()
    return "", 204
