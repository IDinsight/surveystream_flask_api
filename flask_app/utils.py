from sshtunnel import SSHTunnelForwarder
import paramiko
from io import StringIO
import boto3
import base64
from botocore.exceptions import ClientError
from flask_app.queries.helper_queries import build_user_level_query
import os


def get_postgres_uri(
    endpoint,
    port,
    database,
    username,
    password,
):
    """
    Returns PostgreSQL database URI given info and secrets
    """

    connection_uri = "postgresql://%s:%s@%s:%s/%s" % (
        username,
        password,
        endpoint,
        port,
        database,
    )

    return connection_uri


def create_ssh_connection_object(
    ssh_private_key, ec2_endpoint, ec2_username, pg_endpoint, pg_port, local_port
):
    ssh_pkey = paramiko.RSAKey.from_private_key(StringIO(ssh_private_key))
    server = SSHTunnelForwarder(
        (ec2_endpoint, 22),
        ssh_username=ec2_username,
        ssh_pkey=ssh_pkey,
        remote_bind_address=(pg_endpoint, pg_port),
        local_bind_address=("localhost", local_port),
    )

    return server


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

        ADMIN_ACCOUNT = os.getenv("ADMIN_ACCOUNT")

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


def safe_isoformat(value):
    """
    Assert that a value is not None before converting to isoformat()
    """

    if value is not None:
        return value.isoformat()
    else:
        return ""


def get_core_user_status(user_uid, survey_query):
    """
    Return a boolean indicating whether the given user
    is a core team user on the given survey
    """

    result = build_user_level_query(user_uid, survey_query).first()

    level = result.level

    if level == 0:
        return True
    else:
        return False


def safe_get_dict_value(dict, key):
    """
    Assert that an object is not NoneType before trying to get its key
    """

    if dict is not None:
        return dict.get(key, None)
    else:
        return None
