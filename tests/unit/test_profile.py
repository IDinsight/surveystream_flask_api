import jsondiff
import re
from pathlib import Path
from utils import load_reference_data, logout, get_csrf_token


def test_change_password(test_user_credentials, client, login_test_user, csrf_token):
    """
    Check the change-password endpoint
    """

    new_password = "newpassword"
    old_password = test_user_credentials["password"]

    request_body = {
        "cur_password": old_password,
        "new_password": new_password,
        "confirm": new_password,
    }

    response = client.post(
        "/api/change-password",
        headers={"X-CSRF-Token": csrf_token},
        json=request_body,
    )

    assert response.status_code == 200

    logout(client)

    # GET a new CSRF token
    csrf_token = get_csrf_token(client)

    response = client.post(
        "/api/login",
        json={
            "email": test_user_credentials["email"],
            "password": new_password,
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 200


def test_change_password_mismatch(
    test_user_credentials, client, login_test_user, csrf_token
):
    """
    Check the change-password endpoint for a mismatched password
    """

    new_password = "newpassword"
    mismatch_password = "newpassword_mismatch"
    old_password = test_user_credentials["password"]

    request_body = {
        "cur_password": old_password,
        "new_password": new_password,
        "confirm": mismatch_password,
    }

    response = client.post(
        "/api/change-password",
        headers={"X-CSRF-Token": csrf_token},
        json=request_body,
    )
    assert response.status_code == 422


def test_change_password_wrong_current_password(client, login_test_user, csrf_token):
    """
    Check the change-password endpoint for a wrong current password
    """

    wrong_current_password = "wrongpassword"
    new_password = "newpassword"

    request_body = {
        "cur_password": wrong_current_password,
        "new_password": new_password,
        "confirm": new_password,
    }

    response = client.post(
        "/api/change-password",
        headers={"X-CSRF-Token": csrf_token},
        json=request_body,
    )

    assert response.status_code == 403


def test_avatar_workflow(client, login_test_user, csrf_token):
    """
    Check the methods for uploading, reading, and deleting the profile avatar
    """

    filepath = Path(__file__).resolve().parent / "data/images/airflow.png"

    request_body = {"image": (open(filepath, "rb"), "avatar.png")}

    response = client.put(
        "/api/profile/avatar",
        data=request_body,
        headers={
            "X-CSRF-Token": csrf_token,
            "Content-Disposition": 'form-data; name="file"; filename="avatar.png"',
            "Content-Type": "multipart/form-data",
        },
    )

    assert response.status_code == 200

    response = client.get("/api/profile/avatar")
    assert response.status_code == 200

    assert re.match(
        r"^https://dod-surveystream-.*-assets\.s3.amazonaws\.com/images/avatars/.*",
        response.json["image_url"],
    )

    response = client.post(
        "/api/profile/avatar/remove", headers={"X-CSRF-Token": csrf_token}
    )
    assert response.status_code == 200

    response = client.get("/api/profile/avatar")

    assert response.json["image_url"] is None


def test_avatar_incorrect_file_extension(client, login_test_user, csrf_token):
    """
    Try uploading an incorrect file extension
    """

    filepath = Path(__file__).resolve().parent / "data/images/airflow.png"

    request_body = {"image": (open(filepath, "rb"), "avatar.bmp")}

    response = client.put(
        "/api/profile/avatar",
        data=request_body,
        headers={
            "X-CSRF-Token": csrf_token,
            "Content-Disposition": 'form-data; name="file"; filename="avatar.png"',
            "Content-Type": "multipart/form-data",
        },
    )

    assert response.status_code == 422


def test_profile_response(client, login_test_user, test_user_credentials):
    """
    Check profile endpoint response
    """

    response = client.get("/api/profile")
    assert response.status_code == 200

    reference_data = load_reference_data("profile.json")
    reference_data["email"] = test_user_credentials["email"]

    checkdiff = jsondiff.diff(reference_data, response.json)

    assert checkdiff == {}


def test_profile_update(client, login_test_user, csrf_token):
    """
    Check updating the user's email
    """
    new_email = "new_email@email.com"

    request_body = {"new_email": new_email}
    response = client.patch(
        "/api/profile", headers={"X-CSRF-Token": csrf_token}, json=request_body
    )

    assert response.status_code == 200

    response = client.get("/api/profile")

    checkdiff = jsondiff.diff(
        load_reference_data("profile.json"),
        response.json,
    )

    assert checkdiff == {"email": new_email}


def test_profile_update_invalid_email(client, login_test_user, csrf_token):
    """
    Check updating the user's email
    """
    new_email = "new_email"

    request_body = {"new_email": new_email}
    response = client.patch(
        "/api/profile", headers={"X-CSRF-Token": csrf_token}, json=request_body
    )

    assert response.status_code == 422
