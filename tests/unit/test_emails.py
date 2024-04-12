import jsondiff
import pytest
from datetime import datetime, timedelta
from utils import (
    create_new_survey_role_with_permissions,
    login_user,
    update_logged_in_user_roles,
)


@pytest.mark.emails
class TestEmails:
    @pytest.fixture()
    def create_survey(self, client, login_test_user, csrf_token, test_user_credentials):
        """
        Insert new survey as a setup step for the form tests
        """

        payload = {
            "survey_id": "test_survey",
            "survey_name": "Test Survey",
            "survey_description": "A test survey",
            "project_name": "Test Project",
            "surveying_method": "in-person",
            "irb_approval": "Yes",
            "planned_start_date": "2021-01-01",
            "planned_end_date": "2021-12-31",
            "state": "Draft",
            "config_status": "In Progress - Configuration",
            "created_by_user_uid": test_user_credentials["user_uid"],
        }

        response = client.post(
            "/api/surveys",
            query_string={"user_uid": 3},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201

        yield

    @pytest.fixture()
    def create_form(self, client, login_test_user, csrf_token, create_survey):
        """
        Insert new form as a setup step for the form tests
        """

        payload = {
            "survey_uid": 1,
            "scto_form_id": "test_scto_input_output",
            "form_name": "Agrifieldnet Main Form",
            "tz_name": "Asia/Kolkata",
            "scto_server_name": "dod",
            "encryption_key_shared": True,
            "server_access_role_granted": True,
            "server_access_allowed": True,
            "form_type": "parent",
            "parent_form_uid": None,
            "dq_form_type": None,
        }

        response = client.post(
            "/api/forms",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201

        yield

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
        return response.json["data"]

    @pytest.fixture
    def create_email_schedule(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_template,
        create_form,
    ):
        """
        Test fixture for creating an automated email schedule.
        """
        current_datetime = datetime.now()

        future_dates = [
            (current_datetime + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(4)
        ]

        # add today

        future_dates.append(current_datetime.strftime("%Y-%m-%d")),

        payload = {
            "form_uid": 1,
            "dates": future_dates,
            "time": "20:00",
            "template_uid": create_email_template["email_template_uid"],
        }
        response = client.post(
            "/api/emails/schedule",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201
        return response.json["data"]

    @pytest.fixture
    def create_manual_email_trigger(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_template,
        create_form,
    ):
        """
        Test fixture for creating a manual email trigger.
        """
        current_datetime = datetime.now()

        future_date = (current_datetime + timedelta(1)).strftime("%Y-%m-%d")

        payload = {
            "form_uid": 1,
            "date": future_date,
            "time": "08:00",
            "recipients": [1, 2, 3],  # there are supposed to be enumerator ids
            "template_uid": create_email_template["email_template_uid"],
            "status": "queued",
        }

        response = client.post(
            "/api/emails/manual-trigger",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 201
        return response.json["data"]

    def test_get_email_template(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_template,
    ):
        email_template_uid = create_email_template["email_template_uid"]
        response = client.get(
            f"api/emails/template/{email_template_uid}",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

    def test_get_email_templates(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_template,
    ):
        response = client.get(
            f"api/emails/templates",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

    def test_update_email_template(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_template,
    ):
        payload = {
            "template_name": "Assignments",
            "subject": "Test Update Email",
            "sender_email": "test@idinsight.org",
            "content": "Test Content",
        }
        response = client.put(
            f"/api/emails/template/{create_email_template['email_template_uid']}",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        email_template_uid = create_email_template["email_template_uid"]
        get_response = client.get(
            f"api/emails/template/{email_template_uid}",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        checkdiff = jsondiff.diff(
            {
                "data": {**payload, "email_template_uid": email_template_uid},
                "success": True,
            },
            get_response.json,
        )
        assert checkdiff == {}

    def test_delete_email_template(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_template,
    ):
        response = client.delete(
            f"/api/emails/template/{create_email_template['email_template_uid']}",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

    def test_get_email_schedule_for_admin_user(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_schedule,
    ):
        response = client.get(
            f"api/emails/schedule/{create_email_schedule['email_schedule_uid']}?form_uid=1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

    def test_get_email_schedule_for_user_roles(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_schedule,
    ):
        new_role = create_new_survey_role_with_permissions(
            # 19 - WRITE Emails
            client,
            test_user_credentials,
            "Emails Role",
            [19],
            1,
        )
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[1],
        )

        login_user(client, test_user_credentials)

        response = client.get(
            f"api/emails/schedule/{create_email_schedule['email_schedule_uid']}?form_uid=1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_update_email_schedule_for_admin_user(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_template,
        create_email_schedule,
    ):

        payload = {
            "form_uid": 1,
            "dates": create_email_schedule["dates"],
            "time": "08:00",
            "template_uid": create_email_template["email_template_uid"],
        }

        response = client.put(
            f"api/emails/schedule/{create_email_schedule['email_schedule_uid']}",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        get_response = client.get(
            f"api/emails/schedule/{create_email_schedule['email_schedule_uid']}?form_uid=1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert get_response.status_code == 200

        checkdiff = jsondiff.diff(
            {
                "data": {
                    **payload,
                    "email_schedule_uid": create_email_schedule["email_schedule_uid"],
                },
                "success": True,
            },
            get_response.json,
        )
        assert checkdiff == {}

    def test_update_email_schedule_for_user_roles(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_template,
        create_email_schedule,
    ):
        new_role = create_new_survey_role_with_permissions(
            # 19 - WRITE Emails
            client,
            test_user_credentials,
            "Emails Role",
            [19],
            1,
        )
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[1],
        )

        login_user(client, test_user_credentials)

        payload = {
            "form_uid": 1,
            "dates": create_email_schedule["dates"],
            "time": "08:00",
            "template_uid": create_email_template["email_template_uid"],
        }

        response = client.put(
            f"api/emails/schedule/{create_email_schedule['email_schedule_uid']}",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        get_response = client.get(
            f"api/emails/schedule/{create_email_schedule['email_schedule_uid']}?form_uid=1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert get_response.status_code == 200

        print(get_response.json)

        checkdiff = jsondiff.diff(
            {
                "data": {
                    **payload,
                    "email_schedule_uid": create_email_schedule["email_schedule_uid"],
                },
                "success": True,
            },
            get_response.json,
        )
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_delete_email_schedule_for_admin_user(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_schedule,
    ):
        response = client.delete(
            f"api/emails/schedule/{create_email_schedule['email_schedule_uid']}?form_uid=1",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

    def test_delete_email_schedule_for_user_roles(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_schedule,
    ):
        new_role = create_new_survey_role_with_permissions(
            # 19 - WRITE Emails
            client,
            test_user_credentials,
            "Emails Role",
            [19],
            1,
        )
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[1],
        )

        login_user(client, test_user_credentials)

        response = client.delete(
            f"api/emails/schedule/{create_email_schedule['email_schedule_uid']}?form_uid=1",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_get_manual_email_trigger_for_admin_user(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_manual_email_trigger,
        create_form,
    ):
        response = client.get(
            f"api/emails/manual-trigger/{create_manual_email_trigger['manual_email_trigger_uid']}?form_uid=1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

    def test_get_manual_email_trigger_for_user_roles(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_manual_email_trigger,
        create_form,
    ):
        new_role = create_new_survey_role_with_permissions(
            # 19 - WRITE Emails
            client,
            test_user_credentials,
            "Emails Role",
            [19],
            1,
        )
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[1],
        )

        login_user(client, test_user_credentials)

        response = client.get(
            f"api/emails/manual-trigger/{create_manual_email_trigger['manual_email_trigger_uid']}?form_uid=1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_update_manual_email_trigger_for_admin_user(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_manual_email_trigger,
        create_email_template,
    ):

        current_datetime = datetime.now()

        future_date = (current_datetime + timedelta(1)).strftime("%Y-%m-%d")

        data = {
            "form_uid": 1,
            "date": future_date,
            "time": "09:00",
            "recipients": [1, 3, 2],
            "template_uid": create_email_template["email_template_uid"],
            "status": "sent",
        }
        response = client.put(
            f"api/emails/manual-trigger/{create_manual_email_trigger['manual_email_trigger_uid']}",
            json=data,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

    def test_update_manual_email_trigger_for_user_roles(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_manual_email_trigger,
        create_email_template,
    ):
        new_role = create_new_survey_role_with_permissions(
            # 19 - WRITE Emails
            client,
            test_user_credentials,
            "Emails Role",
            [19],
            1,
        )
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[1],
        )

        login_user(client, test_user_credentials)

        current_datetime = datetime.now()

        future_date = (current_datetime + timedelta(1)).strftime("%Y-%m-%d")

        data = {
            "form_uid": 1,
            "date": future_date,
            "time": "09:00",
            "recipients": [1, 3, 2],
            "template_uid": create_email_template["email_template_uid"],
            "status": "sent",
        }
        response = client.put(
            f"api/emails/manual-trigger/{create_manual_email_trigger['manual_email_trigger_uid']}",
            json=data,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_delete_manual_email_trigger_for_admin_user(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_manual_email_trigger,
    ):
        response = client.delete(
            f"api/emails/manual-trigger/{create_manual_email_trigger['manual_email_trigger_uid']}?form_uid={1}",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

    def test_delete_manual_email_trigger_for_user_roles(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_manual_email_trigger,
    ):
        new_role = create_new_survey_role_with_permissions(
            # 19 - WRITE Emails
            client,
            test_user_credentials,
            "Emails Role",
            [19],
            1,
        )
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[1],
        )

        login_user(client, test_user_credentials)

        response = client.delete(
            f"api/emails/manual-trigger/{create_manual_email_trigger['manual_email_trigger_uid']}?form_uid={1}",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)
