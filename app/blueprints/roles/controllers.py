from app.blueprints.auth.models import User
from flask import jsonify, request
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_query_params,
    validate_payload,
)
from flask_login import current_user
from sqlalchemy import insert, cast, Integer, ARRAY, func, distinct
from sqlalchemy.sql import case
from sqlalchemy.exc import IntegrityError
from app import db
from .models import Role, Permission, RolePermission, UserHierarchy
from .routes import roles_bp
from .validators import (
    SurveyRolesQueryParamValidator,
    SurveyRolesPayloadValidator,
    UserHierarchyPayloadValidator,
    UserHierarchyParamValidator,
    CreatePermissionPayloadValidator,
)
from .utils import run_role_hierarchy_validations


@roles_bp.route("/roles", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(SurveyRolesQueryParamValidator)
def get_survey_roles(validated_query_params):
    """Function to get roles per survey"""

    survey_uid = validated_query_params.survey_uid.data

    user_subquery = (
        db.session.query(
            func.unnest(User.roles).label("role_uid"),
            User.user_uid.label("user_uid"),
        )
        .filter(User.to_delete.isnot(True))
        .subquery()
    )

    query = (
        db.session.query(
            Role,
            func.coalesce(func.count(distinct(user_subquery.c.user_uid)), 0).label(
                "user_count"
            ),
        )
        .outerjoin(user_subquery, user_subquery.c.role_uid == Role.role_uid)
        .filter(Role.survey_uid == survey_uid)
        .group_by(Role.role_uid)
        .order_by(Role.role_uid)
    )

    # Execute the query and fetch the results
    roles_with_count = query.all()
    response = jsonify(
        {
            "success": True,
            "data": [
                {
                    **role.to_dict(),
                    "user_count": user_count if user_count is not None else 0,
                }
                for role, user_count in roles_with_count
            ],
        }
    )
    response.add_etag()
    return response, 200


@roles_bp.route("/roles", methods=["PUT"])
@logged_in_active_user_required
@validate_query_params(SurveyRolesQueryParamValidator)
@validate_payload(SurveyRolesPayloadValidator)
@custom_permissions_required("ADMIN", "query", "survey_uid")
def update_survey_roles(validated_query_params, validated_payload):
    """
    Function to update roles per survey
    """

    survey_uid = validated_query_params.survey_uid.data
    user_uid = current_user.user_uid

    payload = request.get_json()
    roles = validated_payload.roles.data

    if payload.get("validate_hierarchy"):
        if len(roles) > 0:
            role_hierarchy_errors = run_role_hierarchy_validations(roles)

            if len(role_hierarchy_errors) > 0:
                return (
                    jsonify({"success": False, "errors": role_hierarchy_errors}),
                    422,
                )

    existing_roles = Role.query.filter_by(survey_uid=survey_uid).all()

    for existing_role in existing_roles:
        if existing_role.role_uid not in [role.get("role_uid") for role in roles]:
            try:
                Role.query.filter(Role.role_uid == existing_role.role_uid).update(
                    {
                        Role.user_uid: user_uid,
                        Role.to_delete: 1,
                    },
                    synchronize_session=False,
                )

                Role.query.filter(Role.role_uid == existing_role.role_uid).delete()

                db.session.commit()
            except IntegrityError as e:
                db.session.rollback()
                return jsonify(message=str(e)), 500

    roles_to_update = [role for role in roles if role["role_uid"] is not None]
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
                            role["role_uid"]: cast(role["reporting_role_uid"], Integer)
                            for role in roles_to_update
                        },
                        value=Role.role_uid,
                    ),
                    Role.user_uid: user_uid,
                    Role.permissions: case(
                        {
                            role["role_uid"]: cast(role["permissions"], ARRAY(Integer))
                            for role in roles_to_update
                        },
                        value=Role.role_uid,
                    ),
                },
                synchronize_session=False,
            )
            db.session.commit()

            for role in roles_to_update:
                RolePermission.query.filter_by(role_uid=role["role_uid"]).delete()

                for permission_uid in role["permissions"]:
                    permissions_statement = insert(RolePermission).values(
                        role_uid=role["role_uid"],
                        permission_uid=permission_uid,
                    )
                    db.session.execute(permissions_statement)
            db.session.commit()

        except IntegrityError as e:
            db.session.rollback()
            return jsonify(message=str(e)), 500

    roles_to_insert = [role for role in roles if role["role_uid"] is None]
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

            for permission_uid in role["permissions"]:
                permissions_statement = insert(RolePermission).values(
                    role_uid=role_uid,
                    permission_uid=permission_uid,
                )
                db.session.execute(permissions_statement)

            db.session.commit()

    return jsonify(message="Success"), 200


### PERMISSIONS
# GET all permissions
@roles_bp.route("/permissions", methods=["GET"])
@logged_in_active_user_required
def get_permissions():
    """Function to get permissions"""
    permissions = Permission.query.all()
    permission_list = [
        {
            "permission_uid": permission.permission_uid,
            "name": permission.name,
            "description": permission.description,
        }
        for permission in permissions
    ]
    return jsonify(permission_list)


# POST create a new permission
@roles_bp.route("/permissions", methods=["POST"])
@logged_in_active_user_required
@validate_payload(CreatePermissionPayloadValidator)
@custom_permissions_required("ADMIN")
def create_permission(validated_payload):
    """Function to create permissions"""

    name = validated_payload.name.data
    description = validated_payload.description.data

    try:
        new_permission = Permission(name=name, description=description)
        db.session.add(new_permission)
        db.session.commit()

        result = {
            "message": "Permission created successfully",
            "permission_uid": new_permission.permission_uid,
            "name": new_permission.name,
            "description": new_permission.description,
        }

        return jsonify(result), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Permission with this name already exists"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500
    finally:
        db.session.close()


# GET details of a specific permission
@roles_bp.route("/permissions/<int:permission_uid>", methods=["GET"])
@logged_in_active_user_required
def get_permission(permission_uid):
    """Function to get single permission"""
    permission = Permission.query.get(permission_uid)
    if not permission:
        return jsonify(message="Permission not found"), 404

    result = {
        "permission_uid": permission.permission_uid,
        "name": permission.name,
        "description": permission.description,
    }

    return jsonify(result)


# PUT update a specific permission
@roles_bp.route("/permissions/<int:permission_uid>", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(CreatePermissionPayloadValidator)
@custom_permissions_required("ADMIN")
def update_permission(permission_uid, validated_payload):
    """Function to update permission"""
    permission = Permission.query.get(permission_uid)
    if not permission:
        return jsonify(message="Permission not found"), 404

    name = validated_payload.name.data
    description = validated_payload.description.data

    try:
        permission.name = name
        permission.description = description
        db.session.commit()

        result = {
            "message": "Permission updated successfully",
            "permission_uid": permission.permission_uid,
            "name": permission.name,
            "description": permission.description,
        }

        return jsonify(result), 200
    except IntegrityError:
        db.session.rollback()
        return (
            jsonify(
                {"error": "Updating to this name would violate uniqueness constraint"}
            ),
            400,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500
    finally:
        db.session.close()


# DELETE a specific permission
@roles_bp.route("/permissions/<int:permission_uid>", methods=["DELETE"])
@logged_in_active_user_required
@custom_permissions_required("ADMIN")
def delete_permission(permission_uid):
    """Function to delete permission"""
    permission = Permission.query.get(permission_uid)
    if not permission:
        return jsonify(message="Permission not found"), 404

    db.session.delete(permission)
    db.session.commit()

    return jsonify(message="Permission deleted successfully"), 200


### UserHierarchy


@roles_bp.route("/user-hierarchy", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(UserHierarchyParamValidator)
def get_user_hierarchy(validated_query_params):
    """Function to get user hierarchy"""

    survey_uid = validated_query_params.survey_uid.data
    user_uid = request.args.get("user_uid")

    user_hierarchy = UserHierarchy.query.filter_by(
        survey_uid=survey_uid, user_uid=user_uid
    ).first()

    if user_hierarchy:
        return (
            jsonify(
                {
                    "success": True,
                    "data": user_hierarchy.to_dict(),
                }
            ),
            200,
        )
    else:
        return jsonify(message="User hierarchy not found"), 404


@roles_bp.route("/user-hierarchy", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(UserHierarchyPayloadValidator)
@custom_permissions_required("ADMIN", "body", "survey_uid")
def update_user_hierarchy(validated_payload):
    """Function to update user hierarchy"""

    survey_uid = validated_payload.survey_uid.data
    user_uid = validated_payload.user_uid.data
    role_uid = validated_payload.role_uid.data
    parent_user_uid = validated_payload.parent_user_uid.data

    existing_user_hierarchy = UserHierarchy.query.filter_by(
        survey_uid=survey_uid, user_uid=user_uid
    ).first()

    if existing_user_hierarchy:
        existing_user_hierarchy.role_uid = role_uid
        existing_user_hierarchy.parent_user_uid = parent_user_uid
        db.session.commit()
        return (
            jsonify(
                message="User hierarchy updated successfully",
                user_hierarchy=existing_user_hierarchy.to_dict(),
            ),
            200,
        )
    else:
        new_user_hierarchy = UserHierarchy(
            survey_uid=survey_uid,
            user_uid=user_uid,
            role_uid=role_uid,
            parent_user_uid=parent_user_uid,
        )

        db.session.add(new_user_hierarchy)
        db.session.commit()
        return (
            jsonify(
                message="User hierarchy created successfully",
                user_hierarchy=new_user_hierarchy.to_dict(),
            ),
            200,
        )


@roles_bp.route("/user-hierarchy", methods=["DELETE"])
@logged_in_active_user_required
@validate_query_params(UserHierarchyParamValidator)
@custom_permissions_required("ADMIN", "query", "survey_uid")
def delete_user_hierarchy(validated_query_params):
    """Function to delete user hierarchy"""

    survey_uid = validated_query_params.survey_uid.data
    user_uid = validated_query_params.user_uid.data

    user_hierarchy = UserHierarchy.query.filter_by(
        survey_uid=survey_uid, user_uid=user_uid
    ).first()

    if user_hierarchy:
        db.session.delete(user_hierarchy)
        db.session.commit()

        return jsonify(message="User hierarchy deleted successfully"), 200
    else:
        return jsonify(message="User hierarchy not found"), 404
