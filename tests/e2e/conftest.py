import pytest
import os
import requests
from utils import login, try_logout, get_local_db_conn
from passlib.hash import pbkdf2_sha256
import yaml


def pytest_configure(config):
    """
    Register custom markers
    """
    config.addinivalue_line("markers", "slow: mark test as slow to run")


def pytest_collection_modifyitems(config, items):
    """
    Check for tests to skip
    """
    with open("config.yml") as file:
        settings = yaml.safe_load(file)

    if settings["run_slow_tests"]:
        # do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need run_slow_tests=True in config.yml to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


@pytest.fixture(scope="session")
def base_url():
    """
    Get the base url of the Flask app
    """
    api_host = os.getenv("API_HOST")
    api_port = os.getenv("API_PORT")

    if api_host and api_port:
        base_url = f"{api_host}:{api_port}"
    else:
        base_url = "http://localhost:5001"

    yield base_url


@pytest.fixture()
def client(base_url):
    """
    Set up and teardown of the requests client
    """
    client = requests.session()
    try_logout(client, base_url)
    yield client
    try_logout(client, base_url)


@pytest.fixture(scope="session")
def test_user_credentials():
    """
    Create credentials for the test user
    """
    with open("config.yml") as file:
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
def login_test_user(test_user_credentials, client, base_url):
    """
    Log in the test user as a setup step for certain tests
    """
    login(
        client,
        base_url,
        test_user_credentials["email"],
        test_user_credentials["password"],
    )
    yield


@pytest.fixture(autouse=True)
def setup_database(test_user_credentials, registration_user_credentials):
    """
    Set up the schema and data in the database on a per-test basis
    """
    conn = get_local_db_conn()

    with conn.cursor() as cur:
        cur.execute(open("db/3-web-app-schema.sql", "r").read())
        cur.execute(open("data/launch_local_db/load_data.sql", "r").read())

        # Set the credentials for the desired test user
        cur.execute(
            "UPDATE users SET email=%s, password_secure=%s WHERE user_uid=%s",
            (
                test_user_credentials["email"],
                test_user_credentials["pw_hash"],
                test_user_credentials["user_uid"],
            ),
        )

        # Add the registration user
        cur.execute(
            "INSERT INTO users (email, password_secure) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (
                registration_user_credentials["email"],
                registration_user_credentials["pw_hash"],
            ),
        )

    conn.commit()
    conn.close()
    yield
