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
                "email": "newuser@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "role": "user",
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token}
        )
        assert response.status_code == 200
        assert b"Success: user invited" in response.data
        return User.query.filter_by(email="newuser@example.com").first()

    @pytest.fixture
    def sample_user(self, added_user):
        # Return the user added by added_user fixture as the sample_user
        return added_user
    def test_add_user_and_complete_registration(self, client, added_user, csrf_token):
        """Test adding a user and completing the registration."""
        self.complete_registration(client, added_user, csrf_token)

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

    def test_complete_registration_inactive_invite(self, client, login_test_user, csrf_token, sample_user):
        """Test completing registration with an inactive invite."""
        user = sample_user
        invite_code = generate_invite_code()
        invite = Invite(invite_code=invite_code, email=user.email, user_uid=user.user_uid, is_active=False)
        db.session.add(invite)
        db.session.commit()

        response = client.post(
            "/api/complete-registration",
            json={
                "invite_code": invite_code,
                "new_password": "newpassword",
                "confirm_password": "newpassword",
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token}
        )
        assert response.status_code == 404
        assert b"Invalid or expired invite code" in response.data

    def test_edit_user(self, client, login_test_user, csrf_token, sample_user):
        # Update user information
        response = client.put(
            f"/api/edit-user/{sample_user.user_uid}",
            json={
                "email": "updateduser@example.com",
                "first_name": "Updated",
                "last_name": "User",
                "roles": ["updated_role"],
                "is_super_admin": True,
                "permissions": ["update_permission"],
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token}
        )
        assert response.status_code == 200

        # Check if user information is updated
        updated_user = User.query.get(sample_user.user_uid)
        expected_data = {
            "email": "updateduser@example.com",
            "first_name": "Updated",
            "last_name": "User",
            "roles": ["updated_role"],
            "is_super_admin": True,
            "permissions": ["update_permission"],
        }
        assert jsondiff.diff(expected_data, updated_user.to_dict()) == {}

    def test_get_user(self, client, login_test_user, csrf_token, sample_user):
        # Retrieve information for a single user
        response = client.get(f"/api/get-user/{sample_user.user_uid}", headers={"X-CSRF-Token": csrf_token})
        assert response.status_code == 200

        # Check if the returned user data matches the expected data
        expected_data = {
            "email": "updateduser@example.com",
            "first_name": "Updated",
            "last_name": "User",
            "roles": ["updated_role"],
            "is_super_admin": True,
            "permissions": ["update_permission"],
        }
        assert jsondiff.diff(expected_data, json.loads(response.data)) == {}

    def test_get_all_users(self, client, login_test_user, csrf_token):
        # Retrieve information for all users
        response = client.get("/api/get-all-users", headers={"X-CSRF-Token": csrf_token})
        assert response.status_code == 200

        # Check if the returned data is a list of users
        users = json.loads(response.data)
        assert isinstance(users, list)

    def test_get_all_users_non_super_admin(self, client, login_test_user, csrf_token):
        # Try to retrieve information for all users as a non-super-admin (expect a 401)
        response = client.get("/get-all-users", headers={"X-CSRF-Token": csrf_token})
        assert response.status_code == 401

    def test_get_all_users_with_survey_id(self, client, login_test_user, csrf_token):
        # Try to retrieve information for all users with a survey_id (expect a 400)
        response = client.get("/get-all-users?survey_id=123", headers={"X-CSRF-Token": csrf_token})
        assert response.status_code == 400
        assert b"Survey ID is required for non-super-admin users" in response.data
