import pytest
import requests
from util import (
    get_user_secret,
    login,
    logout,
    set_user_active_status,
    get_surveys,
    register_user,
    delete_user,
    upload_avatar,
    get_avatar,
    remove_avatar,
    forgot_password,
)


client = requests.session()

APP_URL = "http://0.0.0.0:5001"
TEST_USER = get_user_secret("test-user")
USERNAME = TEST_USER["email"]
PASSWORD = TEST_USER["password"]


def try_logout():
    try:
        logout(client, APP_URL)
        client.cookies.clear()
    except:
        pass


def test_1():
    # Test 1
    # Known user; correct PASSWORD; active; currently logged out
    # Expected behavior: 200 success

    try_logout()
    set_user_active_status(USERNAME, active=True)

    response = login(client, APP_URL, USERNAME, PASSWORD)
    assert response.status_code == 200

    try_logout()


def test_2():
    # Test 2
    # Known user; correct PASSWORD; active; currently logged in
    # Expected behavior: 200 success

    try_logout()
    set_user_active_status(USERNAME, active=True)

    response = login(client, APP_URL, USERNAME, PASSWORD)
    response = login(client, APP_URL, USERNAME, PASSWORD)
    assert response.status_code == 200

    try_logout()


def test_3():
    # Test 3
    # Known user; correct PASSWORD; inactive; currently logged out
    # Expected behavior: 403 unauthorized

    try_logout()
    set_user_active_status(USERNAME, active=False)

    response = login(client, APP_URL, USERNAME, PASSWORD)

    try_logout()
    set_user_active_status(USERNAME, active=True)

    assert response.status_code == 403

def test_4():
    # Test 4
    # Known user; correct PASSWORD; inactive; currently logged in
    # Expected behavior: 401 unauthorized

    try_logout()

    response = login(client, APP_URL, USERNAME, PASSWORD)
    set_user_active_status(USERNAME, active=False)
    
    response = login(client, APP_URL, USERNAME, PASSWORD)

    try_logout()
    set_user_active_status(USERNAME, active=True)

    assert response.status_code == 403

def test_5():
    # Test 5
    # Known user; incorrect PASSWORD; active; currently logged out
    # Expected behavior: 401 unauthorized

    try_logout()
    set_user_active_status(USERNAME, active=True)

    response = login(client, APP_URL, USERNAME, "wrongpassword")
    assert response.status_code == 401

    try_logout()


def test_6():
    # Test 6
    # Known user; incorrect PASSWORD; active; currently logged in
    # Expected behavior: 401 unauthorized
    # Note: but we aren't actually logging the user out in this case so we need to test if they can still access protected endpoints

    try_logout()
    set_user_active_status(USERNAME, active=True)

    response = login(client, APP_URL, USERNAME, PASSWORD)
    response = login(client, APP_URL, USERNAME, "wrongpassword")
    assert response.status_code == 401

    try_logout()


def test_7():
    # Test 7
    # Unknown user
    # Expected behavior: 401 unauthorized

    try_logout()
    response = login(client, APP_URL, "randomuser", "somepassword")
    assert response.status_code == 401

    try_logout()


def test_8():
    # Test 8
    # Verify protected endpoints don't work if user is not logged in

    try_logout()
    response = get_surveys(client, APP_URL)
    assert response.status_code == 401

    try_logout()


def test_9():
    # Test 9
    # Verify logged in inactive user cannot access protected endpoints

    try_logout()

    response = login(client, APP_URL, USERNAME, PASSWORD)
    set_user_active_status(USERNAME, active=False)
    response = get_surveys(client, APP_URL)

    try_logout()
    set_user_active_status(USERNAME, active=True)

    assert response.status_code == 403

def test_10():
    # Test 10
    # Verify register endpoint doesn't work for non-registration user

    try_logout()
    login(client, APP_URL, USERNAME, PASSWORD)
    response = register_user(client, APP_URL, "pytestuser@asdf.com", "asdfasdf")
    assert response.status_code == 401

    try_logout()


def test_11():
    # Test 11
    # Verify register endpoint creates an active user

    registration_user_secret = get_user_secret("registration-user")
    new_user_email = "pytestuser@asdf.com"
    new_user_password = "asdfasdf"

    delete_user(new_user_email)

    try_logout()
    login(
        client,
        APP_URL,
        registration_user_secret["email"],
        registration_user_secret["password"],
    )
    response = register_user(client, APP_URL, new_user_email, new_user_password)
    assert response.status_code == 200

    try_logout()
    response = login(client, APP_URL, new_user_email, new_user_password)
    assert response.status_code == 200

    delete_user(new_user_email)


def test_12():
    # Test 12
    # Check whether the web asset S3 bucket can be accessed

    try_logout()
    login(client, APP_URL, USERNAME, PASSWORD)

    response = upload_avatar(client, APP_URL)
    assert response.status_code == 200

    response = get_avatar(client, APP_URL)

    assert response.json()["image_url"] != ""

    response = remove_avatar(client, APP_URL)
    assert response.status_code == 200

    try_logout()


def test_12():
    # Test 12
    # Checking whether email is being sent. Will use the forgot password endpoint
    # Expecting 200 but check if email is sent
    try_logout()
    response = forgot_password(client, APP_URL, USERNAME)
    assert response.status_code == 200

    try_logout()
