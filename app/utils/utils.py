from flask import jsonify, session, current_app, request
from flask_login import login_required, logout_user, current_user
from botocore.exceptions import ClientError
from functools import wraps
from app import db
from app.blueprints.auth.models import User
from sqlalchemy import and_, func, or_, text

import boto3
import base64


def concat_names(name_tuple):
    """
    Function to concatenate first, middle, last name parts,
    ignoring missing name parts
    """

    name = ""
    for name_part in name_tuple:
        if name_part is not None:
            name += name_part
            name += " "

    name = name.strip()

    return name


def safe_isoformat(value):
    """
    Assert that a value is not None before converting to isoformat()
    """

    if value is not None:
        return value.isoformat()
    else:
        return ""


def safe_get_dict_value(dict, key):
    """
    Assert that an object is not NoneType before trying to get its key
    """

    if dict is not None:
        return dict.get(key, None)
    else:
        return None


def logged_in_active_user_required(f):
    """
    Login required middleware
    Checks additional active user logic. Otherwise pass flow to built-in login_required (Flask-Login) decorator
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "_user_id" in session:
            user_uid = session.get("_user_id")

            if user_uid is not None:
                user = (
                    db.session.query(User)
                    .filter(User.user_uid == user_uid)
                    .one_or_none()
                )
                if user is None:
                    logout_user()
                    return jsonify(message="UNAUTHORIZED"), 401
                if user.is_active() is False:
                    return jsonify(message="INACTIVE_USER"), 403

        return login_required(f)(*args, **kwargs)

    return decorated_function


def get_aws_secret(secret_name, region_name, is_global_secret=False):
    """
    Function to get secrets from the aws secrets manager
    """

    client = get_secret_client(is_global_secret, region_name)

    try:
        secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        raise e
    else:
        if "SecretString" in secret_value_response:
            secret = secret_value_response["SecretString"]
        else:
            secret = base64.b64decode(secret_value_response["SecretBinary"])

    return secret


def get_secret_client(is_global_secret, region_name):
    """
    Function to get secrets client
    """

    if is_global_secret:
        ADMIN_ACCOUNT = current_app.config["ADMIN_ACCOUNT"]

        admin_global_secrets_role_arn = (
            f"arn:aws:iam::{ADMIN_ACCOUNT}:role/web-assume-task-role"
        )
        sts_response = get_sts_assume_role_response(admin_global_secrets_role_arn)

        client = boto3.client(
            service_name="secretsmanager",
            region_name=region_name,
            aws_access_key_id=sts_response["Credentials"]["AccessKeyId"],
            aws_secret_access_key=sts_response["Credentials"]["SecretAccessKey"],
            aws_session_token=sts_response["Credentials"]["SessionToken"],
        )

    else:
        client = boto3.client(service_name="secretsmanager", region_name=region_name)

    return client


def get_sts_assume_role_response(admin_global_secrets_role_arn):
    """
    Function to return details for an AWS role to be assumed
    """

    # Create session using your current creds
    boto_sts = boto3.client("sts")

    # Request to assume the role like this, the ARN is the Role's ARN from
    # the other account you wish to assume. Not your current ARN.
    sts_response = boto_sts.assume_role(
        RoleArn=admin_global_secrets_role_arn, RoleSessionName="new_session"
    )

    return sts_response


def custom_permissions_required(permission_name):
    """
    Function to check if current user has the required permissions
    """
    from app.blueprints.roles.models import Permission, RolePermissions, Role
    from app.blueprints.surveys.models import Survey

    def decorator(fn):
        @wraps(fn)
        def decorated_function(*args, **kwargs):
            # Handle super admins requests
            if current_user.get_is_super_admin():
                return fn(*args, **kwargs)

            # Handle other admin requests
            if permission_name == "ADMIN":
                # use this to validate actions like creating survey
                if current_user.get_is_survey_admin():
                    return fn(*args, **kwargs)
                else:
                    error_message = (
                        f"User does not have the required permission: {permission_name}"
                    )
                    response = {"success": False, "error": error_message}
                    return jsonify(response), 403

            # Handle non-admin crequests
            # Get survey_uid from request args
            survey_uid = request.args.get("survey_uid")
            if not survey_uid and request.args.get("form_uid"):
                # Attempt using form_uid
                form_uid = request.args.get("form_uid")
                survey_uid = db.engine.execute(
                    text(
                        "SELECT survey_uid FROM webapp.parent_forms WHERE form_uid = :form_uid"
                    ),
                    form_uid=form_uid,
                ).scalar()

            if not survey_uid:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Permission denied, survey_uid is required",
                        }
                    ),
                    403,
                )

            # Handle survey admins on non-admin requests
            if current_user.get_is_survey_admin():
                survey = Survey.query.filter_by(survey_uid=survey_uid).first()
                if survey and survey.created_by_user_uid == current_user.user_uid:
                    return fn(*args, **kwargs)
                else:
                    error_message = (
                        "Permission denied, survey not created by the current user"
                    )
                    response = {"success": False, "error": error_message}
                    return jsonify(response), 403

            # Get all permissions associated with the user's roles
            user_roles = current_user.get_roles()

            # Split permission_name into action and resource
            action, resource = permission_name.split(maxsplit=1)

            # Query to get role_permissions
            role_permissions = (
                db.session.query(Permission)
                .join(
                    RolePermissions,
                    Permission.permission_uid == RolePermissions.permission_uid,
                )
                .join(
                    Role,
                    and_(Role.role_uid == RolePermissions.role_uid),
                    Role.survey_uid == survey_uid,
                )
                .filter(
                    and_(
                        Role.role_uid == func.any(user_roles),
                        or_(
                            Permission.name == permission_name,
                            and_(
                                action == "READ", Permission.name == f"WRITE {resource}"
                            ),
                        ),
                    )
                )
                .all()
            )

            # Check if the current user has the specified permission
            if not role_permissions:
                error_message = (
                    f"User does not have the required permission: {permission_name}"
                )
                response = {"success": False, "error": error_message}
                return jsonify(response), 403

            return fn(*args, **kwargs)

        return decorated_function

    return decorator
