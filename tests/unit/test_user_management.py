import base64
import json
from pathlib import Path

import jsondiff
import pandas as pd
import pytest


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
                "gender": None,
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

    @pytest.fixture()
    def create_survey(self, client, login_test_user, csrf_token, test_user_credentials):
        """
        Insert new survey as a setup step for the survey level user tests
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
            "prime_geo_level_uid": 1,
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
    def create_module_questionnaire(
        self, client, login_test_user, csrf_token, test_user_credentials, create_survey
    ):
        """
        Insert new module_questionnaire as a setup step for the module_questionnaire tests
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
    def update_mapping_criteria_to_language(
        self, client, login_test_user, csrf_token, test_user_credentials
    ):
        # Update mapping_criteria to specified value
        payload = {
            "assignment_process": "Manual",
            "language_location_mapping": False,
            "reassignment_required": False,
            "target_mapping_criteria": ["Language"],
            "surveyor_mapping_criteria": ["Language"],
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

    @pytest.fixture()
    def update_mapping_criteria_to_gender(
        self, client, login_test_user, csrf_token, test_user_credentials
    ):
        # Update mapping_criteria to specified value
        payload = {
            "assignment_process": "Manual",
            "language_location_mapping": False,
            "reassignment_required": False,
            "target_mapping_criteria": ["Gender"],
            "surveyor_mapping_criteria": ["Gender"],
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
        self,
        client,
        login_test_user,
        csrf_token,
        create_module_questionnaire,
        create_permission,
    ):
        """
        Insert new roles as a setup step for testing survey level users
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
    def create_form(
        self,
        client,
        login_test_user,
        csrf_token,
        create_survey,
        create_module_questionnaire,
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
            "number_of_attempts": 7,
        }

        response = client.post(
            "/api/forms",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201
        print(response.json)

        yield

    @pytest.fixture()
    def create_geo_levels(self, client, login_test_user, csrf_token, create_form):
        """
        Insert new geo levels as a setup step for the location upload
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
        print(response.json)
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
        Upload locations csv as a setup step for user locations test
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

    @pytest.fixture
    def sample_user_with_locations(
        self, client, csrf_token, sample_user, create_roles, create_locations
    ):
        """
        Return the user added by added_user fixture as the sample_user
        """

        user_uid = sample_user.get("user_uid")
        response = client.put(
            f"/api/users/{user_uid}",
            json={
                "survey_uid": 1,
                "email": "updateduser@example.com",
                "first_name": "Updated",
                "last_name": "User",
                "roles": [2],
                "gender": "Male",
                "location_uids": [1],
                "is_super_admin": True,
                "active": True,
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        return response.json["user_data"]

    @pytest.fixture
    def sample_user_with_languages(
        self,
        client,
        csrf_token,
        sample_user,
        create_roles,
        update_mapping_criteria_to_language,
    ):
        """
        Return the user added by added_user fixture as the sample_user
        """

        user_uid = sample_user.get("user_uid")
        response = client.put(
            f"/api/users/{user_uid}",
            json={
                "survey_uid": 1,
                "email": "updateduser@example.com",
                "first_name": "Updated",
                "last_name": "User",
                "roles": [2],
                "gender": "Male",
                "languages": ["English", "Hindi"],
                "is_super_admin": True,
                "active": True,
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        return response.json["user_data"]

    @pytest.fixture
    def sample_user_with_gender(
        self,
        client,
        csrf_token,
        sample_user,
        create_roles,
        update_mapping_criteria_to_gender,
    ):
        """
        Return the user added by added_user fixture as the sample_user
        """

        user_uid = sample_user.get("user_uid")
        response = client.put(
            f"/api/users/{user_uid}",
            json={
                "survey_uid": 1,
                "email": "updateduser@example.com",
                "first_name": "Updated",
                "last_name": "User",
                "roles": [2],
                "gender": "Male",
                "is_super_admin": True,
                "active": True,
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        return response.json["user_data"]

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
            "gender": sample_user.get("gender"),
            "is_super_admin": sample_user.get("is_super_admin"),
            "can_create_survey": False,
            "active": True,
            "is_survey_admin": False,
            "location_uids": [],
            "location_ids": [],
            "location_names": [],
            "languages": [],
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

    def test_check_user_survey_level(
        self, client, login_test_user, csrf_token, sample_user_with_locations
    ):
        """
        Test checking user availability by email with survey_uid parameter set
        Expect sample_user_with_locations to be available , also expect similar data
        """
        response = client.post(
            "/api/users/check-email-availability",
            json={"email": sample_user_with_locations.get("email"), "survey_uid": 1},
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 200
        assert b"User already exists" in response.data

        # Check if the returned user data matches the expected data
        expected_data = {
            "user_uid": sample_user_with_locations.get("user_uid"),
            "email": sample_user_with_locations.get("email"),
            "first_name": sample_user_with_locations.get("first_name"),
            "last_name": sample_user_with_locations.get("last_name"),
            "roles": sample_user_with_locations.get("roles"),
            "gender": sample_user_with_locations.get("gender"),
            "is_super_admin": sample_user_with_locations.get("is_super_admin"),
            "can_create_survey": False,
            "active": True,
            "is_survey_admin": False,
            "location_uids": [1],
            "location_ids": ["1"],
            "location_names": ["ADILABAD"],
            "languages": [],
        }
        assert response.json["user"] == expected_data

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
            "gender": None,
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
                "gender": "Male",
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
            "gender": "Male",
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

        print(response.json)

        expected_response = [
            {
                "can_create_survey": None,
                "email": "surveystream.devs@idinsight.org",
                "first_name": None,
                "is_super_admin": True,
                "last_name": None,
                "roles": None,
                "gender": None,
                "status": "Active",
                "supervisor_uid": None,
                "user_admin_survey_names": [],
                "user_survey_role_names": [],
                "user_uid": 1,
                "location_uids": [],
                "location_ids": [],
                "location_names": [],
                "languages": [],
            },
            {
                "can_create_survey": None,
                "email": "registration_user",
                "first_name": None,
                "is_super_admin": True,
                "last_name": None,
                "roles": None,
                "gender": None,
                "status": "Active",
                "supervisor_uid": None,
                "user_admin_survey_names": [],
                "user_survey_role_names": [],
                "user_uid": 2,
                "location_uids": [],
                "location_ids": [],
                "location_names": [],
                "languages": [],
            },
        ]

        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_get_all_users_by_survey(self, client, login_test_user, csrf_token):
        """
        Test endpoint for getting all users for a survey
        Expect a user list
        """
        response = client.get(
            "/api/users",
            headers={"X-CSRF-Token": csrf_token},
            query_string={"survey_uid": 1},
        )

        assert response.status_code == 200

        assert response.json == []

    def test_get_all_users_invalid_param(self, client, login_test_user, csrf_token):
        """
        Test endpoint for getting all users
        Test that an invalid parameter returns the correct error
        Expect a user list
        """
        response = client.get(
            "/api/users",
            headers={"X-CSRF-Token": csrf_token},
            query_string={"survey_uid": "undefined"},
        )

        assert response.status_code == 400

        expected_response = {
            "data": None,
            "message": {"survey_uid": ["Not a valid integer value."]},
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

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
            "gender": None,
            "user_uid": 3,
        }
        checkdiff = jsondiff.diff(expected_response, response_get_user.json)
        assert checkdiff == {}

    def test_add_user_at_survey_level(
        self,
        client,
        login_test_user,
        csrf_token,
        create_roles,
        update_mapping_criteria_to_language,
    ):
        """
        Test adding a user at the survey level with role
        """
        response = client.post(
            "/api/users",
            json={
                "survey_uid": 1,
                "email": "newuser2@example.com",
                "first_name": "John",
                "last_name": "Doe2",
                "roles": [2],
                "gender": "Male",
                "languages": ["English"],
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200
        assert b"Success: user invited" in response.data
        response_data = json.loads(response.data)
        user_object = response_data.get("user")
        invite_object = response_data.get("invite")

        response = client.get(
            "/api/users",
            query_string={"survey_uid": 1},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        print(response.json)

        expected_response = [
            {
                "can_create_survey": False,
                "email": "newuser2@example.com",
                "first_name": "John",
                "gender": "Male",
                "is_super_admin": False,
                "languages": ["English"],
                "last_name": "Doe2",
                "location_ids": [],
                "location_names": [],
                "location_uids": [],
                "roles": [2],
                "status": "Active",
                "supervisor_uid": None,
                "user_admin_survey_names": [],
                "user_survey_role_names": [
                    {"role_name": "Regional Coordinator", "survey_name": "Test Survey"}
                ],
                "user_uid": 3,
            },
            {
                "can_create_survey": None,
                "email": "surveystream.devs@idinsight.org",
                "first_name": None,
                "gender": None,
                "is_super_admin": True,
                "languages": [],
                "last_name": None,
                "location_ids": [],
                "location_names": [],
                "location_uids": [],
                "roles": None,
                "status": "Active",
                "supervisor_uid": None,
                "user_admin_survey_names": ["Test Survey"],
                "user_survey_role_names": [],
                "user_uid": 1,
            },
        ]

        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_add_user_at_survey_level_with_locations(
        self, client, login_test_user, csrf_token, create_locations, create_roles
    ):
        """
        Test adding a user at the survey level with role
        """
        response = client.post(
            "/api/users",
            json={
                "survey_uid": 1,
                "email": "newuser2@example.com",
                "first_name": "John",
                "last_name": "Doe2",
                "roles": [2],
                "gender": "Male",
                "languages": ["English"],
                "location_uids": [1],
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200
        assert b"Success: user invited" in response.data
        response_data = json.loads(response.data)
        user_object = response_data.get("user")
        invite_object = response_data.get("invite")

        response = client.get(
            "/api/users",
            query_string={"survey_uid": 1},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        print(response.json)

        expected_response = [
            {
                "can_create_survey": None,
                "email": "surveystream.devs@idinsight.org",
                "first_name": None,
                "gender": None,
                "is_super_admin": True,
                "last_name": None,
                "roles": None,
                "status": "Active",
                "supervisor_uid": None,
                "user_admin_survey_names": ["Test Survey"],
                "user_survey_role_names": [],
                "user_uid": 1,
                "location_uids": [],
                "location_ids": [],
                "location_names": [],
                "languages": [],
            },
            {
                "can_create_survey": False,
                "email": "newuser2@example.com",
                "first_name": "John",
                "is_super_admin": False,
                "last_name": "Doe2",
                "roles": [2],
                "gender": "Male",
                "status": "Active",
                "supervisor_uid": None,
                "user_admin_survey_names": [],
                "user_survey_role_names": [
                    {"role_name": "Regional Coordinator", "survey_name": "Test Survey"}
                ],
                "user_uid": 3,
                "location_uids": [1],
                "location_ids": ["1"],
                "location_names": ["ADILABAD"],
                "languages": ["English"],
            },
        ]

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        # Fetch user locations
        response = client.get(
            "/api/user-locations",
            query_string={"survey_uid": 1, "user_uid": 3},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        print(response.json)

        expected_response = {
            "data": [
                {
                    "location_uid": 1,
                    "user_uid": 3,
                    "user_name": "John Doe2",
                    "location_id": "1",
                    "location_name": "ADILABAD",
                }
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_edit_user_at_survey_level(
        self, client, login_test_user, csrf_token, create_roles, sample_user
    ):
        """
        Test endpoint for updating user data at survey level
        Expect sample_user data to be updated to new values
        """
        user_uid = sample_user.get("user_uid")
        response = client.put(
            f"/api/users/{user_uid}",
            json={
                "survey_uid": 1,
                "email": "updateduser@example.com",
                "first_name": "Updated",
                "last_name": "User",
                "roles": [1],
                "gender": "Male",
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
            "roles": [1],
            "gender": "Male",
            "is_super_admin": True,
            "can_create_survey": False,
            "active": True,
        }
        assert jsondiff.diff(expected_data, updated_user) == {}

    def test_edit_user_at_survey_level_with_locations(
        self,
        client,
        login_test_user,
        csrf_token,
        create_roles,
        sample_user,
        create_locations,
    ):
        """
        Test endpoint for updating user data at survey level
        Expect sample_user data to be updated to new values
        """
        user_uid = sample_user.get("user_uid")
        response = client.put(
            f"/api/users/{user_uid}",
            json={
                "survey_uid": 1,
                "email": "updateduser@example.com",
                "first_name": "Updated",
                "last_name": "User",
                "roles": [2],
                "gender": "Male",
                "location_uids": [1],
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
            "roles": [2],
            "gender": "Male",
            "is_super_admin": True,
            "can_create_survey": False,
            "active": True,
        }
        assert jsondiff.diff(expected_data, updated_user) == {}

        # Fetch user locations
        response = client.get(
            "/api/user-locations",
            query_string={"survey_uid": 1, "user_uid": user_uid},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        print(response.json)

        expected_response = {
            "data": [
                {
                    "location_uid": 1,
                    "user_uid": user_uid,
                    "user_name": "Updated User",
                    "location_id": "1",
                    "location_name": "ADILABAD",
                }
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_user_locations(
        self,
        client,
        login_test_user,
        csrf_token,
        sample_user_with_locations,
    ):
        """
        Test fetching locations for a user and a survey
        """
        user_uid = sample_user_with_locations.get("user_uid")

        # Fetch user locations
        response = client.get(
            "/api/user-locations",
            query_string={"survey_uid": 1, "user_uid": user_uid},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        print(response.json)

        expected_response = {
            "data": [
                {
                    "location_uid": 1,
                    "user_uid": user_uid,
                    "user_name": "Updated User",
                    "location_id": "1",
                    "location_name": "ADILABAD",
                }
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_all_user_locations(
        self,
        client,
        login_test_user,
        csrf_token,
        sample_user_with_locations,
    ):
        """
        Test fetching locations for all users in a survey
        """
        user_uid = sample_user_with_locations.get("user_uid")

        # Fetch user locations
        response = client.get(
            "/api/user-locations",
            query_string={"survey_uid": 1, "user_uid": user_uid},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        print(response.json)

        expected_response = {
            "data": [
                {
                    "location_uid": 1,
                    "user_uid": user_uid,
                    "user_name": "Updated User",
                    "location_id": "1",
                    "location_name": "ADILABAD",
                }
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_user_locations(
        self,
        client,
        login_test_user,
        csrf_token,
        create_locations,
        sample_user_with_locations,
    ):
        """
        Test updating locations data for a user
        """
        user_uid = sample_user_with_locations.get("user_uid")
        response = client.put(
            "/api/user-locations",
            json={
                "survey_uid": 1,
                "user_uid": user_uid,
                "location_uids": [1],
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Fetch user locations
        response = client.get(
            "/api/user-locations",
            query_string={"survey_uid": 1, "user_uid": user_uid},
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        expected_response = {
            "data": [
                {
                    "location_uid": 1,
                    "user_uid": user_uid,
                    "user_name": "Updated User",
                    "location_id": "1",
                    "location_name": "ADILABAD",
                },
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_user_locations_missing_location(
        self,
        client,
        login_test_user,
        csrf_token,
        create_locations,
        sample_user_with_locations,
    ):
        """
        Test updating locations data for a user with a missing location
        """
        user_uid = sample_user_with_locations.get("user_uid")
        response = client.put(
            "/api/user-locations",
            json={
                "survey_uid": 1,
                "user_uid": user_uid,
                "location_uids": [1, 100],
            },  # Add location 100 - this is not a location in locations
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 422
        expected_response = {
            "message": {"location_uids": ["Location with UID 100 does not exist."]},
            "success": False,
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        # Fetch user locations to see it was not updated
        response = client.get(
            "/api/user-locations",
            query_string={"survey_uid": 1, "user_uid": user_uid},
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        expected_response = {
            "data": [
                {
                    "location_uid": 1,
                    "user_uid": user_uid,
                    "user_name": "Updated User",
                    "location_id": "1",
                    "location_name": "ADILABAD",
                },
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_user_locations_not_prime_geo_level(
        self,
        client,
        login_test_user,
        csrf_token,
        create_locations,
        sample_user_with_locations,
    ):
        """
        Test updating locations data for a user with a location that is not a prime geo level location
        """
        user_uid = sample_user_with_locations.get("user_uid")
        response = client.put(
            "/api/user-locations",
            json={
                "survey_uid": 1,
                "user_uid": user_uid,
                "location_uids": [1, 2],
            },  # Add location 2 - this is not a location at prime geo level
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 422
        print(response.json)
        expected_response = {
            "message": {
                "location_uids": [
                    "Location with UID 2 is not a prime geo level location."
                ]
            },
            "success": False,
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_delete_user_locations(
        self,
        client,
        login_test_user,
        csrf_token,
        create_locations,
        sample_user_with_locations,
    ):
        """
        Test deleting locations data for a user
        """
        user_uid = sample_user_with_locations.get("user_uid")
        # Delete user locations
        response = client.delete(
            "/api/user-locations",
            query_string={"survey_uid": 1, "user_uid": user_uid},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Fetch user locations
        response = client.get(
            "/api/user-locations",
            query_string={"survey_uid": 1, "user_uid": user_uid},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 404

        expected_response = {"message": "User locations not found"}
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_add_user_survey_uid_validation_error(
        self, client, login_test_user, csrf_token, create_roles
    ):
        """
        Test adding a user at the survey level with is_survey_admin set to True
        """
        response = client.post(
            "/api/users",
            json={
                "email": "newuser2@example.com",
                "first_name": "John",
                "last_name": "Doe2",
                "roles": [],
                "gender": "Male",
                "is_survey_admin": True,
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        expected_response = {
            "message": {
                "survey_uid": ["Survey UID is required if user is a survey admin."]
            },
            "success": False,
        }
        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_add_user_at_survey_level_location_uid_validation_error(
        self, client, login_test_user, csrf_token, create_roles
    ):
        """
        Test adding a user at the survey level with wrong location_uids raises error
        """
        response = client.post(
            "/api/users",
            json={
                "survey_uid": 1,
                "email": "newuser2@example.com",
                "first_name": "John",
                "last_name": "Doe2",
                "roles": [2],
                "gender": "Male",
                "location_uids": [100],
                "languages": ["English"],
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 422
        expected_response = {
            "message": {"location_uids": ["Location with UID 100 does not exist."]},
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_add_user_at_survey_level_location_uid_mapping_validation_error(
        self, client, login_test_user, csrf_token, create_roles
    ):
        """
        Test adding a user at the survey level without location_uids when Location is in mapping criteria raises error
        """
        response = client.post(
            "/api/users",
            json={
                "survey_uid": 1,
                "email": "newuser2@example.com",
                "first_name": "John",
                "last_name": "Doe2",
                "roles": [2],
                "gender": "Male",
                "languages": ["English"],
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 422
        expected_response = {
            "message": {
                "location_uids": [
                    "Location mapping is required for the lowest supervisor role."
                ]
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_user_languages(
        self,
        client,
        login_test_user,
        csrf_token,
        sample_user_with_languages,
    ):
        """
        Test fetching languages for a user and a survey
        """
        user_uid = sample_user_with_languages.get("user_uid")

        # Fetch user languages
        response = client.get(
            "/api/user-languages",
            query_string={"survey_uid": 1, "user_uid": user_uid},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        print(response.json)

        expected_response = {
            "data": [
                {
                    "language": "English",
                    "user_uid": user_uid,
                    "user_name": "Updated User",
                },
                {
                    "language": "Hindi",
                    "user_uid": user_uid,
                    "user_name": "Updated User",
                },
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_all_user_languages(
        self,
        client,
        login_test_user,
        csrf_token,
        sample_user_with_languages,
    ):
        """
        Test fetching languages for all users in a survey
        """
        user_uid = sample_user_with_languages.get("user_uid")

        # Fetch user languages
        response = client.get(
            "/api/user-languages",
            query_string={"survey_uid": 1},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        print(response.json)

        expected_response = {
            "data": [
                {
                    "language": "Hindi",
                    "user_uid": user_uid,
                    "user_name": "Updated User",
                },
                {
                    "language": "English",
                    "user_uid": user_uid,
                    "user_name": "Updated User",
                },
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_user_gender(
        self, client, login_test_user, csrf_token, sample_user_with_gender
    ):
        """
        Test fetching gender for a user and a survey
        """
        user_uid = sample_user_with_gender.get("user_uid")

        # Fetch user languages
        response = client.get(
            "/api/user-gender",
            query_string={"survey_uid": 1, "user_uid": user_uid},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        print(response.json)

        expected_response = {
            "data": [
                {"gender": "Male", "user_uid": user_uid, "user_name": "Updated User"},
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_all_user_gender(
        self,
        client,
        login_test_user,
        csrf_token,
        sample_user_with_gender,
    ):
        """
        Test fetching gender for all users in a survey
        """
        user_uid = sample_user_with_gender.get("user_uid")

        # Fetch user languages
        response = client.get(
            "/api/user-gender",
            query_string={"survey_uid": 1},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        print(response.json)

        expected_response = {
            "data": [
                {"gender": "Male", "user_uid": user_uid, "user_name": "Updated User"},
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}
