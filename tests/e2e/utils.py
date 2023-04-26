import boto3
import base64
from botocore.exceptions import ClientError
import json
import psycopg2 as pg
import yaml


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


def login(ses, app_url, email, password):
    login_url = f"{app_url}/api/login"
    request_body = {"email": email, "password": password}
    csrf_header = get_csrf_header(ses, app_url)
    response = ses.post(login_url, json=request_body, headers=csrf_header)
    return response


def try_logout(client, app_url):
    try:
        logout(client, app_url)
        client.cookies.clear()
    except:
        pass


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
    filepath = "data/images/airflow.png"
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


def set_test_user_details(user_uid, email, pw_hash):
    conn = get_local_db_conn()
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET email=%s, password_secure=%s WHERE user_uid=%s",
        (email, pw_hash, user_uid),
    )
    conn.commit()
    cur.close()
    conn.close()


def set_registration_user_details(email, pw_hash):
    conn = get_local_db_conn()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO users (email, password_secure) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (email, pw_hash),
    )
    conn.commit()
    cur.close()
    conn.close()


def set_user_active_status(email, active):
    conn = get_local_db_conn()
    cur = conn.cursor()
    if active is True or active is False:
        pass
    else:
        raise Exception("A non-boolean value was provided for 'active' parameter")
    if active:
        active_value = "t"
    else:
        active_value = "f"

    cur.execute("UPDATE users SET active=%s WHERE email=%s", (active_value, email))
    conn.commit()
    cur.close()
    conn.close()


def delete_user(email):
    conn = get_local_db_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM users WHERE email=%s", (email,))
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


def get_local_db_conn():
    PG_ENDPOINT = "host.docker.internal"
    PG_DATABASE = "dod"
    PG_USERNAME = "test_user"
    PG_PASSWORD = "dod"
    PORT = 5433

    conn = pg.connect(
        host=PG_ENDPOINT,
        port=PORT,
        user=PG_USERNAME,
        password=PG_PASSWORD,
        database=PG_DATABASE,
    )

    return conn


def forgot_password(ses, app_url, email):
    endpoint_url = f"{app_url}/api/forgot-password"
    request_body = {"email": email}
    csrf_header = get_csrf_header(ses, app_url)
    response = ses.post(endpoint_url, headers=csrf_header, json=request_body)
    return response


def welcome_user(ses, app_url, email):
    endpoint_url = f"{app_url}/api/welcome-user"
    request_body = {"email": email}
    csrf_header = get_csrf_header(ses, app_url)
    response = ses.post(endpoint_url, headers=csrf_header, json=request_body)
    return response


def change_password(ses, app_url, old_password, new_password, confirm_new_password):
    endpoint_url = f"{app_url}/api/change-password"
    request_body = {
        "cur_password": old_password,
        "new_password": new_password,
        "confirm": confirm_new_password,
    }
    csrf_header = get_csrf_header(ses, app_url)
    response = ses.post(endpoint_url, headers=csrf_header, json=request_body)
    return response


def update_profile(ses, app_url, new_email):
    endpoint_url = f"{app_url}/api/profile"
    request_body = {"new_email": new_email}
    csrf_header = get_csrf_header(ses, app_url)
    response = ses.patch(endpoint_url, headers=csrf_header, json=request_body)
    return response


def delete_assignments(form_uid):
    conn = get_local_db_conn()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM surveyor_assignments WHERE target_uid IN (SELECT target_uid FROM targets WHERE form_uid=%s);",
        (form_uid,),
    )

    conn.commit()
    cur.close()
    conn.close()


def assign_targets(ses, app_url, assignments_payload):
    endpoint_url = f"{app_url}/api/assignments"
    request_body = assignments_payload
    csrf_header = get_csrf_header(ses, app_url)
    response = ses.put(endpoint_url, headers=csrf_header, json=request_body)
    return response


def update_surveyor_status(ses, app_url, enumerator_uid, form_uid, status):
    endpoint_url = f"{app_url}/api/enumerators/{enumerator_uid}"
    request_body = {"form_uid": form_uid, "status": status}
    csrf_header = get_csrf_header(ses, app_url)
    response = ses.patch(endpoint_url, headers=csrf_header, json=request_body)
    return response


def reset_surveyor_status(enumerator_uid, form_uid, status):
    conn = get_local_db_conn()
    cur = conn.cursor()

    cur.execute(
        "UPDATE surveyor_forms SET status=%s WHERE enumerator_uid=%s AND form_uid=%s",
        (status, enumerator_uid, form_uid),
    )

    conn.commit()
    cur.close()
    conn.close()


def load_reference_data(filename_stub):
    with open(f"data/prepared_json_responses/{filename_stub}") as json_file:
        reference_data = json.load(json_file)

    return reference_data
