import jsondiff
import pytest


@pytest.mark.emails
class TestEmails:
    @pytest.fixture
    def create_email_template(
        self, client, login_test_user, csrf_token, test_user_credentials
    ):
        """
        Test fixture for creating an email template.
        """
        payload = {
            "template_name": "Assignments",
            "subject": "Test Assignments Email",
            "sender_email": "test@idinsight.org",
            "content": "Test Content",
        }
        response = client.post(
            "/api/emails/template",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201

    @pytest.fixture
    def create_email_schedule(
        self, client, login_test_user, csrf_token, test_user_credentials
    ):
        """
        Test fixture for creating an automated email schedule.
        """
        payload = {
            "form_uid": 123,
            "date": ["2024-04-11", "2024-04-12", "2024-04-13", "2024-04-14"],
            "time": "20:00",
            "template_uid": 456,
        }
        response = client.post(
            "/api/emails/schedule",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201

    @pytest.fixture
    def create_manual_email_trigger(
        self, client, login_test_user, csrf_token, test_user_credentials
    ):
        """
        Test fixture for creating a manual email trigger.
        """
        payload = {
            "form_uid": 123,
            "date": "2024-04-11",
            "time": "08:00",
            "recipients": ["recipient1@example.com", "recipient2@example.com"],
            "template_uid": 456,
            "status": "pending",
        }

        response = client.post(
            "/api/emails/manual-trigger",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 201

    def test_get_email_schedules(self, authenticated_client):
        # Assuming you have email schedules in the database
        # You might need to create some in the setup method
        response = authenticated_client.get("/schedule/123")
        assert response.status_code == 200
        # Add more assertions to check the response data if n

    def test_update_email_schedule(self, authenticated_client):
        # Assuming you have an email schedule with ID 1 in the database
        data = {
            "form_uid": 123,
            "date": "2024-04-12",
            "time": "09:00",
            "template_uid": 456,
        }
        response = authenticated_client.put("/schedule/1", json=data)
        assert response.status_code == 200
        # Add more assertions if needed

    def test_delete_email_schedule(self, authenticated_client):
        # Assuming you have an email schedule with ID 1 in the database
        response = authenticated_client.delete("/schedule/1")
        assert response.status_code == 200
        # Add more assertions if needed

    def test_create_manual_email_trigger(self, authenticated_client):
        data = {
            "form_uid": 123,
            "date": "2024-04-11",
            "time": "08:00",
            "recipients": ["recipient1@example.com", "recipient2@example.com"],
            "template_uid": 456,
            "status": "pending",
        }
        response = authenticated_client.post("/manual-trigger", json=data)
        assert response.status_code == 201

    def test_get_manual_email_trigger(self, authenticated_client):
        # Assuming you have manual email triggers in the database
        response = authenticated_client.get("/manual-triggers/123")
        assert response.status_code == 200
        # Add more assertions to check the response data if needed

    def test_update_manual_email_trigger(self, authenticated_client):
        # Assuming you have a manual email trigger with ID 1 in the database
        data = {
            "form_uid": 123,
            "date": "2024-04-12",
            "time": "09:00",
            "recipients": ["newrecipient@example.com"],
            "template_uid": 456,
            "status": "sent",
        }
        response = authenticated_client.put("/manual-trigger/1", json=data)
        assert response.status_code == 200
        # Add more assertions if needed

    def test_delete_manual_email_trigger(self, authenticated_client):
        # Assuming you have a manual email trigger with ID 1 in the database
        response = authenticated_client.delete("/manual-trigger/1")
        assert response.status_code == 200
        # Add more assertions if needed
