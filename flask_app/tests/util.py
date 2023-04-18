import boto3
import base64
from botocore.exceptions import ClientError
import json
import psycopg2 as pg


from pathlib import Path


def get_csrf_header(ses, app_url):

    # Get csrf header
    csrf_url = f"{app_url}/api/get-csrf"
    csrf_response = ses.get(csrf_url)
    if csrf_response.status_code == 200:
        csrf_cookie = csrf_response.cookies["CSRF-TOKEN"]
        csrf_header = {"X-CSRF-Token": csrf_cookie}
    else:
        raise Exception(csrf_header.json()["message"])
    return csrf_header


def login(ses, app_url, username, password):

    login_url = f"{app_url}/api/login"
    request_body = {"email": username, "password": password}
    csrf_header = get_csrf_header(ses, app_url)
    response = ses.post(login_url, json=request_body, headers=csrf_header)
    return response


def logout(ses, app_url):

    logout_url = f"{app_url}/api/logout"
    csrf_header = get_csrf_header(ses, app_url)
    response = ses.post(logout_url, headers=csrf_header)
    return response


def get_surveys(ses, app_url):

    endpoint_url = f"{app_url}/api/surveys"
    response = ses.get(endpoint_url)
    return response


def upload_avatar(ses, app_url):
    endpoint_url = f"{app_url}/api/profile/avatar"
    filename = "avatar.png"
    filepath = "images/airflow.png"
    files = {
        "image": (filename, open(filepath, "rb"), "text/xml"),
        "Content-Disposition": 'form-data; name="file"; filename="' + filename + '"',
        "Content-Type": "text/xml",
    }
    csrf_header = get_csrf_header(ses, app_url)
    response = ses.put(endpoint_url, files=files, headers=csrf_header)
    return response


def remove_avatar(ses, app_url):
    endpoint_url = f"{app_url}/api/profile/avatar/remove"
    csrf_header = get_csrf_header(ses, app_url)
    response = ses.post(endpoint_url, headers=csrf_header)
    return response


def get_avatar(ses, app_url):
    endpoint_url = f"{app_url}/api/profile/avatar"
    response = ses.get(endpoint_url)
    return response


def register_user(ses, app_url, username, password):

    endpoint_url = f"{app_url}/api/register"
    request_body = {"email": username, "password": password}
    csrf_header = get_csrf_header(ses, app_url)
    response = ses.post(endpoint_url, json=request_body, headers=csrf_header)
    return response


def set_user_active_status(username, active):
    conn = get_dev_db_conn()
    cur = conn.cursor()
    if active is True or active is False:
        pass
    else:
        raise Exception("A non-boolean value was provided for 'active' parameter")
    if active:
        active_value = "t"
    else:
        active_value = "f"

    cur.execute("UPDATE users SET active=%s WHERE email=%s", (active_value, username))
    conn.commit()
    cur.close()
    conn.close()


def delete_user(username):
    conn = get_dev_db_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM users WHERE email=%s", (username,))
    conn.commit()
    cur.close()
    conn.close()


def get_user_secret(user):
    return json.loads(get_aws_secret(f"dod-surveystream-{user}", "ap-south-1"))


def get_aws_secret(secret_name, region_name):

    """
    Function to get secrets from the aws secrets manager

    """

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)
    secret = None
    # Retrieve secret
    try:

        secret_value_response = client.get_secret_value(SecretId=secret_name)

    except ClientError as e:
        if e.response["Error"]["Code"] == "DecryptionFailureException":
            raise e
        elif e.response["Error"]["Code"] == "InternalServiceErrorException":
            raise e
        elif e.response["Error"]["Code"] == "InvalidParameterException":
            raise e
        elif e.response["Error"]["Code"] == "InvalidRequestException":
            raise e
        elif e.response["Error"]["Code"] == "ResourceNotFoundException":
            raise e
        else:
            raise e
    else:
        # Decrypt secret using the associated KMS CMK
        if "SecretString" in secret_value_response:
            secret = secret_value_response["SecretString"]
        else:
            secret = base64.b64decode(secret_value_response["SecretBinary"])

    return secret


def get_dev_db_conn():

    db_secret = json.loads(get_aws_secret("data-db-connection-details", "ap-south-1"))

    PG_ENDPOINT = db_secret["host"]
    PG_DATABASE = db_secret["dbname"]
    PG_USERNAME = db_secret["username"]
    PG_PASSWORD = db_secret["password"]

    # SSH_CONFIG = read_ssh_config( "dod-airflow" )
    local_port = 5432

    try:

        conn = pg.connect(
            host="localhost",
            port=local_port,
            user=PG_USERNAME,
            password=PG_PASSWORD,
            database=PG_DATABASE,
        )
    except:
        print("Connection Has Failed...")
    return conn


def forgot_password(ses, app_url, email):
    endpoint_url = f"{app_url}/api/forgot-password"
    request_body = {"email": email}
    csrf_header = get_csrf_header(ses, app_url)
    response = ses.post(endpoint_url, headers=csrf_header, json=request_body)
    return response
