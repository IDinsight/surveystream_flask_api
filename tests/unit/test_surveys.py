import jsondiff
import pytest
import re

from utils import (
    create_new_survey_admin_user,
    update_logged_in_user_roles,
    login_user,
    create_new_survey_role_with_permissions,
)


@pytest.mark.surveys
class TestSurveys:
    @pytest.fixture()
    def create_surveys(
        self, client, login_test_user, test_user_credentials, csrf_token
    ):
        """
        Insert new survey as a setup step for the survey tests
        """

        payload = {
            "survey_id": "test_survey",
            "survey_name": "Test Survey",
            "survey_description": "A test survey",
            "project_name": "Test Project",
            "surveying_method": "mixed-mode",
            "irb_approval": "Yes",
            "planned_start_date": "2021-01-01",
            "planned_end_date": "2021-12-31",
            "state": "Draft",
            "config_status": "In Progress - Configuration",
        }

        response_user_survey = client.post(
            "/api/surveys",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response_user_survey.status_code == 201

        payload_user_survey = {
            "survey_id": "user_survey",
            "survey_name": "User survey",
            "survey_description": "A survey admin survey",
            "project_name": "Test Project",
            "surveying_method": "mixed-mode",
            "irb_approval": "Yes",
            "planned_start_date": "2021-01-01",
            "planned_end_date": "2021-12-31",
            "state": "Draft",
            "config_status": "In Progress - Configuration",
        }

        new_survey_admin = create_new_survey_admin_user(client)

        login_user(
            client,
            {
                "email": new_survey_admin["email"],
                "password": new_survey_admin["password"],
            },
        )
        response_user_survey = client.post(
            "/api/surveys",
            json=payload_user_survey,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response_user_survey.status_code == 201

        # login usual user
        login_user(client, test_user_credentials)

        return response_user_survey

    @pytest.fixture()
    def create_parent_form(self, client, login_test_user, csrf_token, create_surveys):
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

    def test_create_survey_for_super_admin(
        self, client, login_test_user, create_surveys, test_user_credentials
    ):
        """
        Test that the create_surveys fixture updloads the data correctly
        Expect super admin to get all created surveys
        """

        # Test the survey was inserted correctly
        response = client.get("/api/surveys")
        assert response.status_code == 200

        expected_response = {
            "data": [
                {
                    "survey_uid": 1,
                    "survey_id": "test_survey",
                    "survey_name": "Test Survey",
                    "survey_description": "A test survey",
                    "project_name": "Test Project",
                    "surveying_method": "mixed-mode",
                    "irb_approval": "Yes",
                    "planned_start_date": "2021-01-01",
                    "planned_end_date": "2021-12-31",
                    "state": "Draft",
                    "prime_geo_level_uid": None,
                    "config_status": "In Progress - Configuration",
                    "last_updated_at": "2023-05-30 00:00:00",
                    "created_by_user_uid": test_user_credentials["user_uid"],
                },
                {
                    "config_status": "In Progress - Configuration",
                    "created_by_user_uid": 3,
                    "irb_approval": "Yes",
                    "last_updated_at": "2024-01-25 12:38:41.277939",
                    "planned_end_date": "2021-12-31",
                    "planned_start_date": "2021-01-01",
                    "prime_geo_level_uid": None,
                    "project_name": "Test Project",
                    "state": "Draft",
                    "survey_description": "A survey admin survey",
                    "survey_id": "user_survey",
                    "survey_name": "User survey",
                    "survey_uid": 2,
                    "surveying_method": "mixed-mode",
                },
            ],
            "success": True,
        }

        # Assert that the last_updated_at field is a valid datetime
        assert re.match(
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
            response.json["data"][0]["last_updated_at"],
        )

        # Replace the last_updated_at field in the expected response with the value from the actual response
        expected_response["data"][0]["last_updated_at"] = response.json["data"][0][
            "last_updated_at"
        ]
        expected_response["data"][1]["last_updated_at"] = response.json["data"][1][
            "last_updated_at"
        ]
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_create_survey_for_non_admin(
        self, client, login_test_user, create_surveys, test_user_credentials, csrf_token
    ):
        """
        To test non admin user - update logged-in user to non admin
        Attempt to create survey
        Expect a 403 fail - permissions not allowed
        Revert test logged user to survey_admin ( this will be used later in getting surveys test
        """
        # Update the logged-in user to be a non-admin
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
        )

        login_user(client, test_user_credentials)

        # Attempt to create a survey
        payload = {
            "survey_id": "test_survey",
            "survey_name": "Test Survey",
            "survey_description": "A test survey",
            "project_name": "Test Project",
            "surveying_method": "mixed-mode",
            "irb_approval": "Yes",
            "planned_start_date": "2021-01-01",
            "planned_end_date": "2021-12-31",
            "state": "Draft",
            "config_status": "In Progress - Configuration",
        }

        response = client.post(
            "/api/surveys",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 403

        expected_response = {
            "success": False,
            "error": f"User does not have the required permission: CREATE SURVEY",
        }
        checkdiff = jsondiff.diff(expected_response, response.json)

        assert not checkdiff

    def test_get_surveys_for_super_admin_user(
        self, client, login_test_user, create_surveys, test_user_credentials
    ):
        """
        Test get surveys for super admin
        Expect to get surveys from all users
        - use fixture for this
            - login another user
            - create new surveys with the other user
            - login the current user
        - attempt to get surveys
        """
        # set user permissions
        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=True,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

        response = client.get("/api/surveys")

        print(response.json)

        expected_response = {
            "data": [
                {
                    "survey_uid": 1,
                    "survey_id": "test_survey",
                    "survey_name": "Test Survey",
                    "survey_description": "A test survey",
                    "project_name": "Test Project",
                    "surveying_method": "mixed-mode",
                    "irb_approval": "Yes",
                    "planned_start_date": "2021-01-01",
                    "planned_end_date": "2021-12-31",
                    "state": "Draft",
                    "prime_geo_level_uid": None,
                    "config_status": "In Progress - Configuration",
                    "last_updated_at": "2023-05-30 00:00:00",
                    "created_by_user_uid": test_user_credentials["user_uid"],
                },
                {
                    "config_status": "In Progress - Configuration",
                    "created_by_user_uid": 3,
                    "irb_approval": "Yes",
                    "last_updated_at": "2024-01-25 12:38:41.277939",
                    "planned_end_date": "2021-12-31",
                    "planned_start_date": "2021-01-01",
                    "prime_geo_level_uid": None,
                    "project_name": "Test Project",
                    "state": "Draft",
                    "survey_description": "A survey admin survey",
                    "survey_id": "user_survey",
                    "survey_name": "User survey",
                    "survey_uid": 2,
                    "surveying_method": "mixed-mode",
                },
            ],
            "success": True,
        }
        # Assert that the last_updated_at field is a valid datetime
        assert re.match(
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
            response.json["data"][0]["last_updated_at"],
        )

        # Replace the last_updated_at field in the expected response with the value from the actual response
        expected_response["data"][0]["last_updated_at"] = response.json["data"][0][
            "last_updated_at"
        ]
        expected_response["data"][1]["last_updated_at"] = response.json["data"][1][
            "last_updated_at"
        ]
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_surveys_for_survey_admin_user(
        self, client, login_test_user, create_surveys, test_user_credentials
    ):
        """
        Test get surveys for super admin
        Expect to get surveys only created by the user
        - assign logged-in user with survey_admin status
        """
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=True,
            survey_uid=1,
            is_super_admin=False,
        )

        login_user(client, test_user_credentials)

        response = client.get("/api/surveys")

        print(response.json)

        assert response.status_code == 200

        print(response.json)

        expected_response = {
            "data": [
                {
                    "survey_uid": 1,
                    "survey_id": "test_survey",
                    "survey_name": "Test Survey",
                    "survey_description": "A test survey",
                    "project_name": "Test Project",
                    "surveying_method": "mixed-mode",
                    "irb_approval": "Yes",
                    "planned_start_date": "2021-01-01",
                    "planned_end_date": "2021-12-31",
                    "state": "Draft",
                    "prime_geo_level_uid": None,
                    "config_status": "In Progress - Configuration",
                    "last_updated_at": "2023-05-30 00:00:00",
                    "created_by_user_uid": test_user_credentials["user_uid"],
                }
            ],
            "success": True,
        }
        # Assert that the last_updated_at field is a valid datetime
        assert re.match(
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
            response.json["data"][0]["last_updated_at"],
        )
        # Replace the last_updated_at field in the expected response with the value from the actual response
        expected_response["data"][0]["last_updated_at"] = response.json["data"][0][
            "last_updated_at"
        ]

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_surveys_for_non_admin_user_no_roles(
        self, client, login_test_user, create_surveys, test_user_credentials
    ):
        """
        Test get surveys for non-admin without roles
        Expect to get no surveys 404
        - assign logged-in user with no roles
        - attempt to get surveys
        """
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[],
        )

        login_user(client, test_user_credentials)

        response = client.get("/api/surveys")

        assert response.status_code == 200

        expected_response = {
            "data": [],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_surveys_for_non_admin_user_survey_roles(
        self, client, login_test_user, create_surveys, test_user_credentials
    ):
        """
        Test get surveys for non-admin with roles
        Expect to get surveys with assigned roles
        - assign logged-in user with new survey roles
        - attempt to get surveys
        """

        new_role = create_new_survey_role_with_permissions(
            client, test_user_credentials, "Survey Role", [2, 3], 1
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

        response = client.get("/api/surveys")

        print(response.json)

        assert response.status_code == 200

        print(response.json)

        expected_response = {
            "data": [
                {
                    "survey_uid": 1,
                    "survey_id": "test_survey",
                    "survey_name": "Test Survey",
                    "survey_description": "A test survey",
                    "project_name": "Test Project",
                    "surveying_method": "mixed-mode",
                    "irb_approval": "Yes",
                    "planned_start_date": "2021-01-01",
                    "planned_end_date": "2021-12-31",
                    "state": "Draft",
                    "prime_geo_level_uid": None,
                    "config_status": "In Progress - Configuration",
                    "last_updated_at": "2023-05-30 00:00:00",
                    "created_by_user_uid": test_user_credentials["user_uid"],
                }
            ],
            "success": True,
        }
        # Assert that the last_updated_at field is a valid datetime
        assert re.match(
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
            response.json["data"][0]["last_updated_at"],
        )
        # Replace the last_updated_at field in the expected response with the value from the actual response
        expected_response["data"][0]["last_updated_at"] = response.json["data"][0][
            "last_updated_at"
        ]

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_survey_for_admin(
        self, client, login_test_user, csrf_token, test_user_credentials, create_surveys
    ):
        """
        Test that an existing survey can be updated by an admin user
        Expect 200 and a successful update
        """
        payload = {
            "survey_uid": 1,
            "survey_id": "test_survey_1",
            "survey_name": "Test Survey 1",
            "survey_description": "A test survey 1",
            "project_name": "Test Project 1",
            "surveying_method": "phone",
            "irb_approval": "No",
            "planned_start_date": "2021-01-02",
            "planned_end_date": "2021-12-30",
            "state": "Active",
            "config_status": "In Progress - Backend Setup",
        }

        response = client.put(
            "/api/surveys/1/basic-information",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        response = client.get("/api/surveys/1/basic-information")
        assert response.status_code == 200

        expected_response = {
            "survey_uid": 1,
            "survey_id": "test_survey_1",
            "survey_name": "Test Survey 1",
            "survey_description": "A test survey 1",
            "project_name": "Test Project 1",
            "surveying_method": "phone",
            "irb_approval": "No",
            "planned_start_date": "2021-01-02",
            "planned_end_date": "2021-12-30",
            "state": "Active",
            "prime_geo_level_uid": None,
            "config_status": "In Progress - Backend Setup",
            "last_updated_at": "2023-05-30 00:00:00",
            "created_by_user_uid": test_user_credentials["user_uid"],
        }

        # Assert that the last_updated_at field is a valid datetime
        assert re.match(
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
            response.json["last_updated_at"],
        )

        # Replace the last_updated_at field in the expected response with the value from the actual response
        expected_response["last_updated_at"] = response.json["last_updated_at"]

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_survey_for_non_admin(
        self, client, csrf_token, login_test_user, test_user_credentials, create_surveys
    ):
        """
        To test non admin user - update logged-in user to non admin
        Attempt to update survey
        Expect a 403 fail - permissions not allowed
        Revert test logged user to survey_admin ( this will be used later in getting surveys test
        """

        # Update the logged-in user to be a non-admin
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
        )

        login_user(client, test_user_credentials)

        payload = {
            "survey_uid": 1,
            "survey_id": "test_survey_1",
            "survey_name": "Test Survey 1",
            "survey_description": "A test survey 1",
            "project_name": "Test Project 1",
            "surveying_method": "phone",
            "irb_approval": "No",
            "planned_start_date": "2021-01-02",
            "planned_end_date": "2021-12-30",
            "state": "Active",
            "config_status": "In Progress - Backend Setup",
        }
        # Attempt to update survey
        response = client.put(
            "/api/surveys/1/basic-information",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 403

        print(response.json)

        expected_response = {
            "success": False,
            "error": f"User does not have the required permission: ADMIN",
        }
        checkdiff = jsondiff.diff(expected_response, response.json)

        assert not checkdiff

        revert_user = update_logged_in_user_roles(
            client, test_user_credentials, is_survey_admin=True, survey_uid=1
        )

        login_user(client, test_user_credentials)

    def test_delete_survey_for_admin(
        self, client, login_test_user, csrf_token, test_user_credentials, create_surveys
    ):
        """
        Test that a survey can be deleted by admin user
        Expect 403 fail
        """

        response = client.delete(
            "/api/surveys/1",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 204

        # Check the response
        response = client.get("/api/surveys/1/basic-information")

        assert response.status_code == 404

    def test_delete_survey_for_non_admin(
        self, client, login_test_user, test_user_credentials, csrf_token, create_surveys
    ):
        """
        Test that a survey can be deleted by an admin user
        """
        # Update the logged-in user to be a non-admin
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
        )

        login_user(client, test_user_credentials)

        response = client.delete(
            "/api/surveys/1",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 403

        revert_user = update_logged_in_user_roles(
            client, test_user_credentials, is_survey_admin=True, survey_uid=1
        )

        login_user(client, test_user_credentials)

    def test_get_config_status(
        self, client, login_test_user, csrf_token, create_surveys, create_parent_form
    ):
        """
        Test that module config status for the survey can be retrieved
        """

        response = client.get("/api/surveys/1/config-status")
        assert response.status_code == 200

        print(response.json)
        expected_response = {
            "data": {
                "Basic information": {"status": "In Progress"},
                "Module selection": {"status": "Not Started"},
                "Survey information": [
                    {"name": "SurveyCTO information", "status": "In Progress"},
                    {"name": "Field supervisor roles", "status": "Not Started"},
                    {"name": "Survey locations", "status": "Not Started"},
                    {"name": "SurveyStream users", "status": "Not Started"},
                    {"name": "Enumerators", "status": "Not Started"},
                    {"name": "Targets", "status": "Not Started"},
                ],
                "overall_status": "In Progress - Configuration",
            },
            "success": True,
            "success": True,
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}
