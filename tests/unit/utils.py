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
            "UPDATE users SET active=:active_value WHERE email=:email",
            {"active_value": active_value, "email": email},
        )
        db.session.commit()


def delete_assignments(app, db, form_uid):
    """
    Delete all assignments directly in the database. Required as setup for certain tests.
    """
    with app.app_context():
        db.session.execute(
            "DELETE FROM surveyor_assignments WHERE target_uid IN (SELECT target_uid FROM targets WHERE form_uid=:form_uid);",
            {"form_uid": form_uid},
        )
        db.session.commit()


def reset_surveyor_status(app, db, enumerator_uid, form_uid, status):
    """
    Set a surveyor's status directly in the database. Required as setup for certain tests.
    """
    with app.app_context():
        # Set the credentials for the desired test user
        db.session.execute(
            "UPDATE surveyor_forms SET status=:status WHERE enumerator_uid=:enumerator_uid AND form_uid=:form_uid",
            {"status": status, "enumerator_uid": enumerator_uid, "form_uid": form_uid},
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
