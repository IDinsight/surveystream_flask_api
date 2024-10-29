import base64
from pathlib import Path
import jsondiff
import pytest
import re
import pandas as pd

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
            "prime_geo_level_uid": 1,
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
            "prime_geo_level_uid": 1,
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
    def create_module_questionnaire(
        self, client, login_test_user, csrf_token, test_user_credentials, create_surveys
    ):
        """
        Insert new module_questionnaire to set up mapping criteria needed for assignments
        """

        payload = {
            "assignment_process": "Manual",
            "language_location_mapping": False,
            "reassignment_required": False,
            "target_mapping_criteria": ["Location"],
            "surveyor_mapping_criteria": ["Location"],
            "supervisor_hierarchy_exists": False,
            "supervisor_surveyor_relation": "1:many",
            "survey_uid": 1,
            "target_assignment_criteria": ["Location of surveyors"],
        }

        response = client.put(
            "/api/module-questionnaire/1",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_parent_form(
        self, client, login_test_user, csrf_token, create_module_questionnaire
    ):
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
    def create_permission(self, client, login_test_user, csrf_token):
        """
        Create simple permissions
        Expect to be used while adding roles
        """
        data = {"name": "WRITE", "description": "Write permission"}
        response = client.post(
            "/api/permissions",
            json=data,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201
        assert response.json["message"] == "Permission created successfully"

        return {
            "permission_uid": response.json["permission_uid"],
            "name": response.json["name"],
            "description": response.json["description"],
        }

    @pytest.fixture()
    def create_roles(
        self, client, login_test_user, csrf_token, create_surveys, create_permission
    ):
        """
        Insert new roles as a setup step for the roles tests
        """

        payload = {
            "roles": [
                {
                    "role_uid": None,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                    "permissions": [create_permission["permission_uid"]],
                },
                {
                    "role_uid": None,
                    "role_name": "Regional Coordinator",
                    "reporting_role_uid": 1,
                    "permissions": [create_permission["permission_uid"]],
                },
            ]
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_geo_levels(
        self, client, login_test_user, csrf_token, create_parent_form
    ):
        """
        Insert new geo levels as a setup step for the location upload tests
        These correspond to the geo levels found in the locations test files
        """

        payload = {
            "geo_levels": [
                {
                    "geo_level_uid": None,
                    "geo_level_name": "District",
                    "parent_geo_level_uid": None,
                },
                {
                    "geo_level_uid": None,
                    "geo_level_name": "Mandal",
                    "parent_geo_level_uid": 1,
                },
                {
                    "geo_level_uid": None,
                    "geo_level_name": "PSU",
                    "parent_geo_level_uid": 2,
                },
            ]
        }

        response = client.put(
            "/api/locations/geo-levels",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_locations(
        self,
        client,
        login_test_user,
        create_geo_levels,
        csrf_token,
    ):
        """
        Upload locations csv as a setup step for the enumerators upload tests
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_locations_small.csv"
        )

        # Read the locations.csv file and convert it to base64
        with open(filepath, "rb") as f:
            locations_csv = f.read()
            locations_csv_encoded = base64.b64encode(locations_csv).decode("utf-8")

        # Try to upload the locations csv
        payload = {
            "geo_level_mapping": [
                {
                    "geo_level_uid": 1,
                    "location_name_column": "district_name",
                    "location_id_column": "district_id",
                },
                {
                    "geo_level_uid": 2,
                    "location_name_column": "mandal_name",
                    "location_id_column": "mandal_id",
                },
                {
                    "geo_level_uid": 3,
                    "location_name_column": "psu_name",
                    "location_id_column": "psu_id",
                },
            ],
            "file": locations_csv_encoded,
        }

        response = client.post(
            "/api/locations",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        df = pd.read_csv(filepath, dtype=str)
        df.rename(
            columns={
                "district_id": "District ID",
                "district_name": "District Name",
                "mandal_id": "Mandal ID",
                "mandal_name": "Mandal Name",
                "psu_id": "PSU ID",
                "psu_name": "PSU Name",
            },
            inplace=True,
        )

        expected_response = {
            "data": {
                "ordered_columns": [
                    "District ID",
                    "District Name",
                    "Mandal ID",
                    "Mandal Name",
                    "PSU ID",
                    "PSU Name",
                ],
                "records": df.to_dict(orient="records"),
            },
            "success": True,
        }
        # Check the response
        response = client.get("/api/locations", query_string={"survey_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    @pytest.fixture()
    def upload_enumerators_csv(
        self, client, login_test_user, create_locations, csrf_token
    ):
        """
        Upload the enumerators csv
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_enumerators_small.csv"
        )

        # Read the enumerators.csv file and convert it to base64
        with open(filepath, "rb") as f:
            enumerators_csv = f.read()
            enumerators_csv_encoded = base64.b64encode(enumerators_csv).decode("utf-8")

        # Try to upload the enumerators csv
        payload = {
            "column_mapping": {
                "enumerator_id": "enumerator_id1",
                "name": "name1",
                "email": "email1",
                "mobile_primary": "mobile_primary1",
                "language": "language1",
                "home_address": "home_address1",
                "gender": "gender1",
                "enumerator_type": "enumerator_type1",
                "location_id_column": "district_id1",
                "custom_fields": [
                    {
                        "field_label": "Mobile (Secondary)",
                        "column_name": "mobile_secondary1",
                    },
                    {
                        "field_label": "Age",
                        "column_name": "age1",
                    },
                ],
            },
            "file": enumerators_csv_encoded,
            "mode": "overwrite",
        }

        response = client.post(
            "/api/enumerators",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

    @pytest.fixture()
    def upload_targets_csv(self, client, login_test_user, create_locations, csrf_token):
        """
        Upload the targets csv
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_targets_small.csv"
        )

        # Read the targets.csv file and convert it to base64
        with open(filepath, "rb") as f:
            targets_csv = f.read()
            targets_csv_encoded = base64.b64encode(targets_csv).decode("utf-8")

        # Try to upload the targets csv
        payload = {
            "column_mapping": {
                "target_id": "target_id1",
                "language": "language1",
                "gender": "gender1",
                "location_id_column": "psu_id1",
                "custom_fields": [
                    {
                        "field_label": "Mobile no.",
                        "column_name": "mobile_primary1",
                    },
                    {
                        "field_label": "Name",
                        "column_name": "name1",
                    },
                    {
                        "field_label": "Address",
                        "column_name": "address1",
                    },
                ],
            },
            "file": targets_csv_encoded,
            "mode": "overwrite",
        }

        response = client.post(
            "/api/targets",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

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
                    "prime_geo_level_uid": 1,
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
                    "prime_geo_level_uid": 1,
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
                    "prime_geo_level_uid": 1,
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
                    "prime_geo_level_uid": 1,
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
                    "prime_geo_level_uid": 1,
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
        self, client, login_test_user, create_surveys, create_module_questionnaire, test_user_credentials
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
                    "prime_geo_level_uid": 1,
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

    def test_update_survey_not_found(
        self, client, csrf_token, login_test_user, test_user_credentials, create_surveys
    ):
        """
        Test update survey not found
        Expect 404
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
        # Attempt to update survey
        response = client.put(
            "/api/surveys/100/basic-information",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 404

        print(response.json)

        expected_response = {"error": "Survey not found"}

        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

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

    def test_delete_survey_not_found(
        self, client, login_test_user, test_user_credentials, csrf_token, create_surveys
    ):
        """
        Test delete not found survey
        Expect a 404

        """
        response = client.delete(
            "/api/surveys/100",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 404

        expected_response = {"error": "Survey not found"}
        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_get_config_status(
        self,
        client,
        login_test_user,
        csrf_token,
        create_surveys,
        create_parent_form,
        create_roles,
        upload_enumerators_csv,
        upload_targets_csv,
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
                    {"name": "User and role management", "status": "In Progress"},
                    {"name": "Survey locations", "status": "In Progress"},
                    {"name": "SurveyStream users", "status": "Not Started"},
                    {"name": "Enumerators", "status": "In Progress"},
                    {"name": "Targets", "status": "In Progress"},
                    {"name": "Mapping", "status": "Not Started"},
                ],
                "overall_status": "In Progress - Configuration",
            },
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_config_status_not_found(
        self,
        client,
        login_test_user,
        csrf_token,
        create_surveys,
        create_parent_form,
        create_roles,
        upload_enumerators_csv,
        upload_targets_csv,
    ):
        """
        Test get config status for a missing survey
        Expect 404 fail
        """

        response = client.get("/api/surveys/100/config-status")
        assert response.status_code == 404

        print(response.json)
        expected_response = {"error": "Survey not found"}

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}
