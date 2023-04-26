from utils import (
    login,
    try_logout,
    set_user_active_status,
    get_surveys,
    register_user,
    welcome_user,
    forgot_password,
)


def test_login_active_logged_out_user_correct_password(
    base_url, test_user_credentials, client
):
    # Known user; correct PASSWORD; active; currently logged out
    # Expected behavior: 200 success

    set_user_active_status(test_user_credentials["email"], active=True)

    response = login(
        client,
        base_url,
        test_user_credentials["email"],
        test_user_credentials["password"],
    )
    assert response.status_code == 200


def test_login_active_logged_in_user_correct_password(
    base_url, test_user_credentials, client
):
    # Known user; correct PASSWORD; active; currently logged in
    # Expected behavior: 200 success

    set_user_active_status(test_user_credentials["email"], active=True)

    login(
        client,
        base_url,
        test_user_credentials["email"],
        test_user_credentials["password"],
    )

    response = login(
        client,
        base_url,
        test_user_credentials["email"],
        test_user_credentials["password"],
    )
    assert response.status_code == 200


def test_login_inactive_logged_out_user_correct_password(
    base_url, test_user_credentials, client
):
    # Known user; correct PASSWORD; inactive; currently logged out
    # Expected behavior: 403 unauthorized

    set_user_active_status(test_user_credentials["email"], active=False)

    response = login(
        client,
        base_url,
        test_user_credentials["email"],
        test_user_credentials["password"],
    )

    assert response.status_code == 403


def test_login_inactive_logged_in_user_correct_password(
    base_url, test_user_credentials, client
):
    # Known user; correct PASSWORD; inactive; currently logged in
    # Expected behavior: 401 unauthorized

    response = login(
        client,
        base_url,
        test_user_credentials["email"],
        test_user_credentials["password"],
    )
    assert response.status_code == 200

    set_user_active_status(test_user_credentials["email"], active=False)

    response = login(
        client,
        base_url,
        test_user_credentials["email"],
        test_user_credentials["password"],
    )

    assert response.status_code == 403


def test_login_active_logged_out_user_incorrect_password(
    base_url, test_user_credentials, client
):
    # Known user; incorrect PASSWORD; active; currently logged out
    # Expected behavior: 401 unauthorized

    set_user_active_status(test_user_credentials["email"], active=True)

    response = login(
        client,
        base_url,
        test_user_credentials["email"],
        "wrongpassword",
    )

    assert response.status_code == 401


def test_login_active_logged_in_user_incorrect_password(
    base_url, test_user_credentials, client
):
    # Known user; incorrect PASSWORD; active; currently logged in
    # Expected behavior: 401 unauthorized
    # Note: but we aren't actually logging the user out in this case so we need to test if they can still access protected endpoints

    set_user_active_status(test_user_credentials["email"], active=True)

    login(
        client,
        base_url,
        test_user_credentials["email"],
        test_user_credentials["password"],
    )

    response = login(
        client,
        base_url,
        test_user_credentials["email"],
        "wrongpassword",
    )
    assert response.status_code == 401


def test_login_unknown_user(base_url, client):
    # Unknown user
    # Expected behavior: 401 unauthorized

    response = login(client, base_url, "someuser", "somepassword")
    assert response.status_code == 401


def test_protected_endpoint_logged_out_user(base_url, client):
    # Verify protected endpoints don't work if user is not logged in

    response = client.get(f"{base_url}/api/surveys_list")
    assert response.status_code == 401


def test_protected_endpoint_inactive_logged_in_user(
    base_url, test_user_credentials, client
):
    # Verify logged in inactive user cannot access protected endpoints

    response = login(
        client,
        base_url,
        test_user_credentials["email"],
        test_user_credentials["password"],
    )
    assert response.status_code == 200

    set_user_active_status(test_user_credentials["email"], active=False)

    response = client.get(f"{base_url}/api/surveys_list")

    assert response.status_code == 403


def test_register_new_user_with_non_registration_user(
    base_url, test_user_credentials, client
):
    # Verify register endpoint doesn't work for non-registration user

    login(
        client,
        base_url,
        test_user_credentials["email"],
        test_user_credentials["password"],
    )
    response = register_user(client, base_url, "pytestuser@asdf.com", "asdfasdf")
    assert response.status_code == 401


def test_register_new_user_with_registration_user(
    base_url, registration_user_credentials, client
):
    # Verify register endpoint creates an active user

    new_user_email = "pytestuser@asdf.com"
    new_user_password = "asdfasdf"

    login(
        client,
        base_url,
        registration_user_credentials["email"],
        registration_user_credentials["password"],
    )
    response = register_user(client, base_url, new_user_email, new_user_password)
    assert response.status_code == 200

    try_logout(client, base_url)
    response = login(client, base_url, new_user_email, new_user_password)
    assert response.status_code == 200


def test_welcome_user_with_non_registration_user(
    base_url, test_user_credentials, client
):
    # Verify welcome endpoint doesn't work for non-registration user

    login(
        client,
        base_url,
        test_user_credentials["email"],
        test_user_credentials["password"],
    )
    response = welcome_user(client, base_url, test_user_credentials["email"])
    assert response.status_code == 401


def test_welcome_user_with_registration_user(
    base_url, test_user_credentials, registration_user_credentials, client
):
    # Verify welcome endpoint sends an email
    # Expecting 200 but need to manually verify if email is received

    login(
        client,
        base_url,
        registration_user_credentials["email"],
        registration_user_credentials["password"],
    )
    response = welcome_user(client, base_url, test_user_credentials["email"])
    assert response.status_code == 200


def test_forgot_password_email(base_url, test_user_credentials, client):
    # Test 13
    # Checking whether email is being sent. Will use the forgot password endpoint
    # Expecting 200 but need to manually verify if email is received

    response = forgot_password(client, base_url, test_user_credentials["email"])
    assert response.status_code == 200
