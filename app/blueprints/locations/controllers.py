from flask import jsonify, request
from app.utils.utils import logged_in_active_user_required
from flask_login import current_user
from sqlalchemy import insert, cast, Integer
from sqlalchemy.sql import case
from sqlalchemy.exc import IntegrityError
from app import db
from .models import GeoLevel
from .routes import locations_bp
from .validators import SurveyGeoLevelsQueryParamValidator, SurveyGeoLevelsPayloadValidator


@locations_bp.route("/geo-levels", methods=["GET"])
@logged_in_active_user_required
def get_survey_geo_levels():
    """
    Get the geo levels for a given survey
    """

    # Validate the query parameter
    query_param_validator = SurveyGeoLevelsQueryParamValidator.from_json(request.args)
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

    survey_uid = request.args.get("survey_uid")
    user_uid = current_user.user_uid

    # Check if the logged in user has permission to access the given survey

    # Get the geo levels for the survey
    geo_levels = GeoLevel.query.filter_by(survey_uid=survey_uid).order_by(GeoLevel.geo_level_uid).all()

    response = jsonify(
        {
            "success": True,
            "data": [geo_level.to_dict() for geo_level in geo_levels],
        }
    )
    response.add_etag()

    return response, 200


@locations_bp.route("/geo-levels", methods=["PUT"])
@logged_in_active_user_required
def update_survey_geo_levels():
    # Validate the query parameter
    query_param_validator = SurveyGeoLevelsQueryParamValidator.from_json(request.args)
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

    survey_uid = request.args.get("survey_uid")
    user_uid = current_user.user_uid
    
    # Check if the logged in user has permission to access the given survey

    # Import the request body payload validator
    payload_validator = SurveyGeoLevelsPayloadValidator.from_json(request.get_json())

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    # Validate the request body payload
    if payload_validator.validate():
        # Get the geo level data in the db for the given survey
        existing_geo_levels = GeoLevel.query.filter_by(survey_uid=survey_uid).all()

        # Find existing geo levels that need to be deleted because they are not in the payload
        for existing_geo_level in existing_geo_levels:
            if existing_geo_level.geo_level_uid not in [
                geo_level.get("geo_level_uid") for geo_level in payload_validator.geo_levels.data
            ]:
                try:
                    # Update the geo level record so its deletion gets captured by the table logging triggers
                    GeoLevel.query.filter(GeoLevel.geo_level_uid == existing_geo_level.geo_level_uid).update(
                        {
                            GeoLevel.user_uid: user_uid,
                            GeoLevel.to_delete: 1,
                        },
                        synchronize_session=False,
                    )

                    # Delete the geo level record
                    GeoLevel.query.filter(GeoLevel.geo_level_uid == existing_geo_level.geo_level_uid).delete()

                    db.session.commit()
                except IntegrityError as e:
                    db.session.rollback()
                    return jsonify(message=str(e)), 500

        # Get the geo levels that need to be updated
        geo_levels_to_update = [
            geo_level
            for geo_level in payload_validator.geo_levels.data
            if geo_level["geo_level_uid"] is not None
        ]
        if len(geo_levels_to_update) > 0:
            try:
                GeoLevel.query.filter(
                    GeoLevel.geo_level_uid.in_([geo_level["geo_level_uid"] for geo_level in geo_levels_to_update])
                ).update(
                    {
                        GeoLevel.geo_level_name: case(
                            {
                                geo_level["geo_level_uid"]: geo_level["geo_level_name"]
                                for geo_level in geo_levels_to_update
                            },
                            value=GeoLevel.geo_level_uid,
                        ),
                        GeoLevel.parent_geo_level_uid: case(
                            {
                                geo_level["geo_level_uid"]: cast(
                                    geo_level["parent_geo_level_uid"], Integer
                                )
                                for geo_level in geo_levels_to_update
                            },
                            value=GeoLevel.geo_level_uid,
                        ),
                        GeoLevel.user_uid: user_uid,
                    },
                    synchronize_session=False,
                )

                db.session.commit()
            except IntegrityError as e:
                db.session.rollback()
                return jsonify(message=str(e)), 500

        # Get the geo levels that need to be created
        geo_levels_to_insert = [
            geo_level for geo_level in payload_validator.geo_levels.data if geo_level["geo_level_uid"] is None
        ]
        if len(geo_levels_to_insert) > 0:
            for geo_level in geo_levels_to_insert:
                statement = insert(GeoLevel).values(
                    geo_level_name=geo_level["geo_level_name"],
                    survey_uid=survey_uid,
                    parent_geo_level_uid=geo_level["parent_geo_level_uid"],
                    user_uid=user_uid,
                )

                db.session.execute(statement)
                db.session.commit()

        return jsonify(message="Success"), 200

    else:
        return jsonify({"success": False, "errors": payload_validator.errors}), 422
