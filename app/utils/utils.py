from flask import jsonify, session, current_app, request
from flask_login import login_required, logout_user, current_user
from botocore.exceptions import ClientError
from functools import wraps
from app import db
from app.blueprints.auth.models import User
from sqlalchemy import and_, func, or_

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


def get_survey_uids(param_location, param_name):
    """
    Function to get the survey UID's based on the provided parameter location and name.
    Requires:
        param_location (str): Location from which to retrieve the parameter value ("query", "path", or "body").
        param_name (str): Name of the parameter to retrieve.
    Returns: A list of applicable survey UID's.
    """

    from app.blueprints.surveys.models import Survey
    from app.blueprints.forms.models import Form
    from app.blueprints.targets.models import Target
    from app.blueprints.enumerators.models import SurveyorForm, MonitorForm
    from app.blueprints.emails.models import EmailConfig

    if param_name not in [
        "survey_uid",
        "form_uid",
        "target_uid",
        "enumerator_uid",
        "email_config_uid",
    ]:
        raise ValueError(
            "'param_name' parameter must be one of survey_uid, form_uid, target_uid, enumerator_uid, email_config_uid"
        )
    if param_location not in ["query", "path", "body"]:
        raise ValueError("'param_location' parameter must be one of query, path, body")

    if param_location == "query":
        param_value = request.args.get(param_name)
    elif param_location == "path":
        param_value = request.view_args.get(param_name)
    elif param_location == "body":
        param_value = request.get_json().get(param_name)

    if param_value is None:
        raise ValueError(
            f"No value for '{param_name}' was found in request {param_location}"
        )

    survey_uids = []

    if param_name == "survey_uid":
        response = Survey.query.filter(Survey.survey_uid == param_value).first()
        if response is not None:
            survey_uids = [response.survey_uid]
        else:
            raise SurveyNotFoundError(
                f"survey_uid {param_value} not found in the database"
            )
    elif param_name == "email_config_uid":
        response = (
            db.session.query(Form.survey_uid)
            .join(EmailConfig, EmailConfig.form_uid == Form.form_uid)
            .filter(EmailConfig.email_config_uid == param_value)
            .first()
        )
        if response is not None:
            survey_uids = [response.survey_uid]
        else:
            raise SurveyNotFoundError(
                f"Could not find a survey for email_config_uid {param_value} in the database"
            )

    elif param_name == "form_uid":
        response = Form.query.filter(Form.form_uid == param_value).first()
        if response is not None:
            survey_uids = [response.survey_uid]
        else:
            raise SurveyNotFoundError(
                f"Could not find a survey for form_uid {param_value} in the database"
            )

    elif param_name == "target_uid":
        response = (
            db.session.query(Form)
            .join(Target, Form.form_uid == Target.form_uid)
            .filter(Target.target_uid == param_value)
            .first()
        )
        if response is not None:
            survey_uids = [response.survey_uid]
        else:
            raise SurveyNotFoundError(
                f"Could not find a survey for target_uid {param_value} in the database"
            )

    elif param_name == "enumerator_uid":
        # create a sqlalchemy query to get the list of survey_uids for the enumerator_uid from the surveyor_forms and monitor_forms tables
        surveyor_forms_query = (
            db.session.query(Form.survey_uid)
            .join(SurveyorForm, SurveyorForm.form_uid == Form.form_uid)
            .filter(SurveyorForm.enumerator_uid == param_value)
        )
        monitor_forms_query = (
            db.session.query(Form.survey_uid)
            .join(MonitorForm, MonitorForm.form_uid == Form.form_uid)
            .filter(MonitorForm.enumerator_uid == param_value)
        )
        response = surveyor_forms_query.union(monitor_forms_query).distinct()
        if response is not None:
            survey_uids = [survey.survey_uid for survey in response]
        else:
            raise SurveyNotFoundError(
                f"enumerator_uid {param_value} not associated with any surveys in the database"
            )

    return survey_uids


def custom_permissions_required(
    permission_name, survey_uid_param_location=None, survey_uid_param_name=None
):
    """
    Function to check if the current user has the required permissions
    """
    from app.blueprints.roles.models import Permission, Role, SurveyAdmin

    def decorator(fn):
        @wraps(fn)
        def decorated_function(*args, **kwargs):
            # Handle super admins requests
            if current_user.get_is_super_admin():
                return fn(*args, **kwargs)

            if permission_name == "CREATE SURVEY":
                if current_user.get_can_create_survey():
                    return fn(*args, **kwargs)
                else:
                    error_message = (
                        f"User does not have the required permission: {permission_name}"
                    )
                    response = {"success": False, "error": error_message}
                    return jsonify(response), 403

            # Handle non-admin crequests
            # Get survey_uid from request args
            survey_uids = get_survey_uids(
                survey_uid_param_location, survey_uid_param_name
            )

            if len(survey_uids) == 0:
                error_message = (
                    f"Permission denied, survey_uid for permissions required not found"
                )
                response = {"success": False, "error": error_message}
                return jsonify(response), 403

            # check if current user is a survey_admin for the survey
            survey_admin = SurveyAdmin.query.filter(
                SurveyAdmin.user_uid == current_user.user_uid,
                SurveyAdmin.survey_uid.in_(survey_uids),
            ).first()

            if survey_admin:
                # If the user is a survey admin for the survey allow all permissions
                return fn(*args, **kwargs)
            elif permission_name == "ADMIN":
                # deny access if the permission_name was ADMIN
                error_message = (
                    f"User does not have the required permission: {permission_name}"
                )
                response = {"success": False, "error": error_message}
                return jsonify(response), 403

            # continue to check the roles
            # Get all permissions associated with the user's roles
            user_roles = current_user.get_roles()

            # Split permission_name into action and resource
            action, resource = permission_name.split(maxsplit=1)

            try:
                # Query to get role_permissions
                role_permissions = (
                    db.session.query(Permission)
                    .join(
                        Role,
                        Role.survey_uid.in_(survey_uids),
                    )
                    .filter(
                        and_(
                            Role.role_uid == func.any(user_roles),
                            or_(
                                Permission.name == permission_name,
                                and_(
                                    action == "READ",
                                    Permission.name == f"WRITE {resource}",
                                ),
                            ),
                        )
                    )
                    .all()
                )
            except Exception as e:
                print("Error querying role_permissions: %s", e)
                return (
                    jsonify({"success": False, "error": "Error checking permissions"}),
                    500,
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


def validate_query_params(validator):
    """
    Decorator to validate query params
    """

    def decorator(fn):
        @wraps(fn)
        def decorated_function(*args, **kwargs):
            query_param_validator = validator.from_json(request.args)

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

            kwargs["validated_query_params"] = query_param_validator

            return fn(*args, **kwargs)

        return decorated_function

    return decorator


def validate_payload(validator):
    """
    Decorator to validate query params
    """

    def decorator(fn):
        @wraps(fn)
        def decorated_function(*args, **kwargs):
            payload_validator = validator.from_json(request.get_json())

            if not payload_validator.validate():
                return jsonify(message=payload_validator.errors, success=False), 422

            kwargs["validated_payload"] = payload_validator

            return fn(*args, **kwargs)

        return decorated_function

    return decorator


class SurveyNotFoundError(Exception):
    def __init__(self, errors):
        self.errors = [errors]
