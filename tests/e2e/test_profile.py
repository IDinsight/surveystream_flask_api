import jsondiff
import re
from utils import (
    login,
    try_logout,
    upload_avatar,
    get_avatar,
    remove_avatar,
    change_password,
    update_profile,
    load_reference_data,
)


def test_change_password(base_url, test_user_credentials, client, login_test_user):
    """
    Check the change-password endpoint
    """

    new_password = "newpassword"

    response = change_password(
        client,
        base_url,
        test_user_credentials["password"],
        new_password,
        new_password,
    )
    assert response.status_code == 200

    try_logout(client, base_url)
    login(
        client,
        base_url,
        test_user_credentials["email"],
        new_password,
    )
    assert response.status_code == 200


def test_change_password_mismatch(
    base_url, test_user_credentials, client, login_test_user
):
    """
    Check the change-password endpoint for a mismatched password
    """

    new_password = "newpassword"
    mismatch_password = "newpassword_mismatch"

    response = change_password(
        client,
        base_url,
        test_user_credentials["password"],
        new_password,
        mismatch_password,
    )
    assert response.status_code == 422


def test_change_password_wrong_current_password(base_url, client, login_test_user):
    """
    Check the change-password endpoint for a wrong current password
    """

    wrong_current_password = "wrongpassword"
    new_password = "newpassword"

    response = change_password(
        client, base_url, wrong_current_password, new_password, new_password
    )
    assert response.status_code == 403


def test_avatar_workflow(base_url, client, login_test_user):
    """
    Check the methods for uploading, reading, and deleting the profile avatar
    """

    response = upload_avatar(client, base_url)
    assert response.status_code == 200

    response = get_avatar(client, base_url)

    assert re.match(
        r"^https://dod-surveystream-[a-z]*-web-app-assets\.s3.amazonaws\.com/images/avatars/.*",
        response.json()["image_url"],
    )

    response = remove_avatar(client, base_url)
    assert response.status_code == 200

    response = get_avatar(client, base_url)

    assert response.json()["image_url"] is None


def test_profile_response(base_url, client, login_test_user, test_user_credentials):
    """
    Check profile endpoint response
    """

    response = client.get(f"{base_url}/api/profile")
    assert response.status_code == 200

    reference_data = load_reference_data("profile.json")
    reference_data["email"] = test_user_credentials["email"]

    checkdiff = jsondiff.diff(reference_data, response.json())

    assert checkdiff == {}


def test_profile_update(base_url, client, login_test_user):
    """
    Check updating the user's email
    """
    new_email = "new_email@email.com"

    response = update_profile(client, base_url, new_email)
    assert response.status_code == 200

    response = client.get(f"{base_url}/api/profile")

    checkdiff = jsondiff.diff(
        load_reference_data("profile.json"),
        response.json(),
    )

    assert checkdiff == {"email": new_email}


def test_profile_update_invalid_email(base_url, client, login_test_user):
    """
    Check updating the user's email
    """
    new_email = "new_email"

    response = update_profile(client, base_url, new_email)
    assert response.status_code == 422
