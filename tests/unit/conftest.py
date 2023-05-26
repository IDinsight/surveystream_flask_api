import pytest
from app import create_app
from app import db
from passlib.hash import pbkdf2_sha256
import yaml
from werkzeug.http import parse_cookie


@pytest.fixture()
def app():
    app = create_app()
    # other setup can go here

    yield app

    # clean up / reset resources here


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


@pytest.fixture(scope="session")
def test_user_credentials():
    """
    Create credentials for the test user
    """
    with open("tests/config.yml") as file:
        settings = yaml.safe_load(file)

    users = {
        "core": {
            "email": settings["email"],
            "user_uid": 3933,
            "password": "asdfasdf",
        }
    }

    for user_type in users.keys():
        users[user_type]["pw_hash"] = pbkdf2_sha256.hash(users[user_type]["password"])

    yield users["core"]


@pytest.fixture(scope="session")
def registration_user_credentials():
    """
    Create credentials for the registration user
    """
    credentials = {
        "email": "registration_user",
        "password": "asdfasdf",
    }

    credentials["pw_hash"] = pbkdf2_sha256.hash(credentials["password"])

    yield credentials


@pytest.fixture()
def login_test_user(test_user_credentials, client):
    """
    Log in the test user as a setup step for certain tests
    """

    # Get a CSRF token
    response = client.get("/api/get-csrf")
    assert response.status_code == 200
    cookies = response.headers.getlist("Set-Cookie")
    cookie = next((cookie for cookie in cookies if "CSRF-TOKEN" in cookie), None)
    assert cookie is not None
    cookie_attrs = parse_cookie(cookie)
    csrf_token = cookie_attrs["CSRF-TOKEN"]

    # Log in the test user using the CSRF token
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

    yield csrf_token


@pytest.fixture(autouse=True)
def setup_database(app, test_user_credentials, registration_user_credentials):
    """
    Set up the schema and data in the database on a per-test basis
    """

    with app.app_context():
        db.session.execute(open("tests/db/3-web-app-schema.sql", "r").read())
        db.session.execute(open("tests/db/1-config-schema.sql", "r").read())
        db.session.execute(open("tests/data/launch_local_db/load_data.sql", "r").read())

        # Set the credentials for the desired test user
        db.session.execute(
            "UPDATE users SET email=:email, password_secure=:pw_hash WHERE user_uid=:user_uid",
            {
                "email": test_user_credentials["email"],
                "pw_hash": test_user_credentials["pw_hash"],
                "user_uid": test_user_credentials["user_uid"],
            },
        )

        db.session.commit()

        # Add the registration user
        db.session.execute(
            "INSERT INTO users (email, password_secure) VALUES (:email, :pw_hash) ON CONFLICT DO NOTHING",
            {
                "email": registration_user_credentials["email"],
                "pw_hash": registration_user_credentials["pw_hash"],
            },
        )

        db.session.commit()

    yield
