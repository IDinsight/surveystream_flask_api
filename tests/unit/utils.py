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
