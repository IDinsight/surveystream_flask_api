import pytest
import jsondiff
import json


@pytest.mark.user_management
class TestUserManagement:
    @pytest.fixture
    def added_user(self, client, login_test_user, csrf_token):
        """
        Add a user for testing and return it
        """

        response = client.post(
            "/api/users",
            json={
                "email": "newuser1@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "roles": [],
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200
        assert b"Success: user invited" in response.data
        response_data = json.loads(response.data)
        user_object = response_data.get("user")
        invite_object = response_data.get("invite")

        return {"user": user_object, "invite": invite_object}

    @pytest.fixture
    def sample_user(self, added_user):
        """
        Return the user added by added_user fixture as the sample_user
        """
        return added_user.get("user")

    @pytest.fixture
    def sample_invite(self, added_user):
        """
        Return the user added by added_user fixture as the sample_user
        """
        return added_user.get("invite")

    @pytest.fixture
    def complete_registration_active_invite(
        self, client, login_test_user, csrf_token, sample_user, sample_invite
    ):
        """Test completing registration with an active invite."""

        response = client.post(
            "/api/users/complete-registration",
            json={
                "invite_code": sample_invite.get("invite_code"),
                "new_password": "newpassword",
                "confirm_password": "newpassword",
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200
        assert b"Success: registration completed" in response.data

    def test_check_user(self, client, login_test_user, csrf_token, sample_user):
        """
        Test checking user availability by email
        Expect sample_user to be available , also expect similar data
        """
        response = client.post(
            "/api/users/check-email-availability",
            json={"email": sample_user.get("email")},
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200
        assert b"User already exists" in response.data

        # Check if the returned user data matches the expected data
        expected_data = {
            "user_uid": sample_user.get("user_uid"),
            "email": sample_user.get("email"),
            "first_name": sample_user.get("first_name"),
            "last_name": sample_user.get("last_name"),
            "roles": sample_user.get("roles"),
            "is_super_admin": sample_user.get("is_super_admin"),
            "can_create_survey": False,
            "active": True,
        }
        assert response.json["user"] == expected_data

    def test_check_user_nonexistent(self, client, login_test_user, csrf_token):
        """
        Test checking user availability by email
        Expect user to be unavailable
        """
        response = client.post(
            "/api/users/check-email-availability",
            json={"email": "nonexistent@example.com"},
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 404
        assert b"User not found" in response.data

    def test_complete_registration_invalid_invite(
        self, client, login_test_user, csrf_token
    ):
        """
        Test completing registration with an invalid invite code.
        """
        response = client.post(
            "/api/users/complete-registration",
            json={
                "invite_code": "invalid_invite_code",
                "new_password": "newpassword",
                "confirm_password": "newpassword",
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 404
        assert b"Invalid or expired invite code" in response.data

    def test_complete_registration_inactive_invite(
        self,
        client,
        login_test_user,
        csrf_token,
        complete_registration_active_invite,
        sample_invite,
    ):
        """
        Test completing registration with an inactive invite.
        """

        response = client.post(
            "/api/users/complete-registration",
            json={
                # invite code should be invalid at this point
                "invite_code": sample_invite.get("invite_code"),
                "new_password": "newpassword",
                "confirm_password": "newpassword",
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 404
        assert b"Invalid or expired invite code" in response.data

    def test_get_user(self, client, sample_user, login_test_user, csrf_token):
        """
        Test endpoint for fetching user data
        Expect sample_user data
        """
        response = client.get(
            f"/api/users/{sample_user.get('user_uid')}",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        # Check if the returned user data matches the expected data
        expected_data = {
            "user_uid": sample_user.get("user_uid"),
            "email": "newuser1@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "roles": [],
            "is_super_admin": False,
            "can_create_survey": False,
            "active": True,
        }
        assert jsondiff.diff(expected_data, json.loads(response.data)) == {}

    def test_edit_user(self, client, login_test_user, csrf_token, sample_user):
        """
        Test endpoint for updating user data
        Expect sample_user data to be updated to new values
        """
        user_uid = sample_user.get("user_uid")
        response = client.put(
            f"/api/users/{user_uid}",
            json={
                "email": "updateduser@example.com",
                "first_name": "Updated",
                "last_name": "User",
                "roles": [],
                "is_super_admin": True,
                "active": True,
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Check if user information is updated
        response_data = json.loads(response.data)

        updated_user = response_data.get("user_data")

        expected_data = {
            "user_uid": user_uid,
            "email": "updateduser@example.com",
            "first_name": "Updated",
            "last_name": "User",
            "roles": [],
            "is_super_admin": True,
            "can_create_survey": False,
            "active": True,
        }
        assert jsondiff.diff(expected_data, updated_user) == {}

    def test_get_all_users(self, client, login_test_user, csrf_token):
        """
        Test endpoint for getting all users
        Expect a user list
        """
        response = client.get("/api/users", headers={"X-CSRF-Token": csrf_token})

        assert response.status_code == 200

        # Check if the returned data is a list of users
        users = json.loads(response.data)

        assert isinstance(users, list)

    def test_deactivate_user(self, client, login_test_user, csrf_token, sample_user):
        """
        Test endpoint for deactivating users
        the test uses the deactivate endpoint to deactivate a user
        then using the fetch endpoint checks if user is available
        """
        user_uid = sample_user.get("user_uid")

        response = client.delete(
            f"/api/users/{user_uid}", headers={"X-CSRF-Token": csrf_token}
        )
        assert response.status_code == 200
        assert b"User deactivated successfully" in response.data

        # Check if the deactivated user is returned by the get-user endpoint
        response_get_user = client.get(
            f"/api/users/{user_uid}", headers={"X-CSRF-Token": csrf_token}
        )
        assert response_get_user.status_code == 200
        expected_response = {
            "active": False,
            "can_create_survey": False,
            "email": "newuser1@example.com",
            "first_name": "John",
            "is_super_admin": False,
            "last_name": "Doe",
            "roles": [],
            "user_uid": 3,
        }
        checkdiff = jsondiff.diff(expected_response, response_get_user.json)
        assert checkdiff == {}
