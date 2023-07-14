from flask import jsonify, session, current_app
from flask_login import login_required
from functools import wraps
from app import db
from app.blueprints.auth.models import User
import boto3
import base64
from botocore.exceptions import ClientError


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
