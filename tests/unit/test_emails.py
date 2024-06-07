from datetime import datetime, timedelta

import jsondiff
import pytest
from utils import (
    create_new_survey_role_with_permissions,
    login_user,
    update_logged_in_user_roles,
)


@pytest.mark.emails
class TestEmails:
    @pytest.fixture
    def user_with_super_admin_permissions(self, client, test_user_credentials):
        # Set the user to have super admin permissions
        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=True,
            survey_uid=1,
            is_super_admin=True,
        )
        login_user(client, test_user_credentials)

    @pytest.fixture
    def user_with_survey_admin_permissions(self, client, test_user_credentials):
        # Set the user to have survey admin permissions
        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=True,
            survey_uid=1,
            is_super_admin=False,
        )
        login_user(client, test_user_credentials)

    @pytest.fixture
    def user_with_email_permissions(self, client, test_user_credentials):
        # Assign new roles and permissions
        new_role = create_new_survey_role_with_permissions(
            # 19 - WRITE Emails
            client,
            test_user_credentials,
            "Emails Role",
            [19],
            1,
        )

        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[1],
        )

        login_user(client, test_user_credentials)

    @pytest.fixture
    def user_with_no_permissions(self, client, test_user_credentials):
        # Assign no roles and permissions
        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[],
        )

        login_user(client, test_user_credentials)

    @pytest.fixture(
        params=[
            ("user_with_super_admin_permissions", True),
            ("user_with_survey_admin_permissions", True),
            ("user_with_email_permissions", True),
            ("user_with_no_permissions", False),
        ],
        ids=[
            "super_admin_permissions",
            "survey_admin_permissions",
            "email_permissions",
            "no_permissions",
        ],
    )
    def user_permissions(self, request):
        return request.param

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
    def create_email_config(
        self, client, login_test_user, csrf_token, test_user_credentials, create_form
    ):
        """
        Insert an email config as a setup step for email tests
        """
        payload = {
            "config_type": "Assignments",
            "form_uid": 1,
            "report_users": [1, 2, 3],
            "email_source": "SurveyStream Data",
            "email_source_gsheet_key": "test_key",
            "email_source_tablename": "test_table",
            "email_source_columns": ["test_column"],
        }
        response = client.post(
            "/api/emails/config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201
        return response.json["data"]

    @pytest.fixture
    def create_email_template(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_config,
    ):
        """
        Insert email template as a setup for emails tests
        """
        payload = {
            "subject": "Test Assignments Email",
            "language": "english",
            "content": "Test Content",
            "email_config_uid": create_email_config["email_config_uid"],
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
        create_email_config,
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
            "dates": future_dates,
            "time": "20:00",
            "email_config_uid": create_email_config["email_config_uid"],
            "email_schedule_name": "Test Schedule",
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
        create_email_config,
    ):
        """
        Test fixture for creating a manual email trigger.
        """
        current_datetime = datetime.now()

        future_date = (current_datetime + timedelta(1)).strftime("%Y-%m-%d")

        payload = {
            "date": future_date,
            "time": "08:00",
            "recipients": [1, 2, 3],  # there are supposed to be enumerator ids
            "email_config_uid": create_email_config["email_config_uid"],
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

    def test_emails_create_config_exception(
        self, client, login_test_user, csrf_token, test_user_credentials, create_form
    ):
        """
        Test if exception is raised when creating configs
        """
        payload = {
            "config_type": "AejroSkv98z1pqnX6G3fT7WbL2u9Nh4kY1QcVxJld5MgP0UmwHDsIFiyCtROZBEa9Dz5jLpQZcVx8NwTm6Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8",
            "form_uid": 1,
        }
        response = client.post(
            "/api/emails/config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 500

    def test_emails_get_config(
        self,
        client,
        csrf_token,
        create_email_config,
        user_permissions,
        request,
    ):
        """
        Test getting a specific email config, with the different permissions
        Expect the email configs list or permissions denied
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            f"api/emails/config/1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": {
                    "config_type": "Assignments",
                    "email_config_uid": 1,
                    "form_uid": 1,
                    "report_users": [1, 2, 3],
                    "email_source": "SurveyStream Data",
                    "email_source_columns": ["test_column"],
                    "email_source_gsheet_key": "test_key",
                    "email_source_tablename": "test_table",
                },
                "success": True,
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: READ Emails",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_emails_get_details(
        self,
        client,
        csrf_token,
        create_email_config,
        create_email_schedule,
        create_email_template,
        create_manual_email_trigger,
        user_permissions,
        request,
    ):
        """
        Test getting all details about email configs for a particular form
        Expect the email details or permissions denied
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            f"api/emails?form_uid=1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "config_type": "Assignments",
                        "email_config_uid": 1,
                        "email_source": "SurveyStream Data",
                        "email_source_columns": ["test_column"],
                        "email_source_gsheet_key": "test_key",
                        "email_source_tablename": "test_table",
                        "form_uid": 1,
                        "report_users": [1, 2, 3],
                        "manual_triggers": [
                            {
                                "date": response.json["data"][0]["manual_triggers"][0][
                                    "date"
                                ],
                                "email_config_uid": 1,
                                "manual_email_trigger_uid": 1,
                                "recipients": [1, 2, 3],
                                "status": "queued",
                                "time": "08:00:00",
                            }
                        ],
                        "schedules": [
                            {
                                "dates": response.json["data"][0]["schedules"][0][
                                    "dates"
                                ],
                                "email_config_uid": 1,
                                "email_schedule_uid": 1,
                                "time": "20:00:00",
                                "email_schedule_name": "Test Schedule",
                            }
                        ],
                        "templates": [
                            {
                                "content": "Test Content",
                                "email_config_uid": 1,
                                "email_template_uid": 1,
                                "language": "english",
                                "subject": "Test Assignments Email",
                            }
                        ],
                    }
                ],
                "success": True,
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: READ Emails",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_emails_get_configs(
        self,
        client,
        csrf_token,
        create_email_config,
        user_permissions,
        request,
    ):
        """
        Test getting a specific form email configs, with the different permissions
        Expect the email configs list or permissions denied
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            f"api/emails/config?form_uid=1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "config_type": "Assignments",
                        "email_config_uid": 1,
                        "form_uid": 1,
                        "report_users": [1, 2, 3],
                        "email_source": "SurveyStream Data",
                        "email_source_columns": ["test_column"],
                        "email_source_gsheet_key": "test_key",
                        "email_source_tablename": "test_table",
                    }
                ],
                "success": True,
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: READ Emails",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_emails_update_config(
        self, client, csrf_token, create_email_config, user_permissions, request
    ):
        """
        Test updating emails config for different roles
        Expect newly created email config to be updated
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "email_config_uid": 1,
            "config_type": "finance",
            "form_uid": 1,
            "report_users": [1, 2, 3],
            "email_source": "SurveyStream Data",
            "email_source_gsheet_key": "test_key",
            "email_source_tablename": "test_table",
            "email_source_columns": ["test_column"],
        }

        response = client.put(
            f"api/emails/config/1",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            get_response = client.get(
                f"api/emails/config/1?form_uid=1",
                content_type="application/json",
                headers={"X-CSRF-Token": csrf_token},
            )

            print(get_response.json)

            assert get_response.status_code == 200

            checkdiff = jsondiff.diff(
                {
                    "data": {
                        **payload,
                    },
                    "success": True,
                },
                get_response.json,
            )

            assert checkdiff == {}
        else:
            assert response.status_code == 403
            expected_response = {
                "error": "User does not have the required permission: WRITE Emails",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_emails_update_config_exception(
        self,
        client,
        login_test_user,
        create_email_config,
        csrf_token,
        test_user_credentials,
        create_form,
    ):
        """
        Test if exception is raised when creating configs
        """
        payload = {
            "email_config_uid": 1,
            "config_type": "AejroSkv98z1pqnX6G3fT7WbL2u9Nh4kY1QcVxJld5MgP0UmwHDsIFiyCtROZBEa9Dz5jLpQZcVx8NwTm6Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8",
            "form_uid": 1,
        }

        response = client.put(
            f"api/emails/config/1",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 500

    def test_emails_delete_config(
        self,
        client,
        csrf_token,
        user_permissions,
        create_survey,
        create_email_config,
        request,
    ):
        """
        Test deleting emails config for different roles
        Expect config to be missing on fetch
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.delete(
            f"api/emails/config/{create_email_config['email_config_uid']}",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)

        if expected_permission:

            assert response.status_code == 200

            expected_response = {
                "success": True,
                "message": "Email config deleted successfully",
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403
            expected_response = {
                "error": "User does not have the required permission: WRITE Emails",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_emails_get_schedule(
        self, client, csrf_token, create_email_schedule, user_permissions, request
    ):
        """
        Test getting a specific  email schedule for different users
        Expect the email schedules
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            f"api/emails/schedule/{create_email_schedule['email_schedule_uid']}?email_config_uid=1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)

        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": {
                    "dates": response.json["data"]["dates"],
                    "email_config_uid": 1,
                    "email_schedule_uid": 1,
                    "time": "20:00:00",
                    "email_schedule_name": "Test Schedule",
                },
                "success": True,
            }

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}

        else:
            expected_response = {
                "error": "User does not have the required permission: READ Emails",
                "success": False,
            }

            assert response.status_code == 403

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}

    def test_emails_get_schedules(
        self, client, csrf_token, create_email_schedule, user_permissions, request
    ):
        """
        Test getting a specific config email schedules for different users
        Expect the email schedules
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            f"api/emails/schedule?email_config_uid=1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "data": [
                    {
                        "dates": response.json["data"][0]["dates"],
                        "email_config_uid": 1,
                        "email_schedule_uid": 1,
                        "time": "20:00:00",
                        "email_schedule_name": "Test Schedule",
                    }
                ],
                "success": True,
            }

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}

        else:
            expected_response = {
                "error": "User does not have the required permission: READ Emails",
                "success": False,
            }

            assert response.status_code == 403

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}

    def test_emails_create_email_schedule_exception(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_config,
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
            "dates": future_dates,
            "time": "20:00",
            "email_config_uid": 2,
            "email_schedule_name": "Test Schedule",
        }
        response = client.post(
            "/api/emails/schedule",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 500

    def test_emails_update_schedule_exception(
        self, client, csrf_token, create_email_schedule, request
    ):
        """
        Test updating emails schedule exception
        Expect newly created email schedule to be updated
        """

        current_datetime = datetime.now()

        future_dates = [
            (current_datetime + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(4)
        ]

        # add today
        future_dates.append(current_datetime.strftime("%Y-%m-%d")),

        payload = {
            "email_config_uid": 2,
            "dates": future_dates,
            "time": "08:00",
            "email_schedule_name": "Test Schedule",
        }

        response = client.put(
            f"api/emails/schedule/{create_email_schedule['email_schedule_uid']}",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 500

    def test_emails_update_schedule(
        self, client, csrf_token, create_email_schedule, user_permissions, request
    ):
        """
        Test updating emails schedule for different roles
        Expect newly created email schedule to be updated
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        current_datetime = datetime.now()

        future_dates = [
            (current_datetime + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(4)
        ]

        # add today
        future_dates.append(current_datetime.strftime("%Y-%m-%d")),

        payload = {
            "email_config_uid": 1,
            "dates": future_dates,
            "time": "08:00",
            "email_schedule_name": "Test Schedule",
        }

        response = client.put(
            f"api/emails/schedule/{create_email_schedule['email_schedule_uid']}",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)

        if expected_permission:

            expected_response = {
                "data": {
                    **payload,
                    "dates": response.json["data"]["dates"],
                    "email_config_uid": 1,
                    "time": "08:00:00",
                    "email_schedule_uid": create_email_schedule["email_schedule_uid"],
                },
                "message": "Email schedule updated successfully",
                "success": True,
            }

            assert response.status_code == 200

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )

            assert checkdiff == {}

            get_response = client.get(
                f"api/emails/schedule/{create_email_schedule['email_schedule_uid']}?email_config_uid=1",
                content_type="application/json",
                headers={"X-CSRF-Token": csrf_token},
            )

            print(get_response.json)

            assert get_response.status_code == 200

            checkdiff = jsondiff.diff(
                {
                    "data": {
                        **payload,
                        "time": get_response.json["data"]["time"],
                        "dates": get_response.json["data"]["dates"],
                        "email_schedule_uid": create_email_schedule[
                            "email_schedule_uid"
                        ],
                        "email_schedule_name": "Test Schedule",
                    },
                    "success": True,
                },
                get_response.json,
            )

            assert checkdiff == {}
        else:
            assert response.status_code == 403
            expected_response = {
                "error": "User does not have the required permission: WRITE Emails",
                "success": False,
            }

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )

            assert checkdiff == {}

    def test_emails_delete_schedule(
        self, client, csrf_token, user_permissions, request
    ):
        """
        Test deleting emails schedule for different user roles
        Expect schedule to be missing on fetch
        """

        # recreate email schedule on each run

        create_email_schedule = request.getfixturevalue("create_email_schedule")

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.delete(
            f"api/emails/schedule/{create_email_schedule['email_schedule_uid']}?email_config_uid=1",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            get_response = client.get(
                f"api/emails/schedule/{create_email_schedule['email_schedule_uid']}?email_config_uid=1",
                content_type="application/json",
                headers={"X-CSRF-Token": csrf_token},
            )
            assert get_response.status_code == 404
        else:
            assert response.status_code == 403
            expected_response = {
                "error": "User does not have the required permission: WRITE Emails",
                "success": False,
            }

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )

            assert checkdiff == {}

    def test_emails_get_manual_trigger(
        self,
        client,
        csrf_token,
        create_manual_email_trigger,
        create_form,
        user_permissions,
        request,
    ):
        """
        Test fetching email manual triggers for different user roles
        Expect newly created manual triggers
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            f"api/emails/manual-trigger/{create_manual_email_trigger['manual_email_trigger_uid']}?email_config_uid=1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)

        if expected_permission:
            expected_response = {
                "data": {
                    "date": response.json["data"]["date"],
                    "email_config_uid": 1,
                    "manual_email_trigger_uid": 1,
                    "recipients": [1, 2, 3],
                    "status": "queued",
                    "time": "08:00:00",
                },
                "success": True,
            }

            assert response.status_code == 200

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}

        else:
            expected_response = {
                "error": "User does not have the required permission: READ Emails",
                "success": False,
            }

            assert response.status_code == 403

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}

    def test_emails_create_manual_triggers_exception(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test exceptions when creating manual triggers
        """
        current_datetime = datetime.now()

        future_date = (current_datetime + timedelta(1)).strftime("%Y-%m-%d")

        payload = {
            "date": future_date,
            "time": "08:00",
            "recipients": [1, 2, 3],
            "email_config_uid": 2,  # to cause an exception
            "status": "queued",
        }

        response = client.post(
            "/api/emails/manual-trigger",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 500

    def test_emails_get_manual_triggers(
        self,
        client,
        csrf_token,
        create_manual_email_trigger,
        create_form,
        user_permissions,
        request,
    ):
        """
        Test fetching email manual triggers for different user roles
        Expect newly created manual triggers
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            f"api/emails/manual-trigger?email_config_uid=1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)

        if expected_permission:
            expected_response = {
                "data": [
                    {
                        "date": response.json["data"][0]["date"],
                        "email_config_uid": 1,
                        "manual_email_trigger_uid": 1,
                        "recipients": [1, 2, 3],
                        "status": "queued",
                        "time": "08:00:00",
                    }
                ],
                "success": True,
            }

            assert response.status_code == 200

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}

        else:
            expected_response = {
                "error": "User does not have the required permission: READ Emails",
                "success": False,
            }

            assert response.status_code == 403

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}

    def test_emails_update_manual_trigger_exception(
        self, client, csrf_token, create_manual_email_trigger, request
    ):
        """
        Test updating email manual triggers exception
        Expect 500
        """

        current_datetime = datetime.now()

        future_date = (current_datetime + timedelta(1)).strftime("%Y-%m-%d")

        data = {
            "email_config_uid": 2,  # to cause exception
            "date": future_date,
            "time": "09:00",
            "recipients": [1, 3, 2],
            "status": "sent",
        }
        response = client.put(
            f"api/emails/manual-trigger/{create_manual_email_trigger['manual_email_trigger_uid']}",
            json=data,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)

        assert response.status_code == 500

    def test_emails_update_manual_trigger(
        self, client, csrf_token, create_manual_email_trigger, user_permissions, request
    ):
        """
        Test updating email manual triggers for different user roles
        Expect newly created manual trigger to be updated
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)
        current_datetime = datetime.now()

        future_date = (current_datetime + timedelta(1)).strftime("%Y-%m-%d")

        data = {
            "email_config_uid": 1,
            "date": future_date,
            "time": "09:00",
            "recipients": [1, 3, 2],
            "status": "sent",
        }
        response = client.put(
            f"api/emails/manual-trigger/{create_manual_email_trigger['manual_email_trigger_uid']}",
            json=data,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)

        if expected_permission:

            assert response.status_code == 200

            expected_response = {
                "data": {
                    "date": response.json["data"]["date"],
                    "email_config_uid": 1,
                    "manual_email_trigger_uid": 1,
                    "recipients": [1, 3, 2],
                    "status": "sent",
                    "time": "09:00:00",
                },
                "message": "Manual email trigger updated successfully",
                "success": True,
            }

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}

            get_response = client.get(
                f"api/emails/manual-trigger/{create_manual_email_trigger['manual_email_trigger_uid']}?email_config_uid=1",
                content_type="application/json",
                headers={"X-CSRF-Token": csrf_token},
            )
            assert get_response.status_code == 200

            checkdiff = jsondiff.diff(
                {
                    "data": {
                        **data,
                        "time": get_response.json["data"]["time"],
                        "date": get_response.json["data"]["date"],
                        "manual_email_trigger_uid": create_manual_email_trigger[
                            "manual_email_trigger_uid"
                        ],
                    },
                    "success": True,
                },
                get_response.json,
            )
            assert checkdiff == {}
        else:
            expected_response = {
                "error": "User does not have the required permission: WRITE Emails",
                "success": False,
            }

            assert response.status_code == 403

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}

    def test_emails_update_manual_email_trigger_status(
        self, client, csrf_token, create_manual_email_trigger, user_permissions, request
    ):
        """
        Test updating email manual triggers for different user roles
        Expect newly created manual trigger to be updated
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)
        current_datetime = datetime.now()

        future_date = (current_datetime + timedelta(1)).strftime("%Y-%m-%d")

        data = {
            "email_config_uid": 1,
            "status": "running",
        }
        response = client.patch(
            f"api/emails/manual-trigger/{create_manual_email_trigger['manual_email_trigger_uid']}",
            json=data,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)

        if expected_permission:

            assert response.status_code == 200

            expected_response = {
                "data": {
                    "date": response.json["data"]["date"],
                    "email_config_uid": 1,
                    "manual_email_trigger_uid": 1,
                    "recipients": [1, 2, 3],
                    "status": "running",
                    "time": "08:00:00",
                },
                "message": "Manual email trigger status updated successfully",
                "success": True,
            }

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}

            get_response = client.get(
                f"api/emails/manual-trigger/{create_manual_email_trigger['manual_email_trigger_uid']}?email_config_uid=1",
                content_type="application/json",
                headers={"X-CSRF-Token": csrf_token},
            )
            assert get_response.status_code == 200

            checkdiff = jsondiff.diff(
                {
                    "data": {
                        **data,
                        "time": get_response.json["data"]["time"],
                        "recipients": [1, 2, 3],
                        "date": get_response.json["data"]["date"],
                        "manual_email_trigger_uid": create_manual_email_trigger[
                            "manual_email_trigger_uid"
                        ],
                    },
                    "success": True,
                },
                get_response.json,
            )
            assert checkdiff == {}
        else:
            expected_response = {
                "error": "User does not have the required permission: WRITE Emails",
                "success": False,
            }

            assert response.status_code == 403

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}

    def test_emails_delete_manual_trigger(
        self, client, csrf_token, create_manual_email_trigger, user_permissions, request
    ):
        """
        Test deleting email manual triggers for an admin user
        Expect newly created manual trigger to be missing after delete
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.delete(
            f"api/emails/manual-trigger/{create_manual_email_trigger['manual_email_trigger_uid']}?email_config_uid={1}",
            headers={"X-CSRF-Token": csrf_token},
        )
        if expected_permission:
            print(response.json)
            assert response.status_code == 200

            get_response = client.get(
                f"api/emails/manual-trigger/{create_manual_email_trigger['manual_email_trigger_uid']}?email_config_uid=1",
                content_type="application/json",
                headers={"X-CSRF-Token": csrf_token},
            )
            assert get_response.status_code == 404
        else:
            expected_response = {
                "error": "User does not have the required permission: WRITE Emails",
                "success": False,
            }

            assert response.status_code == 403

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}

    def test_emails_get_template(
        self, client, csrf_token, create_email_template, user_permissions, request
    ):
        """
        Test fetching a specific emails template for different user roles
        Expect the newly created email template to be found
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        email_template_uid = create_email_template["email_template_uid"]
        response = client.get(
            f"api/emails/template/{email_template_uid}?email_config_uid=1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        if expected_permission:
            expected_response = {
                "data": {
                    "content": "Test Content",
                    "email_config_uid": 1,
                    "email_template_uid": 1,
                    "language": "english",
                    "subject": "Test Assignments Email",
                },
                "success": True,
            }

            assert response.status_code == 200

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}
        else:
            expected_response = {
                "error": "User does not have the required permission: READ Emails",
                "success": False,
            }

            assert response.status_code == 403

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}

    def test_emails_create_email_template_exception(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_config,
    ):
        """
        Test create email templates exceptions
        """
        payload = {
            "subject": "Test Assignments Email",
            "language": "english",
            "content": "Test Content",
            "email_config_uid": 2,
        }
        response = client.post(
            "/api/emails/template",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 500

    def test_emails_get_templates(
        self, client, csrf_token, create_email_template, user_permissions, request
    ):
        """
        Test fetching all email templates for a specific email config
        Expect the newly created email template to be found
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            f"api/emails/template?email_config_uid=1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)

        if expected_permission:
            expected_response = {
                "data": [
                    {
                        "content": "Test Content",
                        "email_config_uid": 1,
                        "email_template_uid": 1,
                        "language": "english",
                        "subject": "Test Assignments Email",
                    }
                ],
                "success": True,
            }

            assert response.status_code == 200

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}
        else:
            expected_response = {
                "error": "User does not have the required permission: READ Emails",
                "success": False,
            }

            assert response.status_code == 403

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}

    def test_emails_update_template(
        self, client, csrf_token, create_email_template, user_permissions, request
    ):
        """
        Test updating a specific email template for different user roles
        Expect the email template to be updated
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "subject": "Test Update Email",
            "language": "Hindi",
            "content": "Test Content",
            "email_config_uid": 1,
        }
        response = client.put(
            f"/api/emails/template/{create_email_template['email_template_uid']}",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)

        if expected_permission:

            assert response.status_code == 200

            email_template_uid = create_email_template["email_template_uid"]
            get_response = client.get(
                f"api/emails/template/{email_template_uid}?email_config_uid=1",
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
        else:
            expected_response = {
                "error": "User does not have the required permission: WRITE Emails",
                "success": False,
            }

            assert response.status_code == 403

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}

    def test_emails_update_template_exception(
        self, client, csrf_token, create_email_template, request
    ):
        """
        Test updating templates exceptions
        Expect error
        """

        payload = {
            "subject": "Test Update Email",
            "language": "Hindi",
            "content": "Test Content",
            "email_config_uid": 2,  # to cause exception
        }
        response = client.put(
            f"/api/emails/template/{create_email_template['email_template_uid']}",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)

        assert response.status_code == 500

    def test_emails_delete_template(
        self, client, csrf_token, create_email_template, user_permissions, request
    ):
        """
        Test deleting a specific email template
        Expect the email template to be 404 after deleting
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.delete(
            f"/api/emails/template/{create_email_template['email_template_uid']}?email_config_uid=1",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "message": "Email template deleted successfully",
                "success": True,
            }
            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )

            assert checkdiff == {}

            email_template_uid = create_email_template["email_template_uid"]
            get_response = client.get(
                f"api/emails/template/{email_template_uid}?email_config_uid=1",
                content_type="application/json",
                headers={"X-CSRF-Token": csrf_token},
            )

            assert get_response.status_code == 404
        else:
            assert response.status_code == 403
            expected_response = {
                "error": "User does not have the required permission: WRITE Emails",
                "success": False,
            }

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )

            assert checkdiff == {}
