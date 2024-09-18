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
            "config_name": "Assignments",
            "form_uid": 1,
            "report_users": [1, 2, 3],
            "email_source": "Google Sheet",
            "email_source_gsheet_link": "https://docs.google.com/spreadsheets/d/1JTYpHS1zVZq2cUH9_dSOGt-tDLCc8qMYWXfC1VRUJYU/edit?gid=0#gid=0",
            "email_source_gsheet_tab": "Test_Success",
            "email_source_gsheet_header_row": 1,
            "email_source_tablename": "test_table",
            "email_source_columns": ["test_column"],
            "cc_users": [1, 2, 3],
            "pdf_attachment": True,
            "pdf_encryption": True,
            "pdf_encryption_password_type": "Pattern",
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
            "variable_list": [],
            "table_list": [
                {
                    "table_name": "test_table",
                    "column_mapping": {
                        "test_column1": "TEST Column 1",
                        "test_column2": "TEST Column 2",
                    },
                    "sort_list": {"test_column1": "asc", "test_column2": "desc"},
                    "variable_name": "test_table+_1",
                    "filter_list": [
                        {
                            "filter_group": [
                                {
                                    "table_name": "test_table",
                                    "filter_variable": "test_column",
                                    "filter_operator": "Is",
                                    "filter_value": "test_value",
                                },
                                {
                                    "table_name": "test_table",
                                    "filter_variable": "test_column2",
                                    "filter_operator": "Is",
                                    "filter_value": "test_value2",
                                },
                            ]
                        },
                        {
                            "filter_group": [
                                {
                                    "table_name": "test_table",
                                    "filter_variable": "test_column",
                                    "filter_operator": "Is",
                                    "filter_value": "test_value",
                                },
                                {
                                    "table_name": "test_table",
                                    "filter_variable": "test_column2",
                                    "filter_operator": "Is not",
                                    "filter_value": "test_value2",
                                },
                            ]
                        },
                    ],
                }
            ],
        }
        response = client.post(
            "/api/emails/template",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 201
        print(response.json)
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
            "config_name": "AejroSkv98z1pqnX6G3fT7WbL2u9Nh4kY1QcVxJld5MgP0UmwHDsIFiyCtROZBEa9Dz5jLpQZcVx8NwTm6Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8Sc1Mw7Ln2Kg3Fh2Bv4Uq9Zy8Wx5Lk3Jc7Gp4Zb9Ah2Dm6Fn5Oe4Vx8",
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
                    "config_name": "Assignments",
                    "email_config_uid": 1,
                    "form_uid": 1,
                    "report_users": [1, 2, 3],
                    "email_source": "Google Sheet",
                    "email_source_columns": [
                        "test_column",
                        "Surveyor Name",
                        "Surveyor Email",
                        "Surveyor Language",
                        "Surveyor ID",
                        "Assignment Date",
                        "Survey Name",
                        "Schedule Name",
                        "Config Name",
                        "SCTO Form ID",
                    ],
                    "email_source_gsheet_link": "https://docs.google.com/spreadsheets/d/1JTYpHS1zVZq2cUH9_dSOGt-tDLCc8qMYWXfC1VRUJYU/edit?gid=0#gid=0",
                    "email_source_gsheet_tab": "Test_Success",
                    "email_source_gsheet_header_row": 1,
                    "email_source_tablename": "test_table",
                    "cc_users": [1, 2, 3],
                    "pdf_attachment": True,
                    "pdf_encryption": True,
                    "pdf_encryption_password_type": "Pattern",
                },
                "success": True,
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            print(expected_response)
            print(response.json)
            print(checkdiff)
            assert checkdiff == {}
        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: READ Emails",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_fetch_email_google_sheet_columns(
        self,
        client,
        csrf_token,
        create_email_config,
        user_permissions,
        request,
    ):
        """
        Test: Fetching google sheet columns for a sheet that exists
        Expect: The columns to be returned or permissions denied
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "form_uid": 1,
            "email_source_gsheet_link": "https://docs.google.com/spreadsheets/d/1JTYpHS1zVZq2cUH9_dSOGt-tDLCc8qMYWXfC1VRUJYU/edit?gid=1838473014#gid=1838473014",
            "email_source_gsheet_tab": "Test_Success",
            "email_source_gsheet_header_row": 1,
        }
        response = client.post(
            "/api/emails/gsheet",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": ["column1", "column2", "column3"],
                "success": True,
                "message": "Google Sheet column Headers retrieved successfully",
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

    def test_fetch_email_google_sheet_columns_no_sheet_permissions(
        self,
        client,
        csrf_token,
        create_email_config,
        user_permissions,
        request,
    ):
        """
        Test: Fetching google sheet columns for a sheet that exists but dont have permissions on Gsheet
        Expect: 403 Error with message to grant permission on sheet
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "form_uid": 1,
            "email_source_gsheet_link": "https://docs.google.com/spreadsheets/d/1hwQeG349NjFsaII_BYgXMY9zS_qOTKMrqLfo2jTisTY/edit?gid=0#gid=0",
            "email_source_gsheet_tab": "Test_Success",
            "email_source_gsheet_header_row": 1,
        }
        response = client.post(
            "/api/emails/gsheet",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        if expected_permission:
            assert response.status_code == 403
        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: READ Emails",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_fetch_email_google_sheet_columns_no_sheet_exists(
        self,
        client,
        csrf_token,
        create_email_config,
        user_permissions,
        request,
    ):
        """T
        Test: Fetching google sheet columns for a sheet that doesnt exist
        Expect: Error 404 with message that sheet does not exist
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "form_uid": 1,
            "email_source_gsheet_link": "https://docs.google.com/spreadsheets/d/1hwQeG349NjFsaII_Bdummy_dummy_dummy_dummy/",
            "email_source_gsheet_tab": "dummy",
            "email_source_gsheet_header_row": 1,
        }
        response = client.post(
            "/api/emails/gsheet",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            assert response.status_code == 404
        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: READ Emails",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_update_email_google_sheet_columns(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_config,
    ):
        """
        Test: Updating google sheet columns for congig that exists in db
        Expect: The columns to be returned or permissions denied
        """

        payload = {"email_config_uid": create_email_config["email_config_uid"]}
        response = client.patch(
            "/api/emails/gsheet",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200
        expected_response = {
            "data": ["column1", "column2", "column3"],
            "success": True,
            "message": "Email Source Columns updated successfully",
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_fetch_email_google_sheet_columns_blanksheet(
        self,
        client,
        csrf_token,
        create_email_config,
        user_permissions,
        request,
    ):
        """
        Test: Fetching google sheet columns for a sheet that exists but has no data
        Expect: Empty list of columns to be returned or permissions denied
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "form_uid": 1,
            "email_source_gsheet_link": "https://docs.google.com/spreadsheets/d/1JTYpHS1zVZq2cUH9_dSOGt-tDLCc8qMYWXfC1VRUJYU/edit?gid=1838473014#gid=1838473014",
            "email_source_gsheet_tab": "Test_BlankException",
            "email_source_gsheet_header_row": 100,
        }
        response = client.post(
            "/api/emails/gsheet",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": [],
                "success": True,
                "message": "Google Sheet column Headers retrieved successfully",
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
                        "config_name": "Assignments",
                        "email_config_uid": 1,
                        "email_source": "Google Sheet",
                        "email_source_columns": [
                            "test_column",
                        ],
                        "email_source_gsheet_link": "https://docs.google.com/spreadsheets/d/1JTYpHS1zVZq2cUH9_dSOGt-tDLCc8qMYWXfC1VRUJYU/edit?gid=0#gid=0",
                        "email_source_gsheet_tab": "Test_Success",
                        "email_source_gsheet_header_row": 1,
                        "email_source_tablename": "test_table",
                        "cc_users": [1, 2, 3],
                        "pdf_attachment": True,
                        "pdf_encryption": True,
                        "pdf_encryption_password_type": "Pattern",
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
                                "filter_list": [],
                            }
                        ],
                        "templates": [
                            {
                                "content": "Test Content",
                                "email_config_uid": 1,
                                "email_template_uid": 1,
                                "language": "english",
                                "subject": "Test Assignments Email",
                                "variable_list": [],
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
                        "config_name": "Assignments",
                        "email_config_uid": 1,
                        "form_uid": 1,
                        "report_users": [1, 2, 3],
                        "email_source": "Google Sheet",
                        "email_source_columns": [
                            "test_column",
                            "Surveyor Name",
                            "Surveyor Email",
                            "Surveyor Language",
                            "Surveyor ID",
                            "Assignment Date",
                            "Survey Name",
                            "Schedule Name",
                            "Config Name",
                            "SCTO Form ID",
                        ],
                        "email_source_gsheet_link": "https://docs.google.com/spreadsheets/d/1JTYpHS1zVZq2cUH9_dSOGt-tDLCc8qMYWXfC1VRUJYU/edit?gid=0#gid=0",
                        "email_source_gsheet_tab": "Test_Success",
                        "email_source_gsheet_header_row": 1,
                        "email_source_tablename": "test_table",
                        "cc_users": [1, 2, 3],
                        "pdf_attachment": True,
                        "pdf_encryption": True,
                        "pdf_encryption_password_type": "Pattern",
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
            "config_name": "finance",
            "form_uid": 1,
            "report_users": [1, 2, 3],
            "email_source": "SurveyStream Data",
            "email_source_gsheet_link": "https://docs.google.com/spreadsheets/d/1JTYpHS1zVZq2cUH9_dSOGt-tDLCc8qMYWXfC1VRUJYU/edit?gid=0#gid=0",
            "email_source_gsheet_tab": "Test_Success",
            "email_source_gsheet_header_row": 1,
            "email_source_tablename": "test_table",
            "email_source_columns": ["test_column", "test_column2"],
            "cc_users": [1, 2, 3],
            "pdf_attachment": True,
            "pdf_encryption": True,
            "pdf_encryption_password_type": "Password",
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

            expected_response = {
                "data": {
                    "cc_users": [1, 2, 3],
                    "config_name": "finance",
                    "email_config_uid": 1,
                    "email_source": "SurveyStream Data",
                    "email_source_columns": [
                        "test_column",
                        "test_column2",
                        "Surveyor Name",
                        "Surveyor Email",
                        "Surveyor Language",
                        "Surveyor ID",
                        "Assignment Date",
                        "Survey Name",
                        "Schedule Name",
                        "Config Name",
                        "SCTO Form ID",
                    ],
                    "email_source_gsheet_header_row": 1,
                    "email_source_gsheet_link": "https://docs.google.com/spreadsheets/d/1JTYpHS1zVZq2cUH9_dSOGt-tDLCc8qMYWXfC1VRUJYU/edit?gid=0#gid=0",
                    "email_source_gsheet_tab": "Test_Success",
                    "email_source_tablename": "test_table",
                    "form_uid": 1,
                    "pdf_attachment": True,
                    "pdf_encryption": True,
                    "pdf_encryption_password_type": "Password",
                    "report_users": [1, 2, 3],
                },
                "success": True,
            }

            checkdiff = jsondiff.diff(
                expected_response,
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
        csrf_token,
        user_permissions,
        create_survey,
        create_email_config,
        request,
    ):
        """
        Test if exception is raised when creating configs
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "email_config_uid": 1,
            "config_name": None,
            "form_uid": 1,
        }

        response = client.put(
            f"api/emails/config/1",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 422

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

    def test_emails_create_email_config_non_encrypted_attachment(
        self,
        client,
        csrf_token,
        user_permissions,
        create_email_config,
        request,
    ):
        """
        Create an email config for encryptred email with no password
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "config_name": "Assignments_attachment",
            "form_uid": 1,
            "report_users": [1, 2, 3],
            "email_source": "SurveyStream Data",
            "email_source_gsheet_link": "https://docs.google.com/spreadsheets/d/1JTYpHS1zVZq2cUH9_dSOGt-tDLCc8qMYWXfC1VRUJYU/edit?gid=0#gid=0",
            "email_source_gsheet_tab": "Test_Success",
            "email_source_gsheet_header_row": 1,
            "email_source_tablename": "test_table",
            "email_source_columns": ["test_column"],
            "cc_users": [1, 2, 3],
            "pdf_attachment": True,
            "pdf_encryption": False,
        }
        response = client.post(
            "/api/emails/config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        if expected_permission:
            assert response.status_code == 201
            expected_response = {
                "data": {
                    "config_name": "Assignments_attachment",
                    "email_config_uid": 2,
                    "form_uid": 1,
                    "report_users": [1, 2, 3],
                    "email_source": "SurveyStream Data",
                    "email_source_columns": [
                        "test_column",
                    ],
                    "email_source_gsheet_link": "https://docs.google.com/spreadsheets/d/1JTYpHS1zVZq2cUH9_dSOGt-tDLCc8qMYWXfC1VRUJYU/edit?gid=0#gid=0",
                    "email_source_gsheet_tab": "Test_Success",
                    "email_source_gsheet_header_row": 1,
                    "email_source_tablename": "test_table",
                    "cc_users": [1, 2, 3],
                    "pdf_attachment": True,
                    "pdf_encryption": False,
                    "pdf_encryption_password_type": None,
                },
                "message": "Email Config created successfully",
                "success": True,
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
                    "filter_list": [],
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
                        "filter_list": [],
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
                        "filter_list": [],
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

    def test_emails_update_schedule_with_filters(
        self, client, csrf_token, create_email_schedule, user_permissions, request
    ):
        """
        Test updating emails schedule with filters for different roles
        Expect newly created email schedule to be updated
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        current_datetime = datetime.now().date()

        future_dates = [
            (current_datetime + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(4)
        ]

        expected_response_dates = [
            (current_datetime + timedelta(days=i)).strftime("%a, %d %b %Y %H:%M:%S GMT")
            for i in range(4)
        ]

        payload = {
            "email_config_uid": 1,
            "dates": future_dates,
            "time": "08:00",
            "email_schedule_name": "Test Schedule",
            "filter_list": [
                {
                    "filter_group": [
                        {
                            "table_name": "test_table",
                            "filter_variable": "test_column",
                            "filter_operator": "Is",
                            "filter_value": "test_value",
                        },
                        {
                            "table_name": "test_table",
                            "filter_variable": "test_column2",
                            "filter_operator": "Is",
                            "filter_value": "test_value2",
                        },
                    ]
                },
                {
                    "filter_group": [
                        {
                            "table_name": "test_table",
                            "filter_variable": "test_column",
                            "filter_operator": "Is",
                            "filter_value": "test_value",
                        },
                        {
                            "table_name": "test_table",
                            "filter_variable": "test_column2",
                            "filter_operator": "Is not",
                            "filter_value": "test_value2",
                        },
                    ]
                },
            ],
        }

        response = client.put(
            f"api/emails/schedule/{create_email_schedule['email_schedule_uid']}",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:

            assert response.status_code == 200

            expected_response = {
                "data": {
                    "dates": expected_response_dates,
                    "email_config_uid": 1,
                    "email_schedule_name": "Test Schedule",
                    "email_schedule_uid": 1,
                    "time": "08:00:00",
                },
                "message": "Email schedule updated successfully",
                "success": True,
            }
            print("Response ", response.json)
            print("Expected Response ", expected_response)
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

            print("Get Response", get_response.json)

            assert get_response.status_code == 200

            checkdiff = jsondiff.diff(
                {
                    "data": {
                        "time": "08:00:00",
                        "dates": expected_response_dates,
                        "email_schedule_uid": create_email_schedule[
                            "email_schedule_uid"
                        ],
                        "email_config_uid": 1,
                        "email_schedule_name": "Test Schedule",
                        "filter_list": [
                            {
                                "filter_group": [
                                    {
                                        "email_schedule_uid": create_email_schedule[
                                            "email_schedule_uid"
                                        ],
                                        "filter_group_id": 1,
                                        "table_name": "test_table",
                                        "filter_variable": "test_column",
                                        "filter_operator": "Is",
                                        "filter_value": "test_value",
                                    },
                                    {
                                        "email_schedule_uid": create_email_schedule[
                                            "email_schedule_uid"
                                        ],
                                        "filter_group_id": 1,
                                        "table_name": "test_table",
                                        "filter_variable": "test_column2",
                                        "filter_operator": "Is",
                                        "filter_value": "test_value2",
                                    },
                                ]
                            },
                            {
                                "filter_group": [
                                    {
                                        "email_schedule_uid": create_email_schedule[
                                            "email_schedule_uid"
                                        ],
                                        "filter_group_id": 2,
                                        "table_name": "test_table",
                                        "filter_variable": "test_column",
                                        "filter_operator": "Is",
                                        "filter_value": "test_value",
                                    },
                                    {
                                        "email_schedule_uid": create_email_schedule[
                                            "email_schedule_uid"
                                        ],
                                        "filter_group_id": 2,
                                        "table_name": "test_table",
                                        "filter_variable": "test_column2",
                                        "filter_operator": "Is not",
                                        "filter_value": "test_value2",
                                    },
                                ]
                            },
                        ],
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

    def test_emails_create_schedule_with_filters(
        self, client, csrf_token, create_email_schedule, user_permissions, request
    ):
        """
        Test creating emails schedule with filters for different roles
        Expect newly created email schedule to be updated
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        current_datetime = datetime.now().date()

        future_dates = [
            (current_datetime + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(4)
        ]

        expected_response_dates = [
            (current_datetime + timedelta(days=i)).strftime("%a, %d %b %Y %H:%M:%S GMT")
            for i in range(4)
        ]

        payload = {
            "email_config_uid": 1,
            "dates": future_dates,
            "time": "08:00",
            "email_schedule_name": "Test Schedule_2",
            "filter_list": [
                {
                    "filter_group": [
                        {
                            "table_name": "test_table",
                            "filter_variable": "test_column",
                            "filter_operator": "Is",
                            "filter_value": "test_value",
                        },
                        {
                            "table_name": "test_table",
                            "filter_variable": "test_column2",
                            "filter_operator": "Is",
                            "filter_value": "test_value2",
                        },
                    ]
                },
                {
                    "filter_group": [
                        {
                            "table_name": "test_table",
                            "filter_variable": "test_column",
                            "filter_operator": "Is",
                            "filter_value": "test_value",
                        },
                        {
                            "table_name": "test_table",
                            "filter_variable": "test_column2",
                            "filter_operator": "Is not",
                            "filter_value": "test_value2",
                        },
                    ]
                },
            ],
        }

        response = client.post(
            f"api/emails/schedule",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print("Response ", response.json)

        if expected_permission:

            assert response.status_code == 201

            expected_response = {
                "data": {
                    "dates": expected_response_dates,
                    "email_config_uid": 1,
                    "email_schedule_name": "Test Schedule_2",
                    "email_schedule_uid": 2,
                    "time": "08:00:00",
                },
                "message": "Email schedule created successfully",
                "success": True,
            }
            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )

            assert checkdiff == {}

            get_response = client.get(
                f"api/emails/schedule?email_config_uid=1",
                content_type="application/json",
                headers={"X-CSRF-Token": csrf_token},
            )

            print("Get Response", get_response.json)

            assert get_response.status_code == 200

            checkdiff = jsondiff.diff(
                {
                    "data": [
                        {
                            "dates": expected_response_dates,
                            "email_config_uid": 1,
                            "email_schedule_name": "Test Schedule",
                            "email_schedule_uid": 1,
                            "filter_list": [],
                            "time": "20:00:00",
                        },
                        {
                            "time": "08:00:00",
                            "dates": expected_response_dates,
                            "email_schedule_uid": 2,
                            "email_config_uid": 1,
                            "email_schedule_name": "Test Schedule_2",
                            "filter_list": [
                                {
                                    "filter_group": [
                                        {
                                            "email_schedule_uid": 2,
                                            "filter_group_id": 1,
                                            "table_name": "test_table",
                                            "filter_variable": "test_column",
                                            "filter_operator": "Is",
                                            "filter_value": "test_value",
                                        },
                                        {
                                            "email_schedule_uid": 2,
                                            "filter_group_id": 1,
                                            "table_name": "test_table",
                                            "filter_variable": "test_column2",
                                            "filter_operator": "Is",
                                            "filter_value": "test_value2",
                                        },
                                    ]
                                },
                                {
                                    "filter_group": [
                                        {
                                            "email_schedule_uid": 2,
                                            "filter_group_id": 2,
                                            "table_name": "test_table",
                                            "filter_variable": "test_column",
                                            "filter_operator": "Is",
                                            "filter_value": "test_value",
                                        },
                                        {
                                            "email_schedule_uid": 2,
                                            "filter_group_id": 2,
                                            "table_name": "test_table",
                                            "filter_variable": "test_column2",
                                            "filter_operator": "Is not",
                                            "filter_value": "test_value2",
                                        },
                                    ]
                                },
                            ],
                        },
                    ],
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
                    "table_list": [
                        {
                            "column_mapping": {
                                "test_column1": "TEST Column 1",
                                "test_column2": "TEST Column 2",
                            },
                            "email_template_table_uid": 1,
                            "filter_list": [
                                [
                                    {
                                        "email_template_table_uid": 1,
                                        "filter_group_id": 1,
                                        "filter_operator": "Is",
                                        "filter_value": "test_value",
                                        "filter_variable": "test_column",
                                    },
                                    {
                                        "email_template_table_uid": 1,
                                        "filter_group_id": 1,
                                        "filter_operator": "Is",
                                        "filter_value": "test_value2",
                                        "filter_variable": "test_column2",
                                    },
                                ],
                                [
                                    {
                                        "email_template_table_uid": 1,
                                        "filter_group_id": 2,
                                        "filter_operator": "Is",
                                        "filter_value": "test_value",
                                        "filter_variable": "test_column",
                                    },
                                    {
                                        "email_template_table_uid": 1,
                                        "filter_group_id": 2,
                                        "filter_operator": "Is not",
                                        "filter_value": "test_value2",
                                        "filter_variable": "test_column2",
                                    },
                                ],
                            ],
                            "sort_list": {
                                "test_column1": "asc",
                                "test_column2": "desc",
                            },
                            "table_name": "test_table",
                            "variable_name": "test_table+_1",
                        }
                    ],
                    "variable_list": [],
                },
                "success": True,
            }

            assert response.status_code == 200

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            print(checkdiff)
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
                        "table_list": [
                            {
                                "column_mapping": {
                                    "test_column1": "TEST Column 1",
                                    "test_column2": "TEST Column 2",
                                },
                                "email_template_table_uid": 1,
                                "filter_list": [
                                    [
                                        {
                                            "email_template_table_uid": 1,
                                            "filter_group_id": 1,
                                            "filter_operator": "Is",
                                            "filter_value": "test_value",
                                            "filter_variable": "test_column",
                                        },
                                        {
                                            "email_template_table_uid": 1,
                                            "filter_group_id": 1,
                                            "filter_operator": "Is",
                                            "filter_value": "test_value2",
                                            "filter_variable": "test_column2",
                                        },
                                    ],
                                    [
                                        {
                                            "email_template_table_uid": 1,
                                            "filter_group_id": 2,
                                            "filter_operator": "Is",
                                            "filter_value": "test_value",
                                            "filter_variable": "test_column",
                                        },
                                        {
                                            "email_template_table_uid": 1,
                                            "filter_group_id": 2,
                                            "filter_operator": "Is not",
                                            "filter_value": "test_value2",
                                            "filter_variable": "test_column2",
                                        },
                                    ],
                                ],
                                "sort_list": {
                                    "test_column1": "asc",
                                    "test_column2": "desc",
                                },
                                "table_name": "test_table",
                                "variable_name": "test_table+_1",
                            }
                        ],
                        "variable_list": [],
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

    def test_emails_bulk_create_templates(
        self, client, csrf_token, create_email_config, user_permissions, request
    ):
        """
        Test uploading multiple email template for different user roles
        Expect the email template to be updated
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "email_config_uid": create_email_config["email_config_uid"],
            "templates": [
                {
                    "subject": "Test Assignments Email",
                    "language": "english",
                    "content": "Test Content",
                    "variable_list": [],
                    "table_list": [
                        {
                            "table_name": "test_table",
                            "column_mapping": {
                                "test_column1": "TEST Column 1",
                                "test_column2": "TEST Column 2",
                            },
                            "sort_list": {
                                "test_column1": "asc",
                                "test_column2": "desc",
                            },
                            "variable_name": "test_table+_1",
                            "filter_list": [
                                {
                                    "filter_group": [
                                        {
                                            "table_name": "test_table",
                                            "filter_variable": "test_column",
                                            "filter_operator": "Is",
                                            "filter_value": "test_value",
                                        },
                                        {
                                            "table_name": "test_table",
                                            "filter_variable": "test_column2",
                                            "filter_operator": "Is",
                                            "filter_value": "test_value2",
                                        },
                                    ]
                                },
                                {
                                    "filter_group": [
                                        {
                                            "table_name": "test_table",
                                            "filter_variable": "test_column",
                                            "filter_operator": "Is",
                                            "filter_value": "test_value",
                                        },
                                        {
                                            "table_name": "test_table",
                                            "filter_variable": "test_column2",
                                            "filter_operator": "Is not",
                                            "filter_value": "test_value2",
                                        },
                                    ]
                                },
                            ],
                        }
                    ],
                },
                {
                    "subject": "Test Assignments Email",
                    "language": "hindi",
                    "content": "Test Content",
                    "variable_list": [],
                    "table_list": [
                        {
                            "table_name": "test_table",
                            "column_mapping": {
                                "test_column1": "TEST Column 1",
                                "test_column2": "TEST Column 2",
                            },
                            "sort_list": {
                                "test_column1": "asc",
                                "test_column2": "desc",
                            },
                            "variable_name": "test_table+_1",
                            "filter_list": [
                                {
                                    "filter_group": [
                                        {
                                            "table_name": "test_table",
                                            "filter_variable": "test_column",
                                            "filter_operator": "Is",
                                            "filter_value": "test_value",
                                        },
                                        {
                                            "table_name": "test_table",
                                            "filter_variable": "test_column2",
                                            "filter_operator": "Is",
                                            "filter_value": "test_value2",
                                        },
                                    ]
                                },
                                {
                                    "filter_group": [
                                        {
                                            "table_name": "test_table",
                                            "filter_variable": "test_column",
                                            "filter_operator": "Is",
                                            "filter_value": "test_value",
                                        },
                                        {
                                            "table_name": "test_table",
                                            "filter_variable": "test_column2",
                                            "filter_operator": "Is not",
                                            "filter_value": "test_value2",
                                        },
                                    ]
                                },
                            ],
                        }
                    ],
                },
            ],
        }

        response = client.post(
            "/api/emails/templates",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        if expected_permission:
            assert response.status_code == 201
            get_response = client.get(
                f"api/emails/template?email_config_uid={create_email_config['email_config_uid']}",
                content_type="application/json",
                headers={"X-CSRF-Token": csrf_token},
            )
            print(get_response.json)
            expected_response = {
                "data": [
                    {
                        "content": "Test Content",
                        "email_config_uid": 1,
                        "email_template_uid": 1,
                        "language": "english",
                        "subject": "Test Assignments Email",
                        "table_list": [
                            {
                                "column_mapping": {
                                    "test_column1": "TEST Column 1",
                                    "test_column2": "TEST Column 2",
                                },
                                "email_template_table_uid": 1,
                                "filter_list": [
                                    [
                                        {
                                            "email_template_table_uid": 1,
                                            "filter_group_id": 1,
                                            "filter_operator": "Is",
                                            "filter_value": "test_value",
                                            "filter_variable": "test_column",
                                        },
                                        {
                                            "email_template_table_uid": 1,
                                            "filter_group_id": 1,
                                            "filter_operator": "Is",
                                            "filter_value": "test_value2",
                                            "filter_variable": "test_column2",
                                        },
                                    ],
                                    [
                                        {
                                            "email_template_table_uid": 1,
                                            "filter_group_id": 2,
                                            "filter_operator": "Is",
                                            "filter_value": "test_value",
                                            "filter_variable": "test_column",
                                        },
                                        {
                                            "email_template_table_uid": 1,
                                            "filter_group_id": 2,
                                            "filter_operator": "Is not",
                                            "filter_value": "test_value2",
                                            "filter_variable": "test_column2",
                                        },
                                    ],
                                ],
                                "sort_list": {
                                    "test_column1": "asc",
                                    "test_column2": "desc",
                                },
                                "table_name": "test_table",
                                "variable_name": "test_table+_1",
                            }
                        ],
                        "variable_list": [],
                    },
                    {
                        "content": "Test Content",
                        "email_config_uid": 1,
                        "email_template_uid": 2,
                        "language": "hindi",
                        "subject": "Test Assignments Email",
                        "table_list": [
                            {
                                "column_mapping": {
                                    "test_column1": "TEST Column 1",
                                    "test_column2": "TEST Column 2",
                                },
                                "email_template_table_uid": 2,
                                "filter_list": [
                                    [
                                        {
                                            "email_template_table_uid": 2,
                                            "filter_group_id": 1,
                                            "filter_operator": "Is",
                                            "filter_value": "test_value",
                                            "filter_variable": "test_column",
                                        },
                                        {
                                            "email_template_table_uid": 2,
                                            "filter_group_id": 1,
                                            "filter_operator": "Is",
                                            "filter_value": "test_value2",
                                            "filter_variable": "test_column2",
                                        },
                                    ],
                                    [
                                        {
                                            "email_template_table_uid": 2,
                                            "filter_group_id": 2,
                                            "filter_operator": "Is",
                                            "filter_value": "test_value",
                                            "filter_variable": "test_column",
                                        },
                                        {
                                            "email_template_table_uid": 2,
                                            "filter_group_id": 2,
                                            "filter_operator": "Is not",
                                            "filter_value": "test_value2",
                                            "filter_variable": "test_column2",
                                        },
                                    ],
                                ],
                                "sort_list": {
                                    "test_column1": "asc",
                                    "test_column2": "desc",
                                },
                                "table_name": "test_table",
                                "variable_name": "test_table+_1",
                            }
                        ],
                        "variable_list": [],
                    },
                ],
                "success": True,
            }

            assert get_response.status_code == 200

            checkdiff = jsondiff.diff(
                expected_response,
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
            "variable_list": [
                {
                    "variable_name": "test_variable",
                    "variable_expression": "UPPERCASE(test_variable)",
                },
                {
                    "variable_name": "test_variable2",
                    "variable_expression": "UPPERCASE(test_variable2)",
                },
            ],
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
            print(get_response.json)
            expected_response = {
                "data": {
                    "content": "Test Content",
                    "email_config_uid": 1,
                    "email_template_uid": 1,
                    "language": "Hindi",
                    "subject": "Test Update Email",
                    "table_list": [],
                    "variable_list": [
                        {
                            "variable_expression": "UPPERCASE(test_variable)",
                            "variable_name": "test_variable",
                        },
                        {
                            "variable_expression": "UPPERCASE(test_variable2)",
                            "variable_name": "test_variable2",
                        },
                    ],
                },
                "success": True,
            }
            print("Get Response", get_response.json)
            checkdiff = jsondiff.diff(
                expected_response,
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

    def test_emails_update_template_variable_list_exception(
        self, client, csrf_token, create_email_template, user_permissions, request
    ):
        """
        Test updating a specific email template for different user roles
        Payload has an error on variable mapping with missing variable name
        Expect errors on email template update
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "subject": "Test Update Email",
            "language": "Hindi",
            "content": "Test Content",
            "email_config_uid": 1,
            "variable_list": [
                {"variable_expression": "test_variable"},
            ],
        }
        response = client.put(
            f"/api/emails/template/{create_email_template['email_template_uid']}",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 422

        excepted_response = {
            "message": {
                "variable_list": [{"variable_name": ["This field is required."]}]
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(excepted_response, response.json)

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

    def test_email_load_table_catalog(
        self, client, csrf_token, create_email_config, user_permissions, request
    ):
        """
        Test loading table catalog for different user roles
        Expect the table catalog to be loaded
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "survey_uid": "1",
            "table_catalog": [
                {
                    "table_name": "test_table",
                    "column_name": "test_column",
                    "column_type": "text",
                    "column_description": "test description",
                },
                {
                    "table_name": "test_table",
                    "column_name": "test_column2",
                    "column_type": "text",
                },
            ],
        }

        response = client.put(
            "/api/emails/tablecatalog",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.status_code)
        print(response.json)

        if expected_permission:
            assert response.status_code == 200
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

    @pytest.fixture()
    def create_tablecatalog(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_config,
    ):
        """
        Insert new survey as a setup step for the form tests
        """

        payload = {
            "survey_uid": "1",
            "table_catalog": [
                {
                    "table_name": "test_table",
                    "column_name": "test_column",
                    "column_type": "text",
                    "column_description": "test description",
                },
                {
                    "table_name": "test_table",
                    "column_name": "test_column2",
                    "column_type": "text",
                },
            ],
        }

        response = client.put(
            "/api/emails/tablecatalog",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        print(response.status_code)
        assert response.status_code == 200

        yield

    def test_emails_get_email_table_catalog(
        self, client, csrf_token, create_tablecatalog, user_permissions, request
    ):
        """
        Test to get table catalog for different user roles
        Expect the table catalog information to be correctly fetched
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "email_config_uid": 1,
        }
        response = client.get(
            f"api/emails/tablecatalog",
            content_type="application/json",
            query_string=payload,
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.status_code)
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "data": [
                    {
                        "column_list": [
                            {
                                "column_description": "test description",
                                "column_name": "test_column",
                            },
                            {"column_description": None, "column_name": "test_column2"},
                        ],
                        "survey_uid": 1,
                        "table_name": "test_table",
                    },
                    {
                        "column_list": [
                            {
                                "column_description": "Enumerators : name",
                                "column_name": "Surveyor Name",
                            },
                            {
                                "column_description": "Enumerators : enumerator_id",
                                "column_name": "Surveyor ID",
                            },
                            {
                                "column_description": "Enumerators : home_address",
                                "column_name": "Surveyor Address",
                            },
                            {
                                "column_description": "Enumerators : gender",
                                "column_name": "Surveyor Gender",
                            },
                            {
                                "column_description": "Enumerators : language",
                                "column_name": "Surveyor Language",
                            },
                            {
                                "column_description": "Enumerators : email",
                                "column_name": "Surveyor Email",
                            },
                            {
                                "column_description": "Enumerators : mobile_primary",
                                "column_name": "Surveyor Mobile",
                            },
                            {
                                "column_description": "Targets: target_id",
                                "column_name": "Target ID",
                            },
                            {
                                "column_description": "Targets: gender",
                                "column_name": "Gender",
                            },
                            {
                                "column_description": "Targets: language",
                                "column_name": "Language",
                            },
                            {
                                "column_description": "Target_Status: final_survey_status_label",
                                "column_name": "Final Survey Status",
                            },
                            {
                                "column_description": "Target_Status: final_survey_status",
                                "column_name": "Final Survey Status Code",
                            },
                            {
                                "column_description": "Target_Status: revisit_sections",
                                "column_name": "Revisit Sections",
                            },
                            {
                                "column_description": "Target_Status: num_attempts",
                                "column_name": "Total Attempts",
                            },
                            {
                                "column_description": "Target_Status: refusal_flag",
                                "column_name": "Refused",
                            },
                            {
                                "column_description": "Target_Status: completed_flag",
                                "column_name": "Completed",
                            },
                        ],
                        "survey_uid": 1,
                        "table_name": "Assignments: Default",
                    },
                    {
                        "column_list": [
                            {"column_description": None, "column_name": "test_column"}
                        ],
                        "survey_uid": 1,
                        "table_name": "Google Sheet: Test_Success",
                    },
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
                "error": "User does not have the required permission: WRITE Emails",
                "success": False,
            }

            assert response.status_code == 403

            checkdiff = jsondiff.diff(
                expected_response,
                response.json,
            )
            assert checkdiff == {}

    def test_email_update_table_catalog(
        self, client, csrf_token, create_tablecatalog, user_permissions, request
    ):
        """
        Test loading table catalog for different user roles
        Expect the table catalog to be loaded
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "survey_uid": "1",
            "table_catalog": [
                {
                    "table_name": "test_table",
                    "column_name": "test_column",
                    "column_type": "text",
                    "column_description": "test description changed",
                },
                {
                    "table_name": "test_table",
                    "column_name": "test_column2",
                    "column_type": "integer",  # change data type
                },
                {
                    "table_name": "test_table2",
                    "column_name": "test_column3",
                    "column_type": "text",  # add new column
                },
            ],
        }

        response = client.put(
            "/api/emails/tablecatalog",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.status_code)
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            # Check if table catalog was updated
            response = client.get(
                f"api/emails/tablecatalog?email_config_uid=1",
                content_type="application/json",
                headers={"X-CSRF-Token": csrf_token},
            )
            print(response.status_code)
            print(response.json)
            assert response.status_code == 200

            expected_response = {
                "data": [
                    {
                        "column_list": [
                            {
                                "column_description": "test description changed",
                                "column_name": "test_column",
                            },
                            {"column_description": None, "column_name": "test_column2"},
                        ],
                        "survey_uid": 1,
                        "table_name": "test_table",
                    },
                    {
                        "column_list": [
                            {"column_description": None, "column_name": "test_column3"}
                        ],
                        "survey_uid": 1,
                        "table_name": "test_table2",
                    },
                    {
                        "column_list": [
                            {
                                "column_description": "Enumerators : name",
                                "column_name": "Surveyor Name",
                            },
                            {
                                "column_description": "Enumerators : enumerator_id",
                                "column_name": "Surveyor ID",
                            },
                            {
                                "column_description": "Enumerators : home_address",
                                "column_name": "Surveyor Address",
                            },
                            {
                                "column_description": "Enumerators : gender",
                                "column_name": "Surveyor Gender",
                            },
                            {
                                "column_description": "Enumerators : language",
                                "column_name": "Surveyor Language",
                            },
                            {
                                "column_description": "Enumerators : email",
                                "column_name": "Surveyor Email",
                            },
                            {
                                "column_description": "Enumerators : mobile_primary",
                                "column_name": "Surveyor Mobile",
                            },
                            {
                                "column_description": "Targets: target_id",
                                "column_name": "Target ID",
                            },
                            {
                                "column_description": "Targets: gender",
                                "column_name": "Gender",
                            },
                            {
                                "column_description": "Targets: language",
                                "column_name": "Language",
                            },
                            {
                                "column_description": "Target_Status: final_survey_status_label",
                                "column_name": "Final Survey Status",
                            },
                            {
                                "column_description": "Target_Status: final_survey_status",
                                "column_name": "Final Survey Status Code",
                            },
                            {
                                "column_description": "Target_Status: revisit_sections",
                                "column_name": "Revisit Sections",
                            },
                            {
                                "column_description": "Target_Status: num_attempts",
                                "column_name": "Total Attempts",
                            },
                            {
                                "column_description": "Target_Status: refusal_flag",
                                "column_name": "Refused",
                            },
                            {
                                "column_description": "Target_Status: completed_flag",
                                "column_name": "Completed",
                            },
                        ],
                        "survey_uid": 1,
                        "table_name": "Assignments: Default",
                    },
                    {
                        "column_list": [
                            {"column_description": None, "column_name": "test_column"}
                        ],
                        "survey_uid": 1,
                        "table_name": "Google Sheet: Test_Success",
                    },
                ],
                "success": True,
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

    def test_email_update_table_catalog_with_exception(
        self, client, csrf_token, create_tablecatalog, user_permissions, request
    ):
        """
        Test loading table catalog for different user roles
        Expect the table catalog to be not loaded since required columns missing
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "survey_uid": "1",
            "table_catalog": [
                {
                    "table_name": "test_table",
                    "column_name": "test_column",
                    "column_type": "text",
                    "column_description": "test description changed",
                },
                {
                    "table_name": "test_table",
                    "column_name": "test_column2",
                    "column_type": "integer",  # change data type
                },
                {
                    "table_name": "test_table",
                    # missing column name and type
                },
            ],
        }

        response = client.put(
            "/api/emails/tablecatalog",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.status_code)
        print(response.json)

        assert response.status_code == 422

        expected_response = {
            "message": {
                "table_catalog": [
                    {},
                    {},
                    {
                        "column_name": ["This field is required."],
                        "column_type": ["This field is required."],
                    },
                ]
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        # Check if table catalog was updated
        get_response = client.get(
            f"api/emails/tablecatalog?email_config_uid=1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        if expected_permission:

            print(get_response.status_code)
            print(get_response.json)
            assert get_response.status_code == 200

            expected_response = {
                "data": [
                    {
                        "column_list": [
                            {
                                "column_description": "test description",
                                "column_name": "test_column",
                            },
                            {"column_description": None, "column_name": "test_column2"},
                        ],
                        "survey_uid": 1,
                        "table_name": "test_table",
                    },
                    {
                        "column_list": [
                            {
                                "column_description": "Enumerators : name",
                                "column_name": "Surveyor Name",
                            },
                            {
                                "column_description": "Enumerators : enumerator_id",
                                "column_name": "Surveyor ID",
                            },
                            {
                                "column_description": "Enumerators : home_address",
                                "column_name": "Surveyor Address",
                            },
                            {
                                "column_description": "Enumerators : gender",
                                "column_name": "Surveyor Gender",
                            },
                            {
                                "column_description": "Enumerators : language",
                                "column_name": "Surveyor Language",
                            },
                            {
                                "column_description": "Enumerators : email",
                                "column_name": "Surveyor Email",
                            },
                            {
                                "column_description": "Enumerators : mobile_primary",
                                "column_name": "Surveyor Mobile",
                            },
                            {
                                "column_description": "Targets: target_id",
                                "column_name": "Target ID",
                            },
                            {
                                "column_description": "Targets: gender",
                                "column_name": "Gender",
                            },
                            {
                                "column_description": "Targets: language",
                                "column_name": "Language",
                            },
                            {
                                "column_description": "Target_Status: final_survey_status_label",
                                "column_name": "Final Survey Status",
                            },
                            {
                                "column_description": "Target_Status: final_survey_status",
                                "column_name": "Final Survey Status Code",
                            },
                            {
                                "column_description": "Target_Status: revisit_sections",
                                "column_name": "Revisit Sections",
                            },
                            {
                                "column_description": "Target_Status: num_attempts",
                                "column_name": "Total Attempts",
                            },
                            {
                                "column_description": "Target_Status: refusal_flag",
                                "column_name": "Refused",
                            },
                            {
                                "column_description": "Target_Status: completed_flag",
                                "column_name": "Completed",
                            },
                        ],
                        "survey_uid": 1,
                        "table_name": "Assignments: Default",
                    },
                    {
                        "column_list": [
                            {"column_description": None, "column_name": "test_column"}
                        ],
                        "survey_uid": 1,
                        "table_name": "Google Sheet: Test_Success",
                    },
                ],
                "success": True,
            }
            checkdiff = jsondiff.diff(expected_response, get_response.json)
            assert checkdiff == {}
        else:
            assert get_response.status_code == 403
            expected_response = {
                "error": "User does not have the required permission: WRITE Emails",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, get_response.json)
            assert checkdiff == {}
