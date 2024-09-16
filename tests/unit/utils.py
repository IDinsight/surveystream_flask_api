import json
from pathlib import Path
from werkzeug.http import parse_cookie


def get_csrf_token(client):
    """
    Get the CSRF token
    """
    response = client.get("/api/get-csrf")
    assert response.status_code == 200
    cookies = response.headers.getlist("Set-Cookie")
    cookie = next((cookie for cookie in cookies if "CSRF-TOKEN" in cookie), None)
    assert cookie is not None
    cookie_attrs = parse_cookie(cookie)
    csrf_token = cookie_attrs["CSRF-TOKEN"]

    return csrf_token


def logout(client):
    """
    Log a user out of the app
    """
    response = client.get(
        "/api/logout",
    )
    assert response.status_code == 200
    client.delete_cookie("session")
    client.delete_cookie("remember_token")
    client.delete_cookie("CSRF-TOKEN")

    return


def update_logged_in_user_roles(
    client,
    test_user_credentials,
    roles=None,
    is_super_admin=False,
    can_create_survey=False,
    is_survey_admin=False,
    survey_uid=None,
    location_uids=None,
):
    """
    Function to update the logged-in user admin status and roles
    """
    if roles is None:
        roles = []
    csrf_token = get_csrf_token(client)
    user_uid = test_user_credentials.get("user_uid")
    response = client.put(
        f"/api/users/{user_uid}",
        json={
            "email": test_user_credentials.get("email"),
            "first_name": "Test",
            "last_name": "User",
            "roles": roles,
            "is_super_admin": is_super_admin,
            "can_create_survey": can_create_survey,
            "is_survey_admin": is_survey_admin,
            "survey_uid": survey_uid,
            "active": True,
            "location_uids": location_uids,
        },
        content_type="application/json",
        headers={"X-CSRF-Token": csrf_token},
    )
    print(response.json)
    assert response.status_code == 200
    response_data = json.loads(response.data)

    updated_user = response_data.get("user_data")

    return updated_user


def login_user(client, test_user_credentials):
    """
    Log in a user with the provided test user credentials
    """

    csrf_token = get_csrf_token(client)

    response = client.post(
        "/api/login",
        json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"],
        },
        content_type="application/json",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200


def create_new_survey_role_with_permissions(
    client, test_user_credentials, role_name, permissions, survey_uid
):
    """
    Function to update the logged-in user permissions
    - create a new role with the provided permissions, use the survey_uid provided
    - update the logged-in user with the new role
    - return updated user
    """
    csrf_token = get_csrf_token(client)
    payload = {
        "roles": [
            {
                "role_uid": None,
                "role_name": role_name,
                "reporting_role_uid": None,
                "permissions": permissions,
            },
        ]
    }

    response = client.put(
        "/api/roles",
        query_string={"survey_uid": survey_uid},
        json=payload,
        content_type="application/json",
        headers={"X-CSRF-Token": csrf_token},
    )
    print(response.json)

    assert response.status_code == 200


def create_new_survey_admin_user(
    client,
    is_super_admin=False,
    can_create_survey=True,
    is_survey_admin=False,
    survey_uid=None,
):
    csrf_token = get_csrf_token(client)
    # Add a user for testing with survey_admin roles
    response_add = client.post(
        "/api/users",
        json={
            "email": "survey_admin@example.com",
            "first_name": "Survey",
            "last_name": "Admin",
            "roles": [],
            "can_create_survey": can_create_survey,
            "is_super_admin": is_super_admin,
            "is_survey_admin": is_survey_admin,
            "survey_uid": survey_uid,
        },
        content_type="application/json",
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response_add.status_code == 200
    assert b"Success: user invited" in response_add.data
    response_data_add = json.loads(response_add.data)
    user_object = response_data_add.get("user")
    invite_object = response_data_add.get("invite")

    # Complete the registration for the added user
    response_complete = client.post(
        "/api/users/complete-registration",
        json={
            "invite_code": invite_object.get("invite_code"),
            "new_password": "newpassword",
            "confirm_password": "newpassword",
        },
        content_type="application/json",
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response_complete.status_code == 200
    assert b"Success: registration completed" in response_complete.data

    # Return email and password for later use
    return {"email": user_object.get("email"), "password": "newpassword"}


def set_user_active_status(app, db, email, active):
    """
    Set a user's active status directly in the database. Needed to set up certain tests.
    """
    if active is True or active is False:
        pass
    else:
        raise Exception("A non-boolean value was provided for 'active' parameter")
    if active:
        active_value = "t"
    else:
        active_value = "f"

    with app.app_context():
        db.session.execute(
            "UPDATE webapp.users SET active=:active_value WHERE email=:email",
            {"active_value": active_value, "email": email},
        )
        db.session.commit()


def set_target_assignable_status(app, db, target_uid, assignable):
    """
    Set a target's assignable status directly in the database. Needed to set up certain tests.
    """
    if assignable is True or assignable is False:
        pass
    else:
        raise Exception("A non-boolean value was provided for 'assignable' parameter")
    if assignable:
        assignable_value = "t"
    else:
        assignable_value = "f"

    with app.app_context():
        db.session.execute(
            "INSERT INTO webapp.target_status (target_uid, target_assignable) VALUES (:target_uid, :assignable_value) ON CONFLICT (target_uid) DO UPDATE SET target_assignable=:assignable_value",
            {"assignable_value": assignable_value, "target_uid": target_uid},
        )
        db.session.commit()


def load_reference_data(filename_stub):
    """
    Load a reference json file
    """
    filepath = (
        Path(__file__).resolve().parent
        / f"data/prepared_json_responses/{filename_stub}"
    )
    with open(filepath) as json_file:
        reference_data = json.load(json_file)

    return reference_data


def delete_user(app, db, email):
    """
    Delete a user directly in the database. Needed to set up certain tests.
    """

    with app.app_context():
        db.session.execute(
            "DELETE FROM webapp.users WHERE email=:email",
            {"email": email},
        )
        db.session.commit()
