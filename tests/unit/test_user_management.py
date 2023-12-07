import json
import pytest
from app import db
from app.blueprints.user_management.models import Invite
from app.blueprints.user_management.utils import generate_invite_code, send_invite_email
from app.blueprints.auth.models import User

@pytest.fixture
def user_fixture():
    # Create a user for testing
    user = User(email="test@example.com", password="testpassword")
    db.session.add(user)
    db.session.commit()
    return user

@pytest.mark.user_management
class TestUserManagement:

    def add_user(self, client, login_test_user, csrf_token):
        response = client.post(
            "/add-user",
            json={
                "email": "newuser@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "role": "user",
            },
            headers={"X-CSRF-Token": csrf_token}
        )
        assert response.status_code == 200
        assert b"Success: user invited" in response.data

        # Return the newly created user for reuse in other tests
        return User.query.filter_by(email="newuser@example.com").first()

    def complete_registration(self, client, login_test_user, csrf_token, user):
        invite_code = generate_invite_code()
        invite = Invite(invite_code=invite_code, email=user.email, user_uid=user.user_uid, is_active=True)
        db.session.add(invite)
        db.session.commit()

        # Test completing registration
        response = client.post(
            "/complete-registration",
            json={
                "invite_code": invite_code,
                "new_password": "newpassword",
                "confirm_password": "newpassword",
            },
            headers={"X-CSRF-Token": csrf_token}
        )
        assert response.status_code == 200
        assert b"Success: registration completed" in response.data

        # Ensure the invite is inactive after completion
        updated_invite = Invite.query.get(invite.invite_uid)
        assert not updated_invite.is_active

        # Ensure the user's password is updated
        updated_user = User.query.get(user.user_uid)
        assert updated_user.verify_password("newpassword")

    def test_add_user_and_complete_registration(self, client, login_test_user, csrf_token):
        # Add a user and then complete the registration
        new_user = self.add_user(client, login_test_user, csrf_token)
        self.complete_registration(client, login_test_user, csrf_token, new_user)
    

    def test_complete_registration_invalid_invite(self, client, login_test_user, csrf_token):
        # Test completing registration with an invalid invite code
        response = client.post(
            "/complete-registration",
            json={
                "invite_code": "invalid_invite_code",
                "new_password": "newpassword",
                "confirm_password": "newpassword",
            },
            headers={"X-CSRF-Token": csrf_token}
        )
        assert response.status_code == 404
        assert b"Invalid or expired invite code" in response.data

    def test_complete_registration_inactive_invite(self, client, login_test_user, csrf_token, user_fixture):
        # Use the user_fixture to get a user for testing
        user = user_fixture

        invite_code = generate_invite_code()
        invite = Invite(invite_code=invite_code, email=user.email, user_uid=user.user_uid, is_active=False)
        db.session.add(invite)
        db.session.commit()

        # Test completing registration with an inactive invite
        response = client.post(
            "/complete-registration",
            json={
                "invite_code": invite_code,
                "new_password": "newpassword",
                "confirm_password": "newpassword",
            },
            headers={"X-CSRF-Token": csrf_token}
        )
        assert response.status_code == 404
        assert b"Invalid or expired invite code" in response.data
