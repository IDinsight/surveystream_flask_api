import pytest
from app import create_app, db
from passlib.hash import pbkdf2_sha256
from sqlalchemy.exc import IntegrityError
import yaml
from werkzeug.http import parse_cookie
from pathlib import Path
import flask_migrate
import os


def pytest_collection_modifyitems(config, items):
    """
    Check for tests to skip
    """

    filepath = Path(__file__).resolve().parent / "config.yml"
    with open(filepath) as file:
        settings = yaml.safe_load(file)

    if settings["run_slow_tests"]:
        # do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need run_slow_tests=True in config.yml to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


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
    filepath = Path(__file__).resolve().parent / "config.yml"
    with open(filepath) as file:
        settings = yaml.safe_load(file)

    users = {
        "core": {
            "email": settings["email"],
            "user_uid": 3933,
            "password": "asdfasdf",
            "is_super_admin": True,
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
def csrf_token(client):
    """
    Get a CSRF token for non-GET requests
    """

    # Get a CSRF token
    response = client.get("/api/get-csrf")
    assert response.status_code == 200
    cookies = response.headers.getlist("Set-Cookie")
    cookie = next((cookie for cookie in cookies if "CSRF-TOKEN" in cookie), None)
    assert cookie is not None
    cookie_attrs = parse_cookie(cookie)
    csrf_token = cookie_attrs["CSRF-TOKEN"]

    yield csrf_token


@pytest.fixture()
def login_test_user(test_user_credentials, client, csrf_token):
    """
    Log in the test user as a setup step for certain tests
    """

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

    yield


@pytest.fixture(autouse=True)
def setup_database(app, test_user_credentials, registration_user_credentials):
    """
    Set up the schema and data in the database on a per-test basis
    """

    filepath = Path(__file__).resolve().parent.parent
    with app.app_context():
        db.engine.execute("CREATE SCHEMA IF NOT EXISTS webapp;")

        if os.getenv("USE_DB_MIGRATIONS") == "true":
            flask_migrate.upgrade(directory=f"{filepath}/migrations")
        else:
            db.create_all()

        # Load general data
        db.session.execute(
            open(f"{filepath}/tests/data/launch_local_db/load_data.sql", "r").read()
        )
        db.session.commit()

        # Load permissions data with exception handling for duplicate errors
        try:
            with open(f"{filepath}/tests/data/launch_local_db/load_permissions.sql", "r") as sql_file:
                db.session.execute(sql_file.read())
            db.session.commit()
        except IntegrityError as e:
            # Handle duplicate errors gracefully
            db.session.rollback()
            print(f"Duplicate data detected. Error: {e}")

        # Set the credentials for the desired test user
        db.session.execute(
            "UPDATE webapp.users SET email=:email, password_secure=:pw_hash, is_super_admin=:is_super_admin WHERE user_uid=:user_uid",
            {
                "email": test_user_credentials["email"],
                "pw_hash": test_user_credentials["pw_hash"],
                "user_uid": test_user_credentials["user_uid"],
                "is_super_admin": test_user_credentials["is_super_admin"],
            },
        )

        db.session.commit()

        # Add the registration user
        db.session.execute(
            "INSERT INTO webapp.users (email, password_secure, is_super_admin) VALUES (:email, :pw_hash, :is_super_admin) ON CONFLICT DO NOTHING",
            {
                "email": registration_user_credentials["email"],
                "pw_hash": registration_user_credentials["pw_hash"],
                "is_super_admin": test_user_credentials["is_super_admin"],
            },
        )

        db.session.commit()

    yield

    # Clean up the database after each test
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.execute("DROP TABLE IF EXISTS alembic_version;")
