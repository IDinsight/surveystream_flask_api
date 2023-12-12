import pytest
from app import db
from app.blueprints.user_management.models import Invite
from app.blueprints.user_management.utils import generate_invite_code, send_invite_email
from app.blueprints.auth.models import User
import jsondiff
import json



@pytest.mark.user_management
class TestUserManagement:
    @pytest.fixture
    def added_user(self, client, login_test_user, csrf_token):
        # Add a user for testing and return it
        response = client.post(
            "/api/add-user",
            json={
                "email": "newuser1@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "roles": [],
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token}
        )

        assert response.status_code == 200
        assert b"Success: user invited" in response.data
        response_data = json.loads(response.data)
        user_object = response_data.get("user")
        invite_object = response_data.get("invite")

        print(user_object)
        print(invite_object)


        return {"user": user_object, "invite":invite_object}

    @pytest.fixture
    def sample_user(self, added_user):
        # Return the user added by added_user fixture as the sample_user
        return added_user.get('user')

    @pytest.fixture
    def sample_invite(self, added_user):
        # Return the user added by added_user fixture as the sample_user
        return added_user.get('invite')
    @pytest.fixture
    def complete_registration_active_invite(self, client, login_test_user, csrf_token, sample_user, sample_invite):
        """Test completing registration with an active invite."""

        response = client.post(
            "/api/complete-registration",
            json={
                "invite_code": sample_invite.get("invite_code"),
                "new_password": "newpassword",
                "confirm_password": "newpassword",
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token}
        )

        assert response.status_code == 200
        assert b"Success: registration completed" in response.data


    def test_complete_registration_invalid_invite(self, client, login_test_user, csrf_token):
        """Test completing registration with an invalid invite code."""
        response = client.post(
            "/api/complete-registration",
            json={
                "invite_code": "invalid_invite_code",
                "new_password": "newpassword",
                "confirm_password": "newpassword",
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token}
        )
        assert response.status_code == 404
        assert b"Invalid or expired invite code" in response.data

    def test_complete_registration_inactive_invite(self, client, login_test_user, csrf_token, complete_registration_active_invite, sample_invite):
        """Test completing registration with an inactive invite."""

        response = client.post(
            "/api/complete-registration",
            json={
                "invite_code": sample_invite.get('invite_code'), ##invite code should be invalid at this point
                "new_password": "newpassword",
                "confirm_password": "newpassword",
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token}
        )
        print(response.json)
        assert response.status_code == 404
        assert b"Invalid or expired invite code" in response.data


    def test_get_user(self,client, sample_user, login_test_user, csrf_token):
        # Return the user added by added_user fixture as the sample_user
        response = client.get(f"/api/get-user/{sample_user.get('user_uid')}", headers={"X-CSRF-Token": csrf_token})

        print(response.json)

        assert response.status_code == 200

        # Check if the returned user data matches the expected data
        expected_data = {
            'user_id': sample_user.get('user_uid'),
            "email": "newuser1@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "roles": [],
            "is_super_admin": False,
        }
        assert jsondiff.diff(expected_data, json.loads(response.data)) == {}

    def test_edit_user(self, client, login_test_user, csrf_token, sample_user):
        # Update user information
        user_uid = sample_user.get('user_uid')
        response = client.put(
            f"/api/edit-user/{user_uid}",
            json={
                "email": "updateduser@example.com",
                "first_name": "Updated",
                "last_name": "User",
                "roles": [],
                "is_super_admin": True,
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token}
        )
        assert response.status_code == 200

        # Check if user information is updated
        response_data = json.loads(response.data)

        updated_user = response_data.get('user_data')

        expected_data = {
            "user_uid":user_uid,
            "email": "updateduser@example.com",
            "first_name": "Updated",
            "last_name": "User",
            "roles": [],
            "is_super_admin": True,
        }
        assert jsondiff.diff(expected_data, updated_user) == {}


    def test_get_all_users(self, client, login_test_user, csrf_token):
        # Retrieve information for all users
        response = client.get("/api/get-all-users", headers={"X-CSRF-Token": csrf_token})
        print(response.json)

        assert response.status_code == 200

        # Check if the returned data is a list of users
        users = json.loads(response.data)

        print(users)

        assert isinstance(users, list)

    # def test_get_all_users_with_survey_id(self, client, login_test_user, csrf_token):
    #     # Try to retrieve information for all users with a survey_id (expect a 400)
    #     response = client.get("/api/get-all-users?survey_id=123", headers={"X-CSRF-Token": csrf_token})
    #     print(response.json)
    #
    #     assert response.status_code == 400
    #     assert b"Survey ID is required for non-super-admin users" in response.data
