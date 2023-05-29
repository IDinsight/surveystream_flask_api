from flask import jsonify, request
from app.utils import logged_in_active_user_required
from flask_login import current_user
from sqlalchemy import insert, cast, Integer
from sqlalchemy.sql import case
from sqlalchemy.exc import IntegrityError
from app import db
from .models import Role
from .routes import roles_bp
from .validators import SurveyRolesQueryParamValidator, SurveyRolesPayloadValidator


@roles_bp.route("", methods=["GET"])
@logged_in_active_user_required
def get_survey_roles():
    """
    Get the roles for a given survey
    """

    # Validate the query parameter
    query_param_validator = SurveyRolesQueryParamValidator.from_json(request.args)
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

    # Get the roles for the survey
    roles = Role.query.filter_by(survey_uid=survey_uid).order_by(Role.role_uid).all()

    response = jsonify(
        {
            "success": True,
            "data": [role.to_dict() for role in roles],
        }
    )
    response.add_etag()

    return response, 200


@roles_bp.route("", methods=["PUT"])
@logged_in_active_user_required
def update_survey_roles():
    # Validate the query parameter
    query_param_validator = SurveyRolesQueryParamValidator.from_json(request.args)
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
    payload_validator = SurveyRolesPayloadValidator.from_json(request.get_json())

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    # Validate the request body payload
    if payload_validator.validate():
        # Get the role data in the db for the given survey
        existing_roles = Role.query.filter_by(survey_uid=survey_uid).all()

        # Find existing roles that need to be deleted because they are not in the payload
        for existing_role in existing_roles:
            if existing_role.role_uid not in [
                role.get("role_uid") for role in payload_validator.roles.data
            ]:
                try:
                    # Update the role record so its deletion gets captured by the table logging triggers
                    Role.query.filter(Role.role_uid == existing_role.role_uid).update(
                        {
                            Role.user_uid: user_uid,
                            Role.to_delete: 1,
                        },
                        synchronize_session=False,
                    )

                    # Delete the role record
                    Role.query.filter(Role.role_uid == existing_role.role_uid).delete()

                    db.session.commit()
                except IntegrityError as e:
                    db.session.rollback()
                    return jsonify(message=str(e)), 500

        # Get the roles that need to be updated
        roles_to_update = [
            role
            for role in payload_validator.roles.data
            if role["role_uid"] is not None
        ]
        if len(roles_to_update) > 0:
            try:
                Role.query.filter(
                    Role.role_uid.in_([role["role_uid"] for role in roles_to_update])
                ).update(
                    {
                        Role.role_name: case(
                            {
                                role["role_uid"]: role["role_name"]
                                for role in roles_to_update
                            },
                            value=Role.role_uid,
                        ),
                        Role.reporting_role_uid: case(
                            {
                                role["role_uid"]: cast(
                                    role["reporting_role_uid"], Integer
                                )
                                for role in roles_to_update
                            },
                            value=Role.role_uid,
                        ),
                        Role.user_uid: user_uid,
                    },
                    synchronize_session=False,
                )

                db.session.commit()
            except IntegrityError as e:
                db.session.rollback()
                return jsonify(message=str(e)), 500

        # Get the roles that need to be created
        roles_to_insert = [
            role for role in payload_validator.roles.data if role["role_uid"] is None
        ]
        if len(roles_to_insert) > 0:
            for role in roles_to_insert:
                statement = insert(Role).values(
                    role_name=role["role_name"],
                    survey_uid=survey_uid,
                    reporting_role_uid=role["reporting_role_uid"],
                    user_uid=user_uid,
                )

                db.session.execute(statement)
                db.session.commit()

        return jsonify(message="Success"), 200

    else:
        return jsonify({"success": False, "errors": payload_validator.errors}), 422
