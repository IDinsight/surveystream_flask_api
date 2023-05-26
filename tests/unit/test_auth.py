from utils import set_user_active_status, logout, get_csrf_token
from app import db


def test_login_active_logged_out_user_correct_password(
    app, client, csrf_token, test_user_credentials
):
    """
    Known user; correct PASSWORD; active; currently logged out
    Expected behavior: 200 success
    """

    set_user_active_status(app, db, test_user_credentials["email"], active=True)

    response = client.post(
        "/api/login",
        json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"],
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200


def test_login_active_logged_in_user_correct_password(
    app, test_user_credentials, client, csrf_token
):
    """
    Known user; correct PASSWORD; active; currently logged in
    Expected behavior: 200 success
    """

    set_user_active_status(app, db, test_user_credentials["email"], active=True)

    client.post(
        "/api/login",
        json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"],
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    response = client.post(
        "/api/login",
        json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"],
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200


def test_login_inactive_logged_out_user_correct_password(
    app, test_user_credentials, client, csrf_token
):
    """
    Known user; correct PASSWORD; inactive; currently logged out
    Expected behavior: 403 unauthorized
    """

    set_user_active_status(app, db, test_user_credentials["email"], active=False)

    response = client.post(
        "/api/login",
        json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"],
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 403


def test_login_inactive_logged_in_user_correct_password(
    app, test_user_credentials, client, csrf_token
):
    """
    Known user; correct PASSWORD; inactive; currently logged in
    Expected behavior: 401 unauthorized
    """

    response = client.post(
        "/api/login",
        json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"],
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200

    set_user_active_status(app, db, test_user_credentials["email"], active=False)

    response = client.post(
        "/api/login",
        json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"],
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 403


def test_login_active_logged_out_user_incorrect_password(
    app, test_user_credentials, client, csrf_token
):
    """
    Known user; incorrect PASSWORD; active; currently logged out
    Expected behavior: 401 unauthorized
    """

    set_user_active_status(app, db, test_user_credentials["email"], active=True)

    response = client.post(
        "/api/login",
        json={
            "email": test_user_credentials["email"],
            "password": "wrongpassword",
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 401


def test_login_active_logged_in_user_incorrect_password(
    app, test_user_credentials, client, csrf_token
):
    """
    Known user; incorrect PASSWORD; active; currently logged in
    Expected behavior: 401 unauthorized
    Note: but we aren't actually logging the user out in this case so we need to test if they can still access protected endpoints
    """

    set_user_active_status(app, db, test_user_credentials["email"], active=True)

    client.post(
        "/api/login",
        json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"],
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    response = client.post(
        "/api/login",
        json={
            "email": test_user_credentials["email"],
            "password": "wrongpassword",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 401


def test_login_unknown_user(client, csrf_token):
    """
    Unknown user
    Expected behavior: 401 unauthorized
    """

    response = client.post(
        "/api/login",
        json={
            "email": "someuser",
            "password": "somepassword",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 401


def test_protected_endpoint_logged_out_user(client):
    """
    Verify protected endpoints don't work if user is not logged in
    """

    response = client.get("/api/surveys-list")
    assert response.status_code == 401


def test_protected_endpoint_inactive_logged_in_user(
    app, test_user_credentials, client, csrf_token
):
    """
    Verify logged in inactive user cannot access protected endpoints
    """

    response = client.post(
        "/api/login",
        json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"],
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200

    set_user_active_status(app, db, test_user_credentials["email"], active=False)

    response = client.get("/api/surveys-list")

    assert response.status_code == 403


def test_register_new_user_with_non_registration_user(
    login_test_user, client, csrf_token
):
    """Verify register endpoint doesn't work for non-registration user"""

    request_body = {"email": "pytestuser@asdf.com", "password": "asdfasdf"}
    response = client.post(
        "/api/register", json=request_body, headers={"X-CSRF-Token": csrf_token}
    )

    assert response.status_code == 401


def test_register_new_user_with_registration_user(
    registration_user_credentials, client, csrf_token
):
    """
    Verify register endpoint creates an active user
    """

    new_user_email = "pytestuser@asdf.com"
    new_user_password = "asdfasdf"

    response = client.post(
        "/api/login",
        json={
            "email": registration_user_credentials["email"],
            "password": registration_user_credentials["password"],
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200

    request_body = {"email": new_user_email, "password": new_user_password}
    response = client.post(
        "/api/register", json=request_body, headers={"X-CSRF-Token": csrf_token}
    )

    assert response.status_code == 200

    logout(client)

    # GET a new CSRF token
    csrf_token = get_csrf_token(client)

    response = client.post(
        "/api/login",
        json={
            "email": new_user_email,
            "password": new_user_password,
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 200


def test_welcome_user_with_non_registration_user(
    test_user_credentials, client, login_test_user, csrf_token
):
    """
    Verify welcome endpoint doesn't work for non-registration user
    """

    request_body = {"email": test_user_credentials["email"]}
    response = client.post(
        "/api/welcome-user",
        headers={"X-CSRF-Token": csrf_token},
        json=request_body,
    )

    assert response.status_code == 401


def test_welcome_user_with_registration_user(
    test_user_credentials, registration_user_credentials, client, csrf_token
):
    """
    Verify welcome endpoint sends an email
    Expecting 200 but need to manually verify if email is received
    """

    response = client.post(
        "/api/login",
        json={
            "email": registration_user_credentials["email"],
            "password": registration_user_credentials["password"],
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200

    request_body = {"email": test_user_credentials["email"]}
    response = client.post(
        "/api/welcome-user",
        headers={"X-CSRF-Token": csrf_token},
        json=request_body,
    )
    assert response.status_code == 200


def test_forgot_password_email(test_user_credentials, client, csrf_token):
    """
    Checking whether email is being sent. Will use the forgot password endpoint
    Expecting 200 but need to manually verify if email is received
    """

    request_body = {"email": test_user_credentials}
    response = client.post(
        "/api/forgot-password",
        headers={"X-CSRF-Token": csrf_token},
        json=request_body,
    )

    assert response.status_code == 200
