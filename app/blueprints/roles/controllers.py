from flask import jsonify, request
from app.utils.utils import logged_in_active_user_required
from flask_login import current_user
from sqlalchemy import insert, cast, Integer, ARRAY
from sqlalchemy.sql import case
from sqlalchemy.exc import IntegrityError
from app import db
from .models import Role, Permission, RolePermissions
from .routes import roles_bp
from .validators import SurveyRolesQueryParamValidator, SurveyRolesPayloadValidator
from .utils import run_role_hierarchy_validations


@roles_bp.route("/roles", methods=["GET"])
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


@roles_bp.route("/roles", methods=["PUT"])
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
    payload = request.get_json()
    payload_validator = SurveyRolesPayloadValidator.from_json(payload)

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        payload_validator.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    # Validate the request body payload
    if payload_validator.validate():
        # If validate_hierarchy is true, validate the hierarchy of the geo levels
        if payload.get("validate_hierarchy"):
            roles = payload_validator.roles.data

            if len(roles) > 0:
                role_hierarchy_errors = run_role_hierarchy_validations(roles)

                if len(role_hierarchy_errors) > 0:
                    return (
                        jsonify({"success": False, "errors": role_hierarchy_errors}),
                        422,
                    )
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
                        Role.permissions: case(
                            {role["role_uid"]: cast(role["permissions"], ARRAY(Integer)) for role in roles_to_update},
                            value=Role.role_uid,
                        ),
                },
                    synchronize_session=False,
                )
                db.session.commit()

                # Update RolePermissions table
                for role in roles_to_update:
                    # Clear existing permissions for the role
                    RolePermissions.query.filter_by(role_uid=role["role_uid"]).delete()

                    # Insert new permissions for the role
                    for permission_uid in role["permissions"]:
                        permissions_statement = insert(RolePermissions).values(
                            role_uid=role["role_uid"],
                            permission_uid=permission_uid,
                        )
                        db.session.execute(permissions_statement)
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
                    permissions=role["permissions"],
                )

                result = db.session.execute(statement)
                role_uid = result.inserted_primary_key[0]

                # Associating roles with permissions in the RolePermissions table
                for permission_uid in role["permissions"]:
                    permissions_statement = insert(RolePermissions).values(
                        role_uid=role_uid,
                        permission_uid=permission_uid,
                    )
                    db.session.execute(permissions_statement)

                db.session.commit()


        return jsonify(message="Success"), 200

    else:
        return jsonify({"success": False, "errors": payload_validator.errors}), 422



### PERMISSIONS


# GET all permissions
@roles_bp.route('/permissions', methods=['GET'])
@logged_in_active_user_required
def get_permissions():
    permissions = Permission.query.all()
    permission_list = [{'permission_uid': permission.permission_uid, 'name': permission.name, 'description': permission.description}
                       for permission in permissions]
    return jsonify(permission_list)


# POST create a new permission
@roles_bp.route('/permissions', methods=['POST'])
@logged_in_active_user_required
def create_permission():
    data = request.get_json()

    # Validate input data
    if 'name' not in data or 'description' not in data:
        return jsonify({'error': 'Name and description are required fields'}), 400

    new_permission = Permission(name=data['name'], description=data['description'])
    db.session.add(new_permission)
    db.session.commit()

    result = {
        'message': 'Permission created successfully',
        'permission_uid': new_permission.permission_uid,
        'name': new_permission.name,
        'description': new_permission.description
    }

    return jsonify(result), 201


# GET details of a specific permission
@roles_bp.route('/permissions/<int:permission_uid>', methods=['GET'])
@logged_in_active_user_required
def get_permission(permission_uid):
    permission = Permission.query.get(permission_uid)
    if not permission:
        return jsonify(message='Permission not found'), 404

    result = {
        'permission_uid': permission.permission_uid,
        'name': permission.name,
        'description': permission.description
    }

    return jsonify(result)


# PUT update a specific permission
@roles_bp.route('/permissions/<int:permission_uid>', methods=['PUT'])
@logged_in_active_user_required
def update_permission(permission_uid):
    permission = Permission.query.get(permission_uid)
    if not permission:
        return jsonify(message='Permission not found'), 404

    data = request.get_json()

    # Validate input data
    if 'name' not in data or 'description' not in data:
        return jsonify({'error': 'Name and description are required fields'}), 400

    permission.name = data['name']
    permission.description = data['description']
    db.session.commit()

    result = {
        'message': 'Permission updated successfully',
        'permission_uid': permission.permission_uid,
        'name': permission.name,
        'description': permission.description
    }

    return jsonify(result), 200


# DELETE a specific permission
@roles_bp.route('/permissions/<int:permission_uid>', methods=['DELETE'])
@logged_in_active_user_required
def delete_permission(permission_uid):
    permission = Permission.query.get(permission_uid)
    if not permission:
        return jsonify(message='Permission not found'), 404

    db.session.delete(permission)
    db.session.commit()

    return jsonify(message='Permission deleted successfully'), 200