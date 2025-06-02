import base64
import json
from datetime import datetime, timedelta
from pathlib import Path

import jsondiff
import pandas as pd
import pytest
from utils import (
    create_new_survey_role_with_permissions,
    login_user,
    set_target_assignable_status,
    update_logged_in_user_roles,
)

from app import db


@pytest.mark.assignments
class TestAssignments:
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
    def user_with_assignment_permissions(
        self, client, test_user_credentials, csrf_token
    ):
        # Give existing roles permissions to write assignments
        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                    "permissions": [9],  # 9 - WRITE Assignments
                },
                {
                    "role_uid": 2,
                    "role_name": "Cluster Coordinator",
                    "reporting_role_uid": 1,
                    "permissions": [9],  # 9 - WRITE Assignments
                },
                {
                    "role_uid": 3,
                    "role_name": "Regional Coordinator",
                    "reporting_role_uid": 2,
                    "permissions": [9],  # 9 - WRITE Assignments
                },
            ],
            "validate_hierarchy": True,
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[1],  # FS L1 role
        )

        login_user(client, test_user_credentials)

    @pytest.fixture
    def user_with_assignment_upload_permissions(
        self, client, test_user_credentials, csrf_token
    ):
        # Give existing roles permissions to upload assignments
        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                    "permissions": [24],  # 24 - WRITE Assignments Upload
                },
                {
                    "role_uid": 2,
                    "role_name": "Cluster Coordinator",
                    "reporting_role_uid": 1,
                    "permissions": [24],  # 24 - WRITE Assignments Upload
                },
                {
                    "role_uid": 3,
                    "role_name": "Regional Coordinator",
                    "reporting_role_uid": 2,
                    "permissions": [24],  # 24 - WRITE Assignments Upload
                },
            ],
            "validate_hierarchy": True,
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[1],  # FS L1 role
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
            ("user_with_assignment_permissions", True),
            ("user_with_no_permissions", False),
        ],
        ids=[
            "super_admin_permissions",
            "survey_admin_permissions",
            "assignment_permissions",
            "no_permissions",
        ],
    )
    def user_permissions(self, request):
        return request.param

    @pytest.fixture(
        params=[
            ("user_with_super_admin_permissions", True),
            ("user_with_survey_admin_permissions", True),
            ("user_with_assignment_upload_permissions", True),
            ("user_with_no_permissions", False),
        ],
        ids=[
            "super_admin_permissions",
            "survey_admin_permissions",
            "assignment_upload_permissions",
            "no_permissions",
        ],
    )
    def user_permissions_with_upload(self, request):
        return request.param

    @pytest.fixture()
    def create_survey(self, client, login_test_user, csrf_token, test_user_credentials):
        """
        Insert new survey
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
    def create_module_selection(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_module_questionnaire,
    ):
        """
        Insert assignments module_selection
        """

        payload = {
            "survey_uid": 1,
            "modules": ["9"],
        }

        response = client.post(
            "/api/module-status",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_form(self, client, login_test_user, csrf_token, create_module_selection):
        """
        Insert new form
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

        yield

    @pytest.fixture()
    def create_scto_question_mapping(
        self, client, csrf_token, login_test_user, create_form
    ):
        """
        Insert SCTO question mapping as a setup step for the tests
        """

        # Insert the SCTO question mapping
        payload = {
            "form_uid": 1,
            "survey_status": "test_survey_status",
            "revisit_section": "test_revisit_section",
            "target_id": "test_target_id",
            "enumerator_id": "test_enumerator_id",
            "locations": {
                "location_1": "test_location_1",
            },
        }

        response = client.post(
            "/api/forms/1/scto-question-mapping",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201

        yield

    @pytest.fixture()
    def create_geo_levels(self, client, login_test_user, csrf_token, create_form):
        """
        Insert new geo levels
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
        Insert new locations
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
    def create_roles(self, client, login_test_user, csrf_token):
        """
        Insert new roles as a setup step
        """

        payload = {
            "roles": [
                {
                    "role_uid": None,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                    "permissions": [9],
                },
                {
                    "role_uid": None,
                    "role_name": "Cluster Coordinator",
                    "reporting_role_uid": 1,
                    "permissions": [9],
                },
                {
                    "role_uid": None,
                    "role_name": "Regional Coordinator",
                    "reporting_role_uid": 2,
                    "permissions": [9],
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
    def add_fsl_1_user(self, client, login_test_user, csrf_token, create_roles):
        """
        Add users at with field supervisor level 1 role
        """
        # Add core team user
        response = client.post(
            "/api/users",
            json={
                "survey_uid": 1,
                "email": "newuser1@example.com",
                "first_name": "Tim",
                "last_name": "Doe",
                "roles": [1],
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200
        assert b"Success: user invited" in response.data
        response_data = json.loads(response.data)
        core_user = response_data.get("user")

        return core_user

    @pytest.fixture()
    def add_fsl_2_user(self, client, login_test_user, csrf_token, create_roles):
        """
        Add users at with field supervisor level 2 role
        """
        # Add CC user
        response = client.post(
            "/api/users",
            json={
                "survey_uid": 1,
                "email": "newuser2@example.com",
                "first_name": "Ron",
                "last_name": "Doe",
                "roles": [2],
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200
        assert b"Success: user invited" in response.data
        response_data = json.loads(response.data)
        cc_user = response_data.get("user")

        return cc_user

    @pytest.fixture()
    def add_fsl_3_user(self, client, login_test_user, csrf_token, create_roles):
        """
        Add users at with field supervisor level 3 role (lowest level)
        """
        # Add RC user
        response = client.post(
            "/api/users",
            json={
                "survey_uid": 1,
                "email": "newuser3@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "roles": [3],
                "gender": "Male",
                "languages": ["Hindi", "Telugu", "English"],
                "location_uids": [1],
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200
        assert b"Success: user invited" in response.data
        response_data = json.loads(response.data)
        rc_user = response_data.get("user")

        return rc_user

    @pytest.fixture()
    def add_user_hierarchy(
        self,
        client,
        login_test_user,
        csrf_token,
        create_roles,
        add_fsl_1_user,
        add_fsl_2_user,
        add_fsl_3_user,
    ):
        """
        Define user hierarchy dependencies between fsl 1, fsl 2 and fsl 3 users added
        """

        # Add user hierarchy records between rc and cc
        payload = {
            "survey_uid": 1,
            "role_uid": 3,
            "user_uid": add_fsl_3_user["user_uid"],
            "parent_user_uid": add_fsl_2_user["user_uid"],
        }

        response = client.put(
            "/api/user-hierarchy",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        # Add user hierarchy records between cc and core user
        payload = {
            "survey_uid": 1,
            "role_uid": 2,
            "user_uid": add_fsl_2_user["user_uid"],
            "parent_user_uid": add_fsl_1_user["user_uid"],
        }

        response = client.put(
            "/api/user-hierarchy",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

    @pytest.fixture()
    def add_user_hierarchy_with_fsl_1_login(
        self,
        client,
        login_test_user,
        csrf_token,
        create_roles,
        test_user_credentials,
        add_fsl_1_user,
        add_fsl_2_user,
        add_fsl_3_user,
    ):
        """
        Add users hierarchy with test user as Field Supervisor Level 1
        """

        # Add user hierarchy records between rc and cc
        payload = {
            "survey_uid": 1,
            "role_uid": 3,
            "user_uid": add_fsl_3_user["user_uid"],
            "parent_user_uid": add_fsl_2_user["user_uid"],
        }

        response = client.put(
            "/api/user-hierarchy",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        # Add user hierarchy records between cc and core user
        payload = {
            "survey_uid": 1,
            "role_uid": 2,
            "user_uid": add_fsl_2_user["user_uid"],
            "parent_user_uid": test_user_credentials.get("user_uid"),
        }

        response = client.put(
            "/api/user-hierarchy",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

    @pytest.fixture()
    def add_user_hierarchy_with_fsl_2_login(
        self,
        client,
        login_test_user,
        csrf_token,
        create_roles,
        test_user_credentials,
        add_fsl_1_user,
        add_fsl_2_user,
        add_fsl_3_user,
    ):
        """
        Add user hierarchy with test user as Field Supervisor Level 2
        """

        # Add user hierarchy records between rc and cc
        payload = {
            "survey_uid": 1,
            "role_uid": 3,
            "user_uid": add_fsl_3_user["user_uid"],
            "parent_user_uid": test_user_credentials.get("user_uid"),
        }

        response = client.put(
            "/api/user-hierarchy",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        # Add user hierarchy records between cc and core user
        payload = {
            "survey_uid": 1,
            "role_uid": 2,
            "user_uid": test_user_credentials.get("user_uid"),
            "parent_user_uid": add_fsl_1_user["user_uid"],
        }

        response = client.put(
            "/api/user-hierarchy",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

    @pytest.fixture()
    def add_user_hierarchy_with_fsl_3_login(
        self,
        client,
        login_test_user,
        csrf_token,
        create_roles,
        test_user_credentials,
        add_fsl_1_user,
        add_fsl_2_user,
        add_fsl_3_user,
    ):
        """
        Add user hierarchy with test user as Field Supervisor Level 3
        """

        # Add user hierarchy records between rc and cc
        payload = {
            "survey_uid": 1,
            "role_uid": 3,
            "user_uid": test_user_credentials.get("user_uid"),
            "parent_user_uid": add_fsl_2_user["user_uid"],
        }

        response = client.put(
            "/api/user-hierarchy",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        # Add user hierarchy records between cc and core user
        payload = {
            "survey_uid": 1,
            "role_uid": 2,
            "user_uid": add_fsl_2_user["user_uid"],
            "parent_user_uid": add_fsl_1_user["user_uid"],
        }

        response = client.put(
            "/api/user-hierarchy",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

    @pytest.fixture()
    def update_test_user_locations(
        self, client, login_test_user, csrf_token, test_user_credentials
    ):
        """
        Function to update the test user's locations
        """

        response = client.put(
            "/api/user-locations",
            json={
                "survey_uid": 1,
                "user_uid": test_user_credentials.get("user_uid"),
                "location_uids": [1],
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

    @pytest.fixture()
    def add_custom_target_mapping_test_user(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        update_test_user_locations,
    ):
        """
        Function to add custom target to supervisor mapping for testing access restrictions
        """
        # First give the test user the necessary role to be able to map targets
        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
            roles=[3],  # FS L3 role
            location_uids=[1],
        )

        # Add mapping
        payload = {
            "form_uid": 1,
            "mappings": [
                {
                    "target_uid": 1,
                    "supervisor_uid": test_user_credentials.get("user_uid"),
                }
            ],
        }
        response = client.put(
            "/api/mapping/targets-mapping",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

    @pytest.fixture()
    def add_custom_surveyor_mapping_test_user(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        update_test_user_locations,
    ):
        """
        Function to add custom surveyor to supervisor mapping for testing access restrictions
        """
        # First give the test user the necessary role to be able to map targets
        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
            roles=[3],  # FS L3 role
            location_uids=[1],
        )

        # Add mapping
        payload = {
            "form_uid": 1,
            "mappings": [
                {
                    "enumerator_uid": 1,
                    "supervisor_uid": test_user_credentials.get("user_uid"),
                }
            ],
        }
        response = client.put(
            "/api/mapping/surveyors-mapping",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

    @pytest.fixture()
    def create_enumerator_column_config(
        self, client, login_test_user, create_form, csrf_token
    ):
        """
        Create the enumerators column config
        """

        payload = {
            "form_uid": 1,
            "column_config": [
                {
                    "column_name": "enumerator_id",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "name",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "email",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "mobile_primary",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "language",
                    "column_type": "personal_details",
                    "bulk_editable": True,
                },
                {
                    "column_name": "home_address",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "gender",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "prime_geo_level_location",
                    "column_type": "location",
                    "bulk_editable": True,
                },
                {
                    "column_name": "Mobile (Secondary)",
                    "column_type": "custom_fields",
                    "bulk_editable": True,
                },
                {
                    "column_name": "Age",
                    "column_type": "custom_fields",
                    "bulk_editable": False,
                },
            ],
        }

        response = client.put(
            "/api/enumerators/column-config",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_enumerator_column_config_no_locations(
        self, client, login_test_user, create_form, csrf_token
    ):
        """
        Create the enumerators column config without a location column type
        """

        payload = {
            "form_uid": 1,
            "column_config": [
                {
                    "column_name": "enumerator_id",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "name",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "email",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "mobile_primary",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "language",
                    "column_type": "personal_details",
                    "bulk_editable": True,
                },
                {
                    "column_name": "home_address",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "gender",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "Mobile (Secondary)",
                    "column_type": "custom_fields",
                    "bulk_editable": True,
                },
                {
                    "column_name": "Age",
                    "column_type": "custom_fields",
                    "bulk_editable": False,
                },
            ],
        }

        response = client.put(
            "/api/enumerators/column-config",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_enumerator_column_config_no_custom_fields(
        self, client, login_test_user, create_form, csrf_token
    ):
        """
        Create the enumerators column config without custom fields
        """

        payload = {
            "form_uid": 1,
            "column_config": [
                {
                    "column_name": "enumerator_id",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "name",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "email",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "mobile_primary",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "language",
                    "column_type": "personal_details",
                    "bulk_editable": True,
                },
                {
                    "column_name": "home_address",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "gender",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "prime_geo_level_location",
                    "column_type": "location",
                    "bulk_editable": True,
                },
            ],
        }

        response = client.put(
            "/api/enumerators/column-config",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        yield

    @pytest.fixture()
    def upload_enumerators_csv(
        self, client, login_test_user, create_locations, csrf_token
    ):
        """
        Insert enumerators
        Include a custom field
        Include a location id column that corresponds to the prime geo level for the survey (district)
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
        assert response.status_code == 200

    @pytest.fixture()
    def upload_enumerators_csv_no_locations(
        self,
        client,
        login_test_user,
        create_locations,
        update_surveyor_mapping_criteria,
        csrf_token,
    ):
        """
        Insert enumerators
        Include a custom field
        Don't include a location id column
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_enumerators_no_locations.csv"
        )

        # Read the enumerators.csv file and convert it to base64
        with open(filepath, "rb") as f:
            enumerators_csv = f.read()
            enumerators_csv_encoded = base64.b64encode(enumerators_csv).decode("utf-8")

        # Try to upload the enumerators csv
        payload = {
            "column_mapping": {
                "enumerator_id": "enumerator_id",
                "name": "name",
                "email": "email",
                "mobile_primary": "mobile_primary",
                "language": "language",
                "home_address": "home_address",
                "gender": "gender",
                "enumerator_type": "enumerator_type",
                "custom_fields": [
                    {
                        "field_label": "Mobile (Secondary)",
                        "column_name": "mobile_secondary",
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

        assert response.status_code == 200

    @pytest.fixture()
    def upload_enumerators_csv_no_locations_no_geo_levels_defined(
        self,
        client,
        login_test_user,
        create_form,
        update_surveyor_mapping_criteria,
        csrf_token,
    ):
        """
        Insert enumerators
        Include a custom field
        Don't include a location id column
        Don't define geo levels or locations for the survey
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_enumerators_no_locations.csv"
        )

        # Read the enumerators.csv file and convert it to base64
        with open(filepath, "rb") as f:
            enumerators_csv = f.read()
            enumerators_csv_encoded = base64.b64encode(enumerators_csv).decode("utf-8")

        # Try to upload the enumerators csv
        payload = {
            "column_mapping": {
                "enumerator_id": "enumerator_id",
                "name": "name",
                "email": "email",
                "mobile_primary": "mobile_primary",
                "language": "language",
                "home_address": "home_address",
                "gender": "gender",
                "enumerator_type": "enumerator_type",
                "custom_fields": [
                    {
                        "field_label": "Mobile (Secondary)",
                        "column_name": "mobile_secondary",
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

        assert response.status_code == 200

    @pytest.fixture()
    def upload_enumerators_csv_no_custom_fields(
        self, client, login_test_user, create_locations, csrf_token
    ):
        """
        Insert enumerators
        Don't include a custom field
        Include a location id column
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_enumerators_no_custom_fields.csv"
        )

        # Read the enumerators.csv file and convert it to base64
        with open(filepath, "rb") as f:
            enumerators_csv = f.read()
            enumerators_csv_encoded = base64.b64encode(enumerators_csv).decode("utf-8")

        # Try to upload the enumerators csv
        payload = {
            "column_mapping": {
                "enumerator_id": "enumerator_id",
                "name": "name",
                "email": "email",
                "mobile_primary": "mobile_primary",
                "language": "language",
                "home_address": "home_address",
                "gender": "gender",
                "enumerator_type": "enumerator_type",
                "location_id_column": "district_id",
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

        assert response.status_code == 200

    @pytest.fixture()
    def upload_enumerators_csv_mandal_prime_geo_level(
        self, client, login_test_user, create_locations, csrf_token
    ):
        """
        Insert enumerators
        Include a custom field
        Include a location id column - use mandal as the prime geo level instead of district
        """

        # Update the survey config to have mandal as the prime geo level

        payload = {
            "survey_uid": 1,
            "survey_id": "test_survey",
            "survey_name": "Test Survey",
            "survey_description": "A test survey",
            "project_name": "Test Project",
            "surveying_method": "in-person",
            "irb_approval": "Yes",
            "planned_start_date": "2021-01-01",
            "planned_end_date": "2021-12-31",
            "state": "Draft",
            "prime_geo_level_uid": 2,
            "config_status": "In Progress - Configuration",
        }

        response = client.put(
            "/api/surveys/1/basic-information",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_enumerators_mandal_prime_geo_level.csv"
        )

        # Read the enumerators.csv file and convert it to base64
        with open(filepath, "rb") as f:
            enumerators_csv = f.read()
            enumerators_csv_encoded = base64.b64encode(enumerators_csv).decode("utf-8")

        # Try to upload the enumerators csv
        payload = {
            "column_mapping": {
                "enumerator_id": "enumerator_id",
                "name": "name",
                "email": "email",
                "mobile_primary": "mobile_primary",
                "language": "language",
                "home_address": "home_address",
                "gender": "gender",
                "enumerator_type": "enumerator_type",
                "location_id_column": "mandal_id",
                "custom_fields": [
                    {
                        "field_label": "Mobile (Secondary)",
                        "column_name": "mobile_secondary",
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
        assert response.status_code == 200

    @pytest.fixture()
    def create_target_config(self, client, login_test_user, create_form, csrf_token):
        """
        Load target config table for tests with form inputs
        """

        payload = {
            "form_uid": 1,
            "target_source": "csv",
        }

        response = client.post(
            "/api/targets/config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

    @pytest.fixture()
    def create_target_column_config(
        self, client, login_test_user, create_form, csrf_token
    ):
        """
        Upload the targets column config
        """

        payload = {
            "form_uid": 1,
            "column_config": [
                {
                    "column_name": "target_id",
                    "column_type": "basic_details",
                    "bulk_editable": False,
                    "contains_pii": False,
                    "column_source": "target_id1",
                },
                {
                    "column_name": "language",
                    "column_type": "basic_details",
                    "bulk_editable": True,
                    "contains_pii": True,
                    "column_source": "language",
                },
                {
                    "column_name": "gender",
                    "column_type": "basic_details",
                    "bulk_editable": False,
                    "contains_pii": True,
                    "column_source": "gender",
                },
                {
                    "column_name": "Name",
                    "column_type": "custom_fields",
                    "bulk_editable": False,
                    "contains_pii": True,
                    "column_source": "name",
                },
                {
                    "column_name": "Mobile no.",
                    "column_type": "custom_fields",
                    "bulk_editable": False,
                    "contains_pii": True,
                    "column_source": "mobile_primary",
                },
                {
                    "column_name": "Address",
                    "column_type": "custom_fields",
                    "bulk_editable": True,
                    "contains_pii": True,
                    "column_source": "address",
                },
                {
                    "column_name": "bottom_geo_level_location",
                    "column_type": "location",
                    "bulk_editable": True,
                    "contains_pii": True,
                    "column_source": "psu_id",
                },
            ],
        }

        response = client.put(
            "/api/targets/column-config",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_target_column_config_no_locations(
        self, client, login_test_user, create_form, csrf_token
    ):
        """
        Upload the targets column config without a location column type
        """

        payload = {
            "form_uid": 1,
            "column_config": [
                {
                    "column_name": "target_id",
                    "column_type": "basic_details",
                    "bulk_editable": False,
                    "contains_pii": False,
                    "column_source": "target_id1",
                },
                {
                    "column_name": "language",
                    "column_type": "basic_details",
                    "bulk_editable": True,
                    "contains_pii": True,
                    "column_source": "language",
                },
                {
                    "column_name": "gender",
                    "column_type": "basic_details",
                    "bulk_editable": False,
                    "contains_pii": True,
                    "column_source": "gender",
                },
                {
                    "column_name": "Name",
                    "column_type": "custom_fields",
                    "bulk_editable": False,
                    "contains_pii": True,
                    "column_source": "name",
                },
                {
                    "column_name": "Mobile no.",
                    "column_type": "custom_fields",
                    "bulk_editable": False,
                    "contains_pii": True,
                    "column_source": "mobile_primary",
                },
                {
                    "column_name": "Address",
                    "column_type": "custom_fields",
                    "bulk_editable": True,
                    "contains_pii": True,
                    "column_source": "address",
                },
            ],
        }

        response = client.put(
            "/api/targets/column-config",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_target_column_config_no_custom_fields(
        self, client, login_test_user, create_form, csrf_token
    ):
        """
        Upload the targets column config without custom fields
        """

        payload = {
            "form_uid": 1,
            "column_config": [
                {
                    "column_name": "target_id",
                    "column_type": "basic_details",
                    "bulk_editable": False,
                    "contains_pii": False,
                    "column_source": "target_id1",
                },
                {
                    "column_name": "language",
                    "column_type": "basic_details",
                    "bulk_editable": True,
                    "contains_pii": True,
                    "column_source": "language",
                },
                {
                    "column_name": "gender",
                    "column_type": "basic_details",
                    "bulk_editable": False,
                    "contains_pii": True,
                    "column_source": "gender",
                },
                {
                    "column_name": "bottom_geo_level_location",
                    "column_type": "location",
                    "bulk_editable": True,
                    "contains_pii": True,
                    "column_source": "psu_id",
                },
            ],
        }

        response = client.put(
            "/api/targets/column-config",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        yield

    @pytest.fixture()
    def upload_targets_csv(
        self,
        client,
        login_test_user,
        create_locations,
        create_target_config,
        csrf_token,
    ):
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

    @pytest.fixture()
    def update_target_mapping_criteria(self, client, csrf_token):
        """
        Method to update the mapping criteria to Langauge for testing assignments without location
        """

        # Update target_mapping_criteria to gender
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
    def update_surveyor_mapping_criteria(self, client, csrf_token):
        """
        Method to update the mapping criteria to Langauge for testing enumerators without location
        """

        # Update surveyor_mapping_criteria to gender
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
    def upload_targets_csv_no_locations(
        self,
        client,
        login_test_user,
        create_locations,
        update_target_mapping_criteria,
        csrf_token,
    ):
        """
        Upload the targets csv with no locations
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_targets_no_locations.csv"
        )

        # Read the targets.csv file and convert it to base64
        with open(filepath, "rb") as f:
            targets_csv = f.read()
            targets_csv_encoded = base64.b64encode(targets_csv).decode("utf-8")

        # Try to upload the targets csv
        payload = {
            "column_mapping": {
                "target_id": "target_id",
                "language": "language",
                "gender": "gender",
                "custom_fields": [
                    {
                        "field_label": "Mobile no.",
                        "column_name": "mobile_primary",
                    },
                    {
                        "field_label": "Name",
                        "column_name": "name",
                    },
                    {
                        "field_label": "Address",
                        "column_name": "address",
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
        print(response)
        assert response.status_code == 200

    @pytest.fixture()
    def upload_targets_csv_no_custom_fields(
        self, client, login_test_user, create_locations, csrf_token
    ):
        """
        Upload the targets csv with no custom fields
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_targets_no_custom_fields.csv"
        )

        # Read the targets.csv file and convert it to base64
        with open(filepath, "rb") as f:
            targets_csv = f.read()
            targets_csv_encoded = base64.b64encode(targets_csv).decode("utf-8")

        # Try to upload the targets csv
        payload = {
            "column_mapping": {
                "target_id": "target_id",
                "language": "language",
                "gender": "gender",
                "location_id_column": "psu_id",
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

    @pytest.fixture
    def create_email_config(
        self, client, login_test_user, csrf_token, test_user_credentials, create_form
    ):
        """
        Insert an email config as a setup step for email tests
        """
        payload = {
            "config_name": "AssignmentsConfig",
            "form_uid": 1,
            "report_users": [1, 2, 3],
            "email_source": "SurveyStream Data",
            "email_source_gsheet_link": "test_key",
            "email_source_gsheet_tab": "test_tab",
            "email_source_gsheet_header_row": 1,
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
        Insert email template as a setup for tests
        """
        payload = {
            "subject": "Test Assignments Email",
            "language": "english",
            "content": "Test Content",
            "email_config_uid": create_email_config["email_config_uid"],
            "variable_list": [],
            "table_list": [
                {
                    "table_name": "Assignments: Default",
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
                                    "table_name": "Assignments: Default",
                                    "filter_variable": "test_column",
                                    "filter_operator": "Is",
                                    "filter_value": "test_value",
                                },
                                {
                                    "table_name": "Assignments: Default",
                                    "filter_variable": "test_column2",
                                    "filter_operator": "Is",
                                    "filter_value": "test_value2",
                                },
                            ]
                        },
                        {
                            "filter_group": [
                                {
                                    "table_name": "Assignments: Default",
                                    "filter_variable": "test_column",
                                    "filter_operator": "Is",
                                    "filter_value": "test_value",
                                },
                                {
                                    "table_name": "Assignments: Default",
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

        schedules = []

        # this will create 3 schedules with future dates starting with the current date
        # this is helpful because it will help with create assignment tests where we check for the next possible date
        for i in range(3):
            # Calculate future dates
            future_dates = [
                (current_datetime + timedelta(days=j)).strftime("%Y-%m-%d")
                for j in range(1 + i * 3, 4 + i * 3)
            ]
            # Add today's date

            # Calculate different times
            current_time = (current_datetime + timedelta(hours=i + 2)).time()

            # Calculate time based on iteration
            if i == 0:
                current_time_past = (current_datetime - timedelta(hours=i + 2)).time()
                formatted_time = current_time_past.strftime("%H:%M")
                future_dates.append(current_datetime.strftime("%Y-%m-%d"))
            elif i == 2:
                future_dates.append(current_datetime.strftime("%Y-%m-%d"))
                formatted_time = current_time.strftime("%H:%M")

            else:
                formatted_time = current_time.strftime("%H:%M")

            # Create payload
            payload = {
                "dates": future_dates,
                "time": formatted_time,
                "email_config_uid": create_email_config["email_config_uid"],
                "email_schedule_name": "Test Schedule " + str(i),
            }

            # Send request
            response = client.post(
                "/api/emails/schedule",
                json=payload,
                content_type="application/json",
                headers={"X-CSRF-Token": csrf_token},
            )
            assert response.status_code == 201

            # Append schedule data to the list
            schedules.append(response.json["data"])
        return schedules[0]

    @pytest.fixture
    def create_assignments(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Test fixture for initializing assignments

        """
        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 1},
                {"target_uid": 2, "enumerator_uid": 2},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1, "validate_mapping": True},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

    ####################################################
    ## FIXTURES END HERE
    ####################################################

    def test_assignments_no_enumerators_no_targets(
        self, client, login_test_user, create_locations, add_user_hierarchy, csrf_token
    ):
        """
        Test the assignments endpoint response when key datasets are missing
        No enumerators
        No targets
        """

        expected_response = {
            "errors": {
                "message": "Targets and enumerators are not available for this form. Kindly upload targets and enumerators first."
            },
            "success": False,
        }

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignments_no_roles(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
        upload_targets_csv,
        upload_enumerators_csv,
    ):
        """
        Test the assignments endpoint response when key datasets are missing
        No roles
        When no roles are defined, the response should be a 422 error
        """

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        assert response.status_code == 422
        expected_response = {
            "errors": {
                "mapping_errors": "Roles not configured for the survey. Cannot perform target to supervisor mapping without roles."
            },
            "success": False,
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignments_no_targets(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        add_user_hierarchy,
        csrf_token,
        user_permissions,
        request,
    ):
        """
        Test the assignments endpoint response when key datasets are missing - multiple user roles
        No targets
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        if expected_permission:
            expected_response = {
                "errors": {
                    "message": "Targets are not available for this form. Kindly upload targets first.",
                },
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Assignments",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_assignments_no_enumerators(
        self,
        client,
        login_test_user,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
        user_permissions,
        request,
    ):
        """
        Test the assignments endpoint response when key datasets are missing - multiple user roles
        No enumerators
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        if expected_permission:
            expected_response = {
                "errors": {
                    "message": "Enumerators are not available for this form. Kindly upload enumerators first.",
                },
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Assignments",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_assignments_schedule_email(
        self,
        client,
        login_test_user,
        create_geo_levels,
        create_roles,
        create_email_config,
        csrf_token,
        user_permissions,
        request,
    ):
        """
        Test the assignments endpoint for scheduling emails - multiple roles

        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        current_datetime = datetime.now()

        current_datetime = current_datetime.strftime("%Y-%m-%d")

        payload = {
            "form_uid": 1,
            "email_config_uid": 1,
            "date": current_datetime,
            "time": "08:00",
            "recipients": [1, 2, 3],  # there are supposed to be enumerator ids
            "template_uid": 1,
            "status": "queued",
        }

        # Check the response
        response = client.post(
            f"/api/assignments/schedule-email",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            expected_response = {
                "message": "Manual email trigger created successfully",
                "success": True,
            }

            assert response.status_code == 201
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: WRITE Assignments",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_assignments_schedule_email_past_date(
        self,
        client,
        login_test_user,
        create_geo_levels,
        create_roles,
        csrf_token,
        user_permissions,
        request,
    ):
        """
        Test the assignments endpoint for scheduling emails past date - multiple roles
        Expect validation error

        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "form_uid": 1,
            "email_config_uid": 1,
            "date": "2024-02-03",
            "time": "08:00",
            "recipients": [1, 2, 3],  # there are supposed to be enumerator ids
            "template_uid": 1,
            "status": "queued",
        }

        # Check the response
        response = client.post(
            f"/api/assignments/schedule-email",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        expected_response = {
            "message": {"date": ["Date must be in the future."]},
            "success": False,
        }

        assert response.status_code == 422
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignments_empty_assignment_table(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
        user_permissions,
        request,
    ):
        """
        Test the assignments endpoint response when the assignment table is empty
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)
        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        if expected_permission:
            # Since this user is not mapped to child users with target mapping, the response should be empty
            if user_fixture != "user_with_assignment_permissions":
                expected_response = {
                    "data": [
                        {
                            "assigned_enumerator_custom_fields": None,
                            "assigned_enumerator_email": None,
                            "assigned_enumerator_gender": None,
                            "assigned_enumerator_home_address": None,
                            "assigned_enumerator_id": None,
                            "assigned_enumerator_language": None,
                            "assigned_enumerator_mobile_primary": None,
                            "assigned_enumerator_name": None,
                            "assigned_enumerator_uid": None,
                            "completed_flag": None,
                            "custom_fields": {
                                "Address": "Hyderabad",
                                "Mobile no.": "1234567890",
                                "Name": "Anil",
                                "column_mapping": {
                                    "custom_fields": [
                                        {
                                            "column_name": "mobile_primary1",
                                            "field_label": "Mobile no.",
                                        },
                                        {"column_name": "name1", "field_label": "Name"},
                                        {
                                            "column_name": "address1",
                                            "field_label": "Address",
                                        },
                                    ],
                                    "gender": "gender1",
                                    "language": "language1",
                                    "location_id_column": "psu_id1",
                                    "target_id": "target_id1",
                                },
                            },
                            "form_uid": 1,
                            "gender": "Male",
                            "language": "Telugu",
                            "last_attempt_survey_status": None,
                            "last_attempt_survey_status_label": "Not Attempted",
                            "final_survey_status": None,
                            "final_survey_status_label": "Not Attempted",
                            "scto_fields": None,
                            "supervisors": [
                                {
                                    "role_name": "Regional Coordinator",
                                    "role_uid": 3,
                                    "supervisor_email": "newuser3@example.com",
                                    "supervisor_name": "John Doe",
                                },
                                {
                                    "role_name": "Cluster Coordinator",
                                    "role_uid": 2,
                                    "supervisor_email": "newuser2@example.com",
                                    "supervisor_name": "Ron Doe",
                                },
                                {
                                    "role_name": "Core User",
                                    "role_uid": 1,
                                    "supervisor_email": "newuser1@example.com",
                                    "supervisor_name": "Tim Doe",
                                },
                            ],
                            "location_uid": 4,
                            "num_attempts": 0,
                            "refusal_flag": None,
                            "revisit_sections": None,
                            "target_assignable": True,
                            "target_id": "1",
                            "target_locations": [
                                {
                                    "geo_level_name": "District",
                                    "geo_level_uid": 1,
                                    "location_id": "1",
                                    "location_name": "ADILABAD",
                                    "location_uid": 1,
                                },
                                {
                                    "geo_level_name": "Mandal",
                                    "geo_level_uid": 2,
                                    "location_id": "1101",
                                    "location_name": "ADILABAD RURAL",
                                    "location_uid": 2,
                                },
                                {
                                    "geo_level_name": "PSU",
                                    "geo_level_uid": 3,
                                    "location_id": "17101102",
                                    "location_name": "ANKOLI",
                                    "location_uid": 4,
                                },
                            ],
                            "target_uid": 1,
                            "webapp_tag_color": None,
                        },
                        {
                            "assigned_enumerator_custom_fields": None,
                            "assigned_enumerator_email": None,
                            "assigned_enumerator_gender": None,
                            "assigned_enumerator_home_address": None,
                            "assigned_enumerator_id": None,
                            "assigned_enumerator_language": None,
                            "assigned_enumerator_mobile_primary": None,
                            "assigned_enumerator_name": None,
                            "assigned_enumerator_uid": None,
                            "completed_flag": None,
                            "custom_fields": {
                                "Address": "South Delhi",
                                "Mobile no.": "1234567891",
                                "Name": "Anupama",
                                "column_mapping": {
                                    "custom_fields": [
                                        {
                                            "column_name": "mobile_primary1",
                                            "field_label": "Mobile no.",
                                        },
                                        {"column_name": "name1", "field_label": "Name"},
                                        {
                                            "column_name": "address1",
                                            "field_label": "Address",
                                        },
                                    ],
                                    "gender": "gender1",
                                    "language": "language1",
                                    "location_id_column": "psu_id1",
                                    "target_id": "target_id1",
                                },
                            },
                            "form_uid": 1,
                            "gender": "Female",
                            "language": "Hindi",
                            "last_attempt_survey_status": None,
                            "last_attempt_survey_status_label": "Not Attempted",
                            "final_survey_status": None,
                            "final_survey_status_label": "Not Attempted",
                            "scto_fields": None,
                            "supervisors": [
                                {
                                    "role_name": "Regional Coordinator",
                                    "role_uid": 3,
                                    "supervisor_email": "newuser3@example.com",
                                    "supervisor_name": "John Doe",
                                },
                                {
                                    "role_name": "Cluster Coordinator",
                                    "role_uid": 2,
                                    "supervisor_email": "newuser2@example.com",
                                    "supervisor_name": "Ron Doe",
                                },
                                {
                                    "role_name": "Core User",
                                    "role_uid": 1,
                                    "supervisor_email": "newuser1@example.com",
                                    "supervisor_name": "Tim Doe",
                                },
                            ],
                            "location_uid": 4,
                            "num_attempts": 0,
                            "refusal_flag": None,
                            "revisit_sections": None,
                            "target_assignable": True,
                            "target_id": "2",
                            "target_locations": [
                                {
                                    "geo_level_name": "District",
                                    "geo_level_uid": 1,
                                    "location_id": "1",
                                    "location_name": "ADILABAD",
                                    "location_uid": 1,
                                },
                                {
                                    "geo_level_name": "Mandal",
                                    "geo_level_uid": 2,
                                    "location_id": "1101",
                                    "location_name": "ADILABAD RURAL",
                                    "location_uid": 2,
                                },
                                {
                                    "geo_level_name": "PSU",
                                    "geo_level_uid": 3,
                                    "location_id": "17101102",
                                    "location_name": "ANKOLI",
                                    "location_uid": 4,
                                },
                            ],
                            "target_uid": 2,
                            "webapp_tag_color": None,
                        },
                    ],
                    "success": True,
                }
            else:
                # User has no child supervisors
                expected_response = {"data": [], "success": True}

            print(response.json)
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Assignments",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_create_assignment(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
        user_permissions,
        request,
        create_email_config,
        create_email_schedule,
        create_email_template,
    ):
        """
        Create an assignment between a single target and enumerator
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "assignments": [{"target_uid": 1, "enumerator_uid": 1}],
            "form_uid": 1,
            "validate_mapping": True,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        current_datetime = datetime.now()
        formatted_date = current_datetime.strftime("%a, %d %b %Y") + " 00:00:00 GMT"

        current_time = datetime.now().strftime("%H:%M")

        # Define the format corresponding to the date string
        date_format = "%a, %d %b %Y %H:%M:%S %Z"

        if expected_permission:
            if user_fixture != "user_with_assignment_permissions":
                assert response.status_code == 200
                assert datetime.strptime(
                    response.json["data"]["email_schedule"][0]["schedule_date"],
                    date_format,
                ) >= datetime.strptime(formatted_date, date_format)
                expected_put_response = {
                    "data": {
                        "assignments_count": 1,
                        "new_assignments_count": 1,
                        "no_changes_count": 0,
                        "re_assignments_count": 0,
                        "email_schedule": [
                            {
                                "config_name": "AssignmentsConfig",
                                "dates": response.json["data"]["email_schedule"][0][
                                    "dates"
                                ],
                                "schedule_date": response.json["data"][
                                    "email_schedule"
                                ][0]["schedule_date"],
                                "current_time": current_time,
                                "email_schedule_uid": response.json["data"][
                                    "email_schedule"
                                ][0]["email_schedule_uid"],
                                "email_config_uid": 1,
                                "time": response.json["data"]["email_schedule"][0][
                                    "time"
                                ],
                            }
                        ],
                    },
                    "message": "Success",
                }

                checkdiff = jsondiff.diff(expected_put_response, response.json)
                assert checkdiff == {}

                expected_response = {
                    "data": [
                        {
                            "assigned_enumerator_custom_fields": {
                                "Age": "1",
                                "Mobile (Secondary)": "1123456789",
                                "column_mapping": {
                                    "custom_fields": [
                                        {
                                            "column_name": "mobile_secondary1",
                                            "field_label": "Mobile (Secondary)",
                                        },
                                        {"column_name": "age1", "field_label": "Age"},
                                    ],
                                    "email": "email1",
                                    "enumerator_id": "enumerator_id1",
                                    "enumerator_type": "enumerator_type1",
                                    "gender": "gender1",
                                    "home_address": "home_address1",
                                    "language": "language1",
                                    "location_id_column": "district_id1",
                                    "mobile_primary": "mobile_primary1",
                                    "name": "name1",
                                },
                            },
                            "assigned_enumerator_email": "eric.dodge@idinsight.org",
                            "assigned_enumerator_gender": "Male",
                            "assigned_enumerator_home_address": "my house",
                            "assigned_enumerator_id": "0294612",
                            "assigned_enumerator_language": "English",
                            "assigned_enumerator_mobile_primary": "0123456789",
                            "assigned_enumerator_name": "Eric Dodge",
                            "assigned_enumerator_uid": 1,
                            "completed_flag": None,
                            "custom_fields": {
                                "Address": "Hyderabad",
                                "Mobile no.": "1234567890",
                                "Name": "Anil",
                                "column_mapping": {
                                    "custom_fields": [
                                        {
                                            "column_name": "mobile_primary1",
                                            "field_label": "Mobile no.",
                                        },
                                        {"column_name": "name1", "field_label": "Name"},
                                        {
                                            "column_name": "address1",
                                            "field_label": "Address",
                                        },
                                    ],
                                    "gender": "gender1",
                                    "language": "language1",
                                    "location_id_column": "psu_id1",
                                    "target_id": "target_id1",
                                },
                            },
                            "form_uid": 1,
                            "gender": "Male",
                            "language": "Telugu",
                            "last_attempt_survey_status": None,
                            "last_attempt_survey_status_label": "Not Attempted",
                            "final_survey_status": None,
                            "final_survey_status_label": "Not Attempted",
                            "scto_fields": None,
                            "supervisors": [
                                {
                                    "role_name": "Regional Coordinator",
                                    "role_uid": 3,
                                    "supervisor_email": "newuser3@example.com",
                                    "supervisor_name": "John Doe",
                                },
                                {
                                    "role_name": "Cluster Coordinator",
                                    "role_uid": 2,
                                    "supervisor_email": "newuser2@example.com",
                                    "supervisor_name": "Ron Doe",
                                },
                                {
                                    "role_name": "Core User",
                                    "role_uid": 1,
                                    "supervisor_email": "newuser1@example.com",
                                    "supervisor_name": "Tim Doe",
                                },
                            ],
                            "location_uid": 4,
                            "num_attempts": 0,
                            "refusal_flag": None,
                            "revisit_sections": None,
                            "target_assignable": True,
                            "target_id": "1",
                            "target_locations": [
                                {
                                    "geo_level_name": "District",
                                    "geo_level_uid": 1,
                                    "location_id": "1",
                                    "location_name": "ADILABAD",
                                    "location_uid": 1,
                                },
                                {
                                    "geo_level_name": "Mandal",
                                    "geo_level_uid": 2,
                                    "location_id": "1101",
                                    "location_name": "ADILABAD RURAL",
                                    "location_uid": 2,
                                },
                                {
                                    "geo_level_name": "PSU",
                                    "geo_level_uid": 3,
                                    "location_id": "17101102",
                                    "location_name": "ANKOLI",
                                    "location_uid": 4,
                                },
                            ],
                            "target_uid": 1,
                            "webapp_tag_color": None,
                        },
                        {
                            "assigned_enumerator_custom_fields": None,
                            "assigned_enumerator_email": None,
                            "assigned_enumerator_gender": None,
                            "assigned_enumerator_home_address": None,
                            "assigned_enumerator_id": None,
                            "assigned_enumerator_language": None,
                            "assigned_enumerator_mobile_primary": None,
                            "assigned_enumerator_name": None,
                            "assigned_enumerator_uid": None,
                            "completed_flag": None,
                            "custom_fields": {
                                "Address": "South Delhi",
                                "Mobile no.": "1234567891",
                                "Name": "Anupama",
                                "column_mapping": {
                                    "custom_fields": [
                                        {
                                            "column_name": "mobile_primary1",
                                            "field_label": "Mobile no.",
                                        },
                                        {"column_name": "name1", "field_label": "Name"},
                                        {
                                            "column_name": "address1",
                                            "field_label": "Address",
                                        },
                                    ],
                                    "gender": "gender1",
                                    "language": "language1",
                                    "location_id_column": "psu_id1",
                                    "target_id": "target_id1",
                                },
                            },
                            "form_uid": 1,
                            "gender": "Female",
                            "language": "Hindi",
                            "last_attempt_survey_status": None,
                            "last_attempt_survey_status_label": "Not Attempted",
                            "final_survey_status": None,
                            "final_survey_status_label": "Not Attempted",
                            "scto_fields": None,
                            "supervisors": [
                                {
                                    "role_name": "Regional Coordinator",
                                    "role_uid": 3,
                                    "supervisor_email": "newuser3@example.com",
                                    "supervisor_name": "John Doe",
                                },
                                {
                                    "role_name": "Cluster Coordinator",
                                    "role_uid": 2,
                                    "supervisor_email": "newuser2@example.com",
                                    "supervisor_name": "Ron Doe",
                                },
                                {
                                    "role_name": "Core User",
                                    "role_uid": 1,
                                    "supervisor_email": "newuser1@example.com",
                                    "supervisor_name": "Tim Doe",
                                },
                            ],
                            "location_uid": 4,
                            "num_attempts": 0,
                            "refusal_flag": None,
                            "revisit_sections": None,
                            "target_assignable": True,
                            "target_id": "2",
                            "target_locations": [
                                {
                                    "geo_level_name": "District",
                                    "geo_level_uid": 1,
                                    "location_id": "1",
                                    "location_name": "ADILABAD",
                                    "location_uid": 1,
                                },
                                {
                                    "geo_level_name": "Mandal",
                                    "geo_level_uid": 2,
                                    "location_id": "1101",
                                    "location_name": "ADILABAD RURAL",
                                    "location_uid": 2,
                                },
                                {
                                    "geo_level_name": "PSU",
                                    "geo_level_uid": 3,
                                    "location_id": "17101102",
                                    "location_name": "ANKOLI",
                                    "location_uid": 4,
                                },
                            ],
                            "target_uid": 2,
                            "webapp_tag_color": None,
                        },
                    ],
                    "success": True,
                }
                # Check the response
                response = client.get("/api/assignments", query_string={"form_uid": 1})

                print(response.json)
                checkdiff = jsondiff.diff(expected_response, response.json)
                assert checkdiff == {}

            else:
                # Can't save assignments since user doesn't have access to the targets as per mapping
                assert response.status_code == 422
                expected_put_response = {
                    "errors": {
                        "message": "The following target ID's are not assignable by the current user: 1. Kindly refresh and try again.",
                        "not_mapped_target_uids": [1],
                    },
                    "success": False,
                }

                print(response.json)
                checkdiff = jsondiff.diff(expected_put_response, response.json)
                assert checkdiff == {}

        else:
            assert response.status_code == 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: WRITE Assignments",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_create_assignment_no_locations(
        self,
        client,
        login_test_user,
        upload_enumerators_csv_no_locations,
        upload_targets_csv_no_locations,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Create an assignment between a single target and enumerator
        We want to do this with targets/enumerators that don't have locations to make sure the response is correct
        """

        payload = {
            "assignments": [{"target_uid": 1, "enumerator_uid": 1}],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        expected_response = {
            "data": [
                {
                    "assigned_enumerator_custom_fields": {
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary",
                                    "field_label": "Mobile (Secondary)",
                                }
                            ],
                            "email": "email",
                            "enumerator_id": "enumerator_id",
                            "enumerator_type": "enumerator_type",
                            "gender": "gender",
                            "home_address": "home_address",
                            "language": "language",
                            "mobile_primary": "mobile_primary",
                            "name": "name",
                        },
                    },
                    "assigned_enumerator_email": "eric.dodge@idinsight.org",
                    "assigned_enumerator_gender": "Male",
                    "assigned_enumerator_home_address": "my house",
                    "assigned_enumerator_id": "0294612",
                    "assigned_enumerator_language": "English",
                    "assigned_enumerator_mobile_primary": "0123456789",
                    "assigned_enumerator_name": "Eric Dodge",
                    "assigned_enumerator_uid": 1,
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "Hyderabad",
                        "Mobile no.": "1234567890",
                        "Name": "Anil",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name", "field_label": "Name"},
                                {"column_name": "address", "field_label": "Address"},
                            ],
                            "gender": "gender",
                            "language": "language",
                            "target_id": "target_id",
                        },
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                    ],
                    "location_uid": None,
                    "num_attempts": 0,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": True,
                    "target_id": "1",
                    "target_locations": None,
                    "target_uid": 1,
                    "webapp_tag_color": None,
                },
                {
                    "assigned_enumerator_custom_fields": None,
                    "assigned_enumerator_email": None,
                    "assigned_enumerator_gender": None,
                    "assigned_enumerator_home_address": None,
                    "assigned_enumerator_id": None,
                    "assigned_enumerator_language": None,
                    "assigned_enumerator_mobile_primary": None,
                    "assigned_enumerator_name": None,
                    "assigned_enumerator_uid": None,
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "South Delhi",
                        "Mobile no.": "1234567891",
                        "Name": "Anupama",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name", "field_label": "Name"},
                                {"column_name": "address", "field_label": "Address"},
                            ],
                            "gender": "gender",
                            "language": "language",
                            "target_id": "target_id",
                        },
                    },
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                    ],
                    "location_uid": None,
                    "num_attempts": 0,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": True,
                    "target_id": "2",
                    "target_locations": None,
                    "target_uid": 2,
                    "webapp_tag_color": None,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_create_assignment_no_email_config(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Create an assignment between a single target and enumerator without email config
        """
        payload = {
            "assignments": [{"target_uid": 1, "enumerator_uid": 1}],
            "form_uid": 1,
            "validate_mapping": True,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        current_datetime = datetime.now()
        formatted_date = current_datetime.strftime("%a, %d %b %Y") + " 00:00:00 GMT"

        current_time = datetime.now().strftime("%H:%M")

        # Define the format corresponding to the date string
        date_format = "%a, %d %b %Y %H:%M:%S %Z"

        assert response.status_code == 200

        expected_put_response = {
            "data": {
                "assignments_count": 1,
                "new_assignments_count": 1,
                "no_changes_count": 0,
                "re_assignments_count": 0,
            },
            "message": "Success",
        }

        checkdiff = jsondiff.diff(expected_put_response, response.json)
        assert checkdiff == {}

    def test_create_assignment_no_email_schedule(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
        create_email_config,
        create_email_template,
    ):
        """
        Create an assignment between a single target and enumerator without email schedule
        """
        payload = {
            "assignments": [{"target_uid": 1, "enumerator_uid": 1}],
            "form_uid": 1,
            "validate_mapping": True,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        current_time = datetime.now().strftime("%H:%M")

        assert response.status_code == 200

        expected_put_response = {
            "data": {
                "assignments_count": 1,
                "new_assignments_count": 1,
                "no_changes_count": 0,
                "re_assignments_count": 0,
                "email_schedule": [
                    {
                        "email_config_uid": 1,
                        "config_name": "AssignmentsConfig",
                        "dates": None,
                        "time": None,
                        "current_time": current_time,
                        "email_schedule_uid": None,
                        "schedule_date": None,
                    }
                ],
            },
            "message": "Success",
        }
        print(response.json)
        print(expected_put_response)

        checkdiff = jsondiff.diff(expected_put_response, response.json)
        assert checkdiff == {}

    def test_multiple_assignments(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Test creating assignments between multiple targets and enumerators
        """

        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 1},
                {"target_uid": 2, "enumerator_uid": 2},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        expected_response = {
            "data": [
                {
                    "assigned_enumerator_custom_fields": {
                        "Age": "1",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "assigned_enumerator_email": "eric.dodge@idinsight.org",
                    "assigned_enumerator_gender": "Male",
                    "assigned_enumerator_home_address": "my house",
                    "assigned_enumerator_id": "0294612",
                    "assigned_enumerator_language": "English",
                    "assigned_enumerator_mobile_primary": "0123456789",
                    "assigned_enumerator_name": "Eric Dodge",
                    "assigned_enumerator_uid": 1,
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "Hyderabad",
                        "Mobile no.": "1234567890",
                        "Name": "Anil",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {"column_name": "address1", "field_label": "Address"},
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                    ],
                    "location_uid": 4,
                    "num_attempts": 0,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": True,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 1,
                    "webapp_tag_color": None,
                },
                {
                    "assigned_enumerator_custom_fields": {
                        "Age": "2",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "assigned_enumerator_email": "jahnavi.meher@idinsight.org",
                    "assigned_enumerator_gender": "Female",
                    "assigned_enumerator_home_address": "my house",
                    "assigned_enumerator_id": "0294613",
                    "assigned_enumerator_language": "Telugu",
                    "assigned_enumerator_mobile_primary": "0123456789",
                    "assigned_enumerator_name": "Jahnavi Meher",
                    "assigned_enumerator_uid": 2,
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "South Delhi",
                        "Mobile no.": "1234567891",
                        "Name": "Anupama",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {"column_name": "address1", "field_label": "Address"},
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                    ],
                    "location_uid": 4,
                    "num_attempts": 0,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": True,
                    "target_id": "2",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 2,
                    "webapp_tag_color": None,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_remove_assignment(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Test removing an assignment
        """

        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 1},
                {"target_uid": 2, "enumerator_uid": 1},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        payload = {
            "assignments": [
                {"target_uid": 2, "enumerator_uid": None},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        expected_response = {
            "data": [
                {
                    "assigned_enumerator_custom_fields": {
                        "Age": "1",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "assigned_enumerator_email": "eric.dodge@idinsight.org",
                    "assigned_enumerator_gender": "Male",
                    "assigned_enumerator_home_address": "my house",
                    "assigned_enumerator_id": "0294612",
                    "assigned_enumerator_language": "English",
                    "assigned_enumerator_mobile_primary": "0123456789",
                    "assigned_enumerator_name": "Eric Dodge",
                    "assigned_enumerator_uid": 1,
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "Hyderabad",
                        "Mobile no.": "1234567890",
                        "Name": "Anil",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {"column_name": "address1", "field_label": "Address"},
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                    ],
                    "location_uid": 4,
                    "num_attempts": 0,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": True,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 1,
                    "webapp_tag_color": None,
                },
                {
                    "assigned_enumerator_custom_fields": None,
                    "assigned_enumerator_email": None,
                    "assigned_enumerator_gender": None,
                    "assigned_enumerator_home_address": None,
                    "assigned_enumerator_id": None,
                    "assigned_enumerator_language": None,
                    "assigned_enumerator_mobile_primary": None,
                    "assigned_enumerator_name": None,
                    "assigned_enumerator_uid": None,
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "South Delhi",
                        "Mobile no.": "1234567891",
                        "Name": "Anupama",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {"column_name": "address1", "field_label": "Address"},
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                    ],
                    "location_uid": 4,
                    "num_attempts": 0,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": True,
                    "target_id": "2",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 2,
                    "webapp_tag_color": None,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_reassign_assignment(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Test reassigning a target to a different enumerator
        """

        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 1},
                {"target_uid": 2, "enumerator_uid": 1},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        payload = {
            "assignments": [
                {"target_uid": 2, "enumerator_uid": 2},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        expected_response = {
            "data": [
                {
                    "assigned_enumerator_custom_fields": {
                        "Age": "1",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "assigned_enumerator_email": "eric.dodge@idinsight.org",
                    "assigned_enumerator_gender": "Male",
                    "assigned_enumerator_home_address": "my house",
                    "assigned_enumerator_id": "0294612",
                    "assigned_enumerator_language": "English",
                    "assigned_enumerator_mobile_primary": "0123456789",
                    "assigned_enumerator_name": "Eric Dodge",
                    "assigned_enumerator_uid": 1,
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "Hyderabad",
                        "Mobile no.": "1234567890",
                        "Name": "Anil",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {"column_name": "address1", "field_label": "Address"},
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                    ],
                    "location_uid": 4,
                    "num_attempts": 0,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": True,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 1,
                    "webapp_tag_color": None,
                },
                {
                    "assigned_enumerator_custom_fields": {
                        "Age": "2",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "assigned_enumerator_email": "jahnavi.meher@idinsight.org",
                    "assigned_enumerator_gender": "Female",
                    "assigned_enumerator_home_address": "my house",
                    "assigned_enumerator_id": "0294613",
                    "assigned_enumerator_language": "Telugu",
                    "assigned_enumerator_mobile_primary": "0123456789",
                    "assigned_enumerator_name": "Jahnavi Meher",
                    "assigned_enumerator_uid": 2,
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "South Delhi",
                        "Mobile no.": "1234567891",
                        "Name": "Anupama",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {"column_name": "address1", "field_label": "Address"},
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                    ],
                    "location_uid": 4,
                    "num_attempts": 0,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": True,
                    "target_id": "2",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 2,
                    "webapp_tag_color": None,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_dropout_enumerator(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Test removing an assignment on a target when the enumerator is marked as Dropout
        """

        # Making the assignment
        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 1},
                {"target_uid": 2, "enumerator_uid": 1},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        # Update an enumerator's status to Dropout
        payload = {
            "status": "Dropout",
            "form_uid": 1,
            "enumerator_type": "surveyor",
        }

        response = client.patch(
            "/api/enumerators/1/roles/status",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        # Check the response and assert that the target are released
        expected_response = {
            "data": [
                {
                    "assigned_enumerator_custom_fields": None,
                    "assigned_enumerator_email": None,
                    "assigned_enumerator_gender": None,
                    "assigned_enumerator_home_address": None,
                    "assigned_enumerator_id": None,
                    "assigned_enumerator_language": None,
                    "assigned_enumerator_mobile_primary": None,
                    "assigned_enumerator_name": None,
                    "assigned_enumerator_uid": None,
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "Hyderabad",
                        "Mobile no.": "1234567890",
                        "Name": "Anil",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile " "no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {"column_name": "address1", "field_label": "Address"},
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                    ],
                    "location_uid": 4,
                    "num_attempts": 0,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": True,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 1,
                    "webapp_tag_color": None,
                },
                {
                    "assigned_enumerator_custom_fields": None,
                    "assigned_enumerator_email": None,
                    "assigned_enumerator_gender": None,
                    "assigned_enumerator_home_address": None,
                    "assigned_enumerator_id": None,
                    "assigned_enumerator_language": None,
                    "assigned_enumerator_mobile_primary": None,
                    "assigned_enumerator_name": None,
                    "assigned_enumerator_uid": None,
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "South Delhi",
                        "Mobile no.": "1234567891",
                        "Name": "Anupama",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile " "no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {"column_name": "address1", "field_label": "Address"},
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                    ],
                    "location_uid": 4,
                    "num_attempts": 0,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": True,
                    "target_id": "2",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 2,
                    "webapp_tag_color": None,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_dropout_enumerator_ineligible(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Test that a target can't be assigned to an ineligible enumerator
        """

        # Update an enumerator's status to Dropout
        payload = {
            "status": "Dropout",
            "form_uid": 1,
            "enumerator_type": "surveyor",
        }

        response = client.patch(
            "/api/enumerators/1/roles/status",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200
        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 1},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        print(response.json)
        expected_response = {
            "errors": {
                "dropout_enumerator_uids": [1],
                "message": "The following enumerator ID's have status 'Dropout' and are ineligible for assignment: 0294612",
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_unassignable_target(
        self,
        app,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Test that an unassignable target can't be assigned
        This is when `target_assignable` in the target_status table is not equal to `True`
        """

        # Update a target's assignable status to False
        set_target_assignable_status(app, db, 1, False)

        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 1},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422
        print(response.json)

        expected_response = {
            "errors": {
                "message": "The following target ID's are not assignable for this form (most likely because they are complete): 1",
                "unassignable_target_uids": [1],
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_unassignable_target_unassignment(
        self,
        app,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Test that an unassignable target can't be unassigned
        This is when `target_assignable` in the target_status table is not equal to `True`
        """

        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 1},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        # Update a target's assignable status to False
        set_target_assignable_status(app, db, 1, False)

        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": None},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        print(response.json)
        expected_response = {
            "errors": {
                "message": "The following target ID's are not assignable for this form (most likely because they are complete): 1",
                "unassignable_target_uids": [1],
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_unassignable_target_reassignment(
        self,
        app,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Test that an unassignable target can't be reassigned
        This is when `target_assignable` in the target_status table is not equal to `True`
        """

        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 1},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        # Update a target's assignable status to False
        set_target_assignable_status(app, db, 1, False)

        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 2},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        print(response.json)
        expected_response = {
            "errors": {
                "message": "The following target ID's are not assignable for this form (most likely because they are complete): 1",
                "unassignable_target_uids": [1],
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignment_target_not_found(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Test trying to assign a target that doesn't exist
        """

        payload = {
            "assignments": [
                {"target_uid": 10, "enumerator_uid": 1},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 404
        print(response.json)

        expected_response = {
            "errors": {
                "message": "Some of the target ID's provided were not found for this form. Kindly refresh and try again.",
                "not_found_target_uids": [10],
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignment_enumerator_not_found(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Test trying to assign an enumerator that doesn't exist
        """

        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 10},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 404

        print(response.json)
        expected_response = {
            "errors": {
                "message": "Some of the enumerator ID's provided were not found for this form. Kindly refresh and try again.",
                "not_found_enumerator_uids": [10],
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_mismatched_supervisor_mapping_assignment(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        update_target_mapping_criteria,
        csrf_token,
    ):
        """
        Test trying to assign a target to enumerator with different supervisor
        """

        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 4},
            ],
            "form_uid": 1,
            "validate_mapping": True,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 422

        expected_response = {
            "errors": {
                "message": "The following target ID's are assigned to enumerators mapped to a different supervisor: 1. Please ensure that the target and assigned enumerator are mapped to the same supervisor.",
                "incorrect_mapping_target_uids": [1],
            },
            "success": False,
        }
        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_mismatched_supervisor_mapping_assignment_success(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        update_target_mapping_criteria,
        csrf_token,
    ):
        """
        Test trying to assign a target to enumerator with different supervisor is successful when `validate_mapping` is False
        """

        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 4},
            ],
            "form_uid": 1,
            "validate_mapping": False,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        expected_response = {
            "success": True,
            "data": [
                {
                    "target_uid": 1,
                    "target_id": "1",
                    "language": "Telugu",
                    "gender": "Male",
                    "location_uid": 4,
                    "form_uid": 1,
                    "custom_fields": {
                        "Name": "Anil",
                        "Address": "Hyderabad",
                        "Mobile no.": "1234567890",
                        "column_mapping": {
                            "gender": "gender1",
                            "language": "language1",
                            "target_id": "target_id1",
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {"column_name": "address1", "field_label": "Address"},
                            ],
                            "location_id_column": "psu_id1",
                        },
                    },
                    "assigned_enumerator_uid": 4,
                    "assigned_enumerator_id": "0294615",
                    "assigned_enumerator_name": "Griffin Muteti",
                    "assigned_enumerator_home_address": "my house",
                    "assigned_enumerator_language": "Swahili",
                    "assigned_enumerator_gender": "Male",
                    "assigned_enumerator_email": "griffin.muteti@idinsight.org",
                    "assigned_enumerator_mobile_primary": "0123456789",
                    "assigned_enumerator_custom_fields": {
                        "Age": "4",
                        "column_mapping": {
                            "name": "name1",
                            "email": "email1",
                            "gender": "gender1",
                            "language": "language1",
                            "home_address": "home_address1",
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "enumerator_id": "enumerator_id1",
                            "mobile_primary": "mobile_primary1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                        },
                        "Mobile (Secondary)": "1123456789",
                    },
                    "completed_flag": None,
                    "refusal_flag": None,
                    "num_attempts": 0,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "target_assignable": True,
                    "webapp_tag_color": None,
                    "revisit_sections": None,
                    "scto_fields": None,
                    "target_locations": [
                        {
                            "location_id": "1",
                            "location_uid": 1,
                            "geo_level_uid": 1,
                            "location_name": "ADILABAD",
                            "geo_level_name": "District",
                        },
                        {
                            "location_id": "1101",
                            "location_uid": 2,
                            "geo_level_uid": 2,
                            "location_name": "ADILABAD RURAL",
                            "geo_level_name": "Mandal",
                        },
                        {
                            "location_id": "17101102",
                            "location_uid": 4,
                            "geo_level_uid": 3,
                            "location_name": "ANKOLI",
                            "geo_level_name": "PSU",
                        },
                    ],
                    "supervisors": [
                        {
                            "role_uid": 3,
                            "role_name": "Regional Coordinator",
                            "supervisor_name": "John Doe",
                            "supervisor_email": "newuser3@example.com",
                        },
                        {
                            "role_uid": 2,
                            "role_name": "Cluster Coordinator",
                            "supervisor_name": "Ron Doe",
                            "supervisor_email": "newuser2@example.com",
                        },
                        {
                            "role_uid": 1,
                            "role_name": "Core User",
                            "supervisor_name": "Tim Doe",
                            "supervisor_email": "newuser1@example.com",
                        },
                    ],
                },
                {
                    "target_uid": 2,
                    "target_id": "2",
                    "language": "Hindi",
                    "gender": "Female",
                    "location_uid": 4,
                    "form_uid": 1,
                    "custom_fields": {
                        "Name": "Anupama",
                        "Address": "South Delhi",
                        "Mobile no.": "1234567891",
                        "column_mapping": {
                            "gender": "gender1",
                            "language": "language1",
                            "target_id": "target_id1",
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {"column_name": "address1", "field_label": "Address"},
                            ],
                            "location_id_column": "psu_id1",
                        },
                    },
                    "assigned_enumerator_uid": None,
                    "assigned_enumerator_id": None,
                    "assigned_enumerator_name": None,
                    "assigned_enumerator_home_address": None,
                    "assigned_enumerator_language": None,
                    "assigned_enumerator_gender": None,
                    "assigned_enumerator_email": None,
                    "assigned_enumerator_mobile_primary": None,
                    "assigned_enumerator_custom_fields": None,
                    "completed_flag": None,
                    "refusal_flag": None,
                    "num_attempts": 0,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "target_assignable": True,
                    "webapp_tag_color": None,
                    "revisit_sections": None,
                    "scto_fields": None,
                    "target_locations": [
                        {
                            "location_id": "1",
                            "location_uid": 1,
                            "geo_level_uid": 1,
                            "location_name": "ADILABAD",
                            "geo_level_name": "District",
                        },
                        {
                            "location_id": "1101",
                            "location_uid": 2,
                            "geo_level_uid": 2,
                            "location_name": "ADILABAD RURAL",
                            "geo_level_name": "Mandal",
                        },
                        {
                            "location_id": "17101102",
                            "location_uid": 4,
                            "geo_level_uid": 3,
                            "location_name": "ANKOLI",
                            "geo_level_name": "PSU",
                        },
                    ],
                    "supervisors": [
                        {
                            "role_uid": 3,
                            "role_name": "Regional Coordinator",
                            "supervisor_name": "John Doe",
                            "supervisor_email": "newuser3@example.com",
                        },
                        {
                            "role_uid": 2,
                            "role_name": "Cluster Coordinator",
                            "supervisor_name": "Ron Doe",
                            "supervisor_email": "newuser2@example.com",
                        },
                        {
                            "role_uid": 1,
                            "role_name": "Core User",
                            "supervisor_name": "Tim Doe",
                            "supervisor_email": "newuser1@example.com",
                        },
                    ],
                },
            ],
        }
        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_eligible_enumerators(
        self,
        app,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Test the assignable enumerators endpoint
        We will also check that the productivity stats are correct
        """

        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 1},
                {"target_uid": 2, "enumerator_uid": 2},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        set_target_assignable_status(app, db, 1, True)
        set_target_assignable_status(app, db, 2, False)

        # Check the response

        expected_response = {
            "data": [
                {
                    "custom_fields": {
                        "Age": "1",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "email": "eric.dodge@idinsight.org",
                    "enumerator_id": "0294612",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "geo_level_uid": 1,
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "enumerator_uid": 1,
                    "form_productivity": {
                        "test_scto_input_output": {
                            "form_name": "Agrifieldnet Main Form",
                            "scto_form_id": "test_scto_input_output",
                            "total_assigned_targets": 1,
                            "total_completed_targets": 0,
                            "total_pending_targets": 1,
                            "avg_num_completed_per_day": 0,
                            "avg_num_submissions_per_day": 0,
                        }
                    },
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "English",
                    "mobile_primary": "0123456789",
                    "name": "Eric Dodge",
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                    ],
                    "surveyor_status": "Active",
                },
                {
                    "custom_fields": {
                        "Age": "2",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "email": "jahnavi.meher@idinsight.org",
                    "enumerator_id": "0294613",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "geo_level_uid": 1,
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "enumerator_uid": 2,
                    "form_productivity": {
                        "test_scto_input_output": {
                            "form_name": "Agrifieldnet Main Form",
                            "scto_form_id": "test_scto_input_output",
                            "total_assigned_targets": 1,
                            "total_completed_targets": 1,
                            "total_pending_targets": 0,
                            "avg_num_completed_per_day": 0,
                            "avg_num_submissions_per_day": 0,
                        }
                    },
                    "gender": "Female",
                    "home_address": "my house",
                    "language": "Telugu",
                    "mobile_primary": "0123456789",
                    "name": "Jahnavi Meher",
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                    ],
                    "surveyor_status": "Active",
                },
                {
                    "custom_fields": {
                        "Age": "4",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "email": "griffin.muteti@idinsight.org",
                    "enumerator_id": "0294615",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "geo_level_uid": 1,
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "enumerator_uid": 4,
                    "form_productivity": {
                        "test_scto_input_output": {
                            "form_name": "Agrifieldnet Main Form",
                            "scto_form_id": "test_scto_input_output",
                            "total_assigned_targets": 0,
                            "total_completed_targets": 0,
                            "total_pending_targets": 0,
                            "avg_num_completed_per_day": 0,
                            "avg_num_submissions_per_day": 0,
                        }
                    },
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Swahili",
                    "mobile_primary": "0123456789",
                    "name": "Griffin Muteti",
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                    ],
                    "surveyor_status": "Active",
                },
            ],
            "success": True,
        }

        response = client.get(
            "/api/assignments/enumerators", query_string={"form_uid": 1}
        )

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_table_config_default(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        create_enumerator_column_config,
        create_target_column_config,
        csrf_token,
    ):
        """
        Test the default response from the table config endpoint
        """

        response = client.get(
            "/api/assignments/table-config", query_string={"form_uid": 1}
        )

        assert response.status_code == 200

        expected_response = {
            "assignments_main": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target ID"},
                        {"column_key": "gender", "column_label": "Gender"},
                        {"column_key": "language", "column_label": "Language"},
                    ],
                    "group_label": "Target Details",
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Name']", "column_label": "Name"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Address']",
                            "column_label": "Address",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "District Name",
                        },
                        {
                            "column_key": "target_locations[1].location_id",
                            "column_label": "Mandal ID",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "Mandal Name",
                        },
                        {
                            "column_key": "target_locations[2].location_id",
                            "column_label": "PSU ID",
                        },
                        {
                            "column_key": "target_locations[2].location_name",
                            "column_label": "PSU Name",
                        },
                    ],
                    "group_label": "Target Location Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Final Survey Status",
                        },
                        {
                            "column_key": "revisit_sections",
                            "column_label": "Revisit Sections",
                        },
                        {
                            "column_key": "num_attempts",
                            "column_label": "Total Attempts",
                        },
                    ],
                    "group_label": "Target Status Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[2].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[2].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Core User",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[1].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[1].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Cluster Coordinator",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[0].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
            "assignments_review": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "prev_assigned_to",
                            "column_label": "Previously Assigned To",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target Unique ID"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Target Status",
                        }
                    ],
                    "group_label": None,
                },
            ],
            "assignments_surveyors": [
                {
                    "columns": [
                        {
                            "column_key": "name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "surveyor_status", "column_label": "Status"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "District Name",
                        },
                    ],
                    "group_label": "Surveyor Working Location",
                },
                {
                    "columns": [
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_assigned_targets",
                            "column_label": "Total Assigned Targets",
                        },
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_pending_targets",
                            "column_label": "Total Pending Targets",
                        },
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_completed_targets",
                            "column_label": "Total Completed Targets",
                        },
                    ],
                    "group_label": "Form Productivity (Agrifieldnet Main Form)",
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "home_address", "column_label": "Address"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile (Secondary)']",
                            "column_label": "Mobile (Secondary)",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Age']", "column_label": "Age"}
                    ],
                    "group_label": None,
                },
            ],
            "surveyors": [
                {
                    "columns": [{"column_key": "name", "column_label": "Name"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "enumerator_id", "column_label": "ID"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "surveyor_status", "column_label": "Status"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "District Name",
                        },
                    ],
                    "group_label": "Surveyor Working Location",
                },
                {
                    "columns": [{"column_key": "email", "column_label": "Email"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "mobile_primary", "column_label": "Mobile"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "home_address", "column_label": "Address"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile (Secondary)']",
                            "column_label": "Mobile (Secondary)",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Age']", "column_label": "Age"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[2].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[2].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Core User",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[1].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[1].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Cluster Coordinator",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[0].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
            "targets": [
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target ID"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Name']", "column_label": "Name"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Address']",
                            "column_label": "Address",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "District Name",
                        },
                        {
                            "column_key": "target_locations[1].location_id",
                            "column_label": "Mandal ID",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "Mandal Name",
                        },
                        {
                            "column_key": "target_locations[2].location_id",
                            "column_label": "PSU ID",
                        },
                        {
                            "column_key": "target_locations[2].location_name",
                            "column_label": "PSU Name",
                        },
                    ],
                    "group_label": "Target Location Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Final Survey Status",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "revisit_sections",
                            "column_label": "Revisit Sections",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "num_attempts", "column_label": "Total Attempts"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[2].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[2].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Core User",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[1].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[1].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Cluster Coordinator",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[0].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
        }

        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_table_config_default_fsl_1_login(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy_with_fsl_1_login,
        create_enumerator_column_config,
        create_target_column_config,
        test_user_credentials,
        csrf_token,
    ):
        """
        Test the default response from the table config endpoint for an FS L1 user
        with no `all_supervisors` flag set to True
        """
        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[1],  # FS L1 role
        )

        login_user(client, test_user_credentials)

        response = client.get(
            "/api/assignments/table-config", query_string={"form_uid": 1}
        )

        assert response.status_code == 200

        expected_response = {
            "assignments_main": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target ID"},
                        {"column_key": "gender", "column_label": "Gender"},
                        {"column_key": "language", "column_label": "Language"},
                    ],
                    "group_label": "Target Details",
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Name']", "column_label": "Name"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Address']",
                            "column_label": "Address",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "District Name",
                        },
                        {
                            "column_key": "target_locations[1].location_id",
                            "column_label": "Mandal ID",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "Mandal Name",
                        },
                        {
                            "column_key": "target_locations[2].location_id",
                            "column_label": "PSU ID",
                        },
                        {
                            "column_key": "target_locations[2].location_name",
                            "column_label": "PSU Name",
                        },
                    ],
                    "group_label": "Target Location Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Final Survey Status",
                        },
                        {
                            "column_key": "revisit_sections",
                            "column_label": "Revisit Sections",
                        },
                        {
                            "column_key": "num_attempts",
                            "column_label": "Total Attempts",
                        },
                    ],
                    "group_label": "Target Status Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[2].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[2].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Core User",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[1].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[1].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Cluster Coordinator",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[0].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
            "assignments_review": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "prev_assigned_to",
                            "column_label": "Previously Assigned To",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target Unique ID"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Target Status",
                        }
                    ],
                    "group_label": None,
                },
            ],
            "assignments_surveyors": [
                {
                    "columns": [
                        {
                            "column_key": "name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "surveyor_status", "column_label": "Status"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "District Name",
                        },
                    ],
                    "group_label": "Surveyor Working Location",
                },
                {
                    "columns": [
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_assigned_targets",
                            "column_label": "Total Assigned Targets",
                        },
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_pending_targets",
                            "column_label": "Total Pending Targets",
                        },
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_completed_targets",
                            "column_label": "Total Completed Targets",
                        },
                    ],
                    "group_label": "Form Productivity (Agrifieldnet Main Form)",
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "home_address", "column_label": "Address"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile (Secondary)']",
                            "column_label": "Mobile (Secondary)",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Age']", "column_label": "Age"}
                    ],
                    "group_label": None,
                },
            ],
            "surveyors": [
                {
                    "columns": [{"column_key": "name", "column_label": "Name"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "enumerator_id", "column_label": "ID"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "surveyor_status", "column_label": "Status"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "District Name",
                        },
                    ],
                    "group_label": "Surveyor Working Location",
                },
                {
                    "columns": [{"column_key": "email", "column_label": "Email"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "mobile_primary", "column_label": "Mobile"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "home_address", "column_label": "Address"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile (Secondary)']",
                            "column_label": "Mobile (Secondary)",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Age']", "column_label": "Age"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[2].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[2].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Core User",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[1].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[1].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Cluster Coordinator",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[0].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
            "targets": [
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target ID"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Name']", "column_label": "Name"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Address']",
                            "column_label": "Address",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "District Name",
                        },
                        {
                            "column_key": "target_locations[1].location_id",
                            "column_label": "Mandal ID",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "Mandal Name",
                        },
                        {
                            "column_key": "target_locations[2].location_id",
                            "column_label": "PSU ID",
                        },
                        {
                            "column_key": "target_locations[2].location_name",
                            "column_label": "PSU Name",
                        },
                    ],
                    "group_label": "Target Location Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Final Survey Status",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "revisit_sections",
                            "column_label": "Revisit Sections",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "num_attempts", "column_label": "Total Attempts"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[2].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[2].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Core User",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[1].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[1].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Cluster Coordinator",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[0].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
        }

        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_table_config_default_fsl_1_login_filtered_supervisors(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy_with_fsl_1_login,
        create_enumerator_column_config,
        create_target_column_config,
        test_user_credentials,
        csrf_token,
    ):
        """
        Test the default response from the table config endpoint for an FS L1 user
        with `filter_supervisors` flag
        """
        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[1],  # FS L1 role
        )

        login_user(client, test_user_credentials)

        response = client.get(
            "/api/assignments/table-config",
            query_string={"form_uid": 1, "filter_supervisors": "true"},
        )

        assert response.status_code == 200

        expected_response = {
            "assignments_main": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target ID"},
                        {"column_key": "gender", "column_label": "Gender"},
                        {"column_key": "language", "column_label": "Language"},
                    ],
                    "group_label": "Target Details",
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Name']", "column_label": "Name"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Address']",
                            "column_label": "Address",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "District Name",
                        },
                        {
                            "column_key": "target_locations[1].location_id",
                            "column_label": "Mandal ID",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "Mandal Name",
                        },
                        {
                            "column_key": "target_locations[2].location_id",
                            "column_label": "PSU ID",
                        },
                        {
                            "column_key": "target_locations[2].location_name",
                            "column_label": "PSU Name",
                        },
                    ],
                    "group_label": "Target Location Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Final Survey Status",
                        },
                        {
                            "column_key": "revisit_sections",
                            "column_label": "Revisit Sections",
                        },
                        {
                            "column_key": "num_attempts",
                            "column_label": "Total Attempts",
                        },
                    ],
                    "group_label": "Target Status Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[1].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[1].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Cluster Coordinator",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[0].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
            "assignments_review": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "prev_assigned_to",
                            "column_label": "Previously Assigned To",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target Unique ID"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Target Status",
                        }
                    ],
                    "group_label": None,
                },
            ],
            "assignments_surveyors": [
                {
                    "columns": [
                        {
                            "column_key": "name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "surveyor_status", "column_label": "Status"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "District Name",
                        },
                    ],
                    "group_label": "Surveyor Working Location",
                },
                {
                    "columns": [
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_assigned_targets",
                            "column_label": "Total Assigned Targets",
                        },
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_pending_targets",
                            "column_label": "Total Pending Targets",
                        },
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_completed_targets",
                            "column_label": "Total Completed Targets",
                        },
                    ],
                    "group_label": "Form Productivity (Agrifieldnet Main Form)",
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "home_address", "column_label": "Address"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile (Secondary)']",
                            "column_label": "Mobile (Secondary)",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Age']", "column_label": "Age"}
                    ],
                    "group_label": None,
                },
            ],
            "surveyors": [
                {
                    "columns": [{"column_key": "name", "column_label": "Name"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "enumerator_id", "column_label": "ID"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "surveyor_status", "column_label": "Status"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "District Name",
                        },
                    ],
                    "group_label": "Surveyor Working Location",
                },
                {
                    "columns": [{"column_key": "email", "column_label": "Email"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "mobile_primary", "column_label": "Mobile"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "home_address", "column_label": "Address"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile (Secondary)']",
                            "column_label": "Mobile (Secondary)",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Age']", "column_label": "Age"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[1].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[1].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Cluster Coordinator",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[0].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
            "targets": [
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target ID"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Name']", "column_label": "Name"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Address']",
                            "column_label": "Address",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "District Name",
                        },
                        {
                            "column_key": "target_locations[1].location_id",
                            "column_label": "Mandal ID",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "Mandal Name",
                        },
                        {
                            "column_key": "target_locations[2].location_id",
                            "column_label": "PSU ID",
                        },
                        {
                            "column_key": "target_locations[2].location_name",
                            "column_label": "PSU Name",
                        },
                    ],
                    "group_label": "Target Location Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Final Survey Status",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "revisit_sections",
                            "column_label": "Revisit Sections",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "num_attempts", "column_label": "Total Attempts"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[1].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[1].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Cluster Coordinator",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[0].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
        }

        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_table_config_default_fsl_2_login_filtered_supervisors(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy_with_fsl_2_login,
        create_enumerator_column_config,
        create_target_column_config,
        test_user_credentials,
        csrf_token,
    ):
        """
        Test the default response from the table config endpoint for an FS L2 user
        with no `filter_supervisors` flag
        """
        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[2],  # FS L2 role
        )

        login_user(client, test_user_credentials)

        response = client.get(
            "/api/assignments/table-config",
            query_string={"form_uid": 1, "filter_supervisors": "true"},
        )

        assert response.status_code == 200

        expected_response = {
            "assignments_main": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target ID"},
                        {"column_key": "gender", "column_label": "Gender"},
                        {"column_key": "language", "column_label": "Language"},
                    ],
                    "group_label": "Target Details",
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Name']", "column_label": "Name"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Address']",
                            "column_label": "Address",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "District Name",
                        },
                        {
                            "column_key": "target_locations[1].location_id",
                            "column_label": "Mandal ID",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "Mandal Name",
                        },
                        {
                            "column_key": "target_locations[2].location_id",
                            "column_label": "PSU ID",
                        },
                        {
                            "column_key": "target_locations[2].location_name",
                            "column_label": "PSU Name",
                        },
                    ],
                    "group_label": "Target Location Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Final Survey Status",
                        },
                        {
                            "column_key": "revisit_sections",
                            "column_label": "Revisit Sections",
                        },
                        {
                            "column_key": "num_attempts",
                            "column_label": "Total Attempts",
                        },
                    ],
                    "group_label": "Target Status Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[0].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
            "assignments_review": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "prev_assigned_to",
                            "column_label": "Previously Assigned To",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target Unique ID"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Target Status",
                        }
                    ],
                    "group_label": None,
                },
            ],
            "assignments_surveyors": [
                {
                    "columns": [
                        {
                            "column_key": "name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "surveyor_status", "column_label": "Status"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "District Name",
                        },
                    ],
                    "group_label": "Surveyor Working Location",
                },
                {
                    "columns": [
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_assigned_targets",
                            "column_label": "Total Assigned Targets",
                        },
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_pending_targets",
                            "column_label": "Total Pending Targets",
                        },
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_completed_targets",
                            "column_label": "Total Completed Targets",
                        },
                    ],
                    "group_label": "Form Productivity (Agrifieldnet Main Form)",
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "home_address", "column_label": "Address"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile (Secondary)']",
                            "column_label": "Mobile (Secondary)",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Age']", "column_label": "Age"}
                    ],
                    "group_label": None,
                },
            ],
            "surveyors": [
                {
                    "columns": [{"column_key": "name", "column_label": "Name"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "enumerator_id", "column_label": "ID"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "surveyor_status", "column_label": "Status"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "District Name",
                        },
                    ],
                    "group_label": "Surveyor Working Location",
                },
                {
                    "columns": [{"column_key": "email", "column_label": "Email"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "mobile_primary", "column_label": "Mobile"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "home_address", "column_label": "Address"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile (Secondary)']",
                            "column_label": "Mobile (Secondary)",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Age']", "column_label": "Age"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[0].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
            "targets": [
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target ID"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Name']", "column_label": "Name"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Address']",
                            "column_label": "Address",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "District Name",
                        },
                        {
                            "column_key": "target_locations[1].location_id",
                            "column_label": "Mandal ID",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "Mandal Name",
                        },
                        {
                            "column_key": "target_locations[2].location_id",
                            "column_label": "PSU ID",
                        },
                        {
                            "column_key": "target_locations[2].location_name",
                            "column_label": "PSU Name",
                        },
                    ],
                    "group_label": "Target Location Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Final Survey Status",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "revisit_sections",
                            "column_label": "Revisit Sections",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "num_attempts", "column_label": "Total Attempts"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[0].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
        }

        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_table_config_default_fsl_3_login_filtered_supervisors(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy_with_fsl_3_login,
        create_enumerator_column_config,
        create_target_column_config,
        test_user_credentials,
        csrf_token,
    ):
        """
        Test the default response from the table config endpoint for an FS L3 user
        with no `filter_supervisors` flag
        """
        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[3],  # FS L3 role
            location_uids=[1],
        )

        login_user(client, test_user_credentials)

        response = client.get(
            "/api/assignments/table-config",
            query_string={"form_uid": 1, "filter_supervisors": "true"},
        )

        assert response.status_code == 200

        expected_response = {
            "assignments_main": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target ID"},
                        {"column_key": "gender", "column_label": "Gender"},
                        {"column_key": "language", "column_label": "Language"},
                    ],
                    "group_label": "Target Details",
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Name']", "column_label": "Name"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Address']",
                            "column_label": "Address",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "District Name",
                        },
                        {
                            "column_key": "target_locations[1].location_id",
                            "column_label": "Mandal ID",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "Mandal Name",
                        },
                        {
                            "column_key": "target_locations[2].location_id",
                            "column_label": "PSU ID",
                        },
                        {
                            "column_key": "target_locations[2].location_name",
                            "column_label": "PSU Name",
                        },
                    ],
                    "group_label": "Target Location Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Final Survey Status",
                        },
                        {
                            "column_key": "revisit_sections",
                            "column_label": "Revisit Sections",
                        },
                        {
                            "column_key": "num_attempts",
                            "column_label": "Total Attempts",
                        },
                    ],
                    "group_label": "Target Status Details",
                },
            ],
            "assignments_review": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "prev_assigned_to",
                            "column_label": "Previously Assigned To",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target Unique ID"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Target Status",
                        }
                    ],
                    "group_label": None,
                },
            ],
            "assignments_surveyors": [
                {
                    "columns": [
                        {
                            "column_key": "name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "surveyor_status", "column_label": "Status"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "District Name",
                        },
                    ],
                    "group_label": "Surveyor Working Location",
                },
                {
                    "columns": [
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_assigned_targets",
                            "column_label": "Total Assigned Targets",
                        },
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_pending_targets",
                            "column_label": "Total Pending Targets",
                        },
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_completed_targets",
                            "column_label": "Total Completed Targets",
                        },
                    ],
                    "group_label": "Form Productivity (Agrifieldnet Main Form)",
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "home_address", "column_label": "Address"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile (Secondary)']",
                            "column_label": "Mobile (Secondary)",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Age']", "column_label": "Age"}
                    ],
                    "group_label": None,
                },
            ],
            "surveyors": [
                {
                    "columns": [{"column_key": "name", "column_label": "Name"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "enumerator_id", "column_label": "ID"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "surveyor_status", "column_label": "Status"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "District Name",
                        },
                    ],
                    "group_label": "Surveyor Working Location",
                },
                {
                    "columns": [{"column_key": "email", "column_label": "Email"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "mobile_primary", "column_label": "Mobile"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "home_address", "column_label": "Address"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile (Secondary)']",
                            "column_label": "Mobile (Secondary)",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Age']", "column_label": "Age"}
                    ],
                    "group_label": None,
                },
            ],
            "targets": [
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target ID"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Name']", "column_label": "Name"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Address']",
                            "column_label": "Address",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "District Name",
                        },
                        {
                            "column_key": "target_locations[1].location_id",
                            "column_label": "Mandal ID",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "Mandal Name",
                        },
                        {
                            "column_key": "target_locations[2].location_id",
                            "column_label": "PSU ID",
                        },
                        {
                            "column_key": "target_locations[2].location_name",
                            "column_label": "PSU Name",
                        },
                    ],
                    "group_label": "Target Location Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Final Survey Status",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "revisit_sections",
                            "column_label": "Revisit Sections",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "num_attempts", "column_label": "Total Attempts"}
                    ],
                    "group_label": None,
                },
            ],
        }

        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_table_config_default_no_locations(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        create_enumerator_column_config_no_locations,
        create_target_column_config_no_locations,
        csrf_token,
    ):
        """
        Test the default response from the table config endpoint when no locations are in the enumerator and target column configs
        """

        response = client.get(
            "/api/assignments/table-config", query_string={"form_uid": 1}
        )

        assert response.status_code == 200

        expected_response = {
            "assignments_main": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target ID"},
                        {"column_key": "gender", "column_label": "Gender"},
                        {"column_key": "language", "column_label": "Language"},
                    ],
                    "group_label": "Target Details",
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Name']", "column_label": "Name"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Address']",
                            "column_label": "Address",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Final Survey Status",
                        },
                        {
                            "column_key": "revisit_sections",
                            "column_label": "Revisit Sections",
                        },
                        {
                            "column_key": "num_attempts",
                            "column_label": "Total Attempts",
                        },
                    ],
                    "group_label": "Target Status Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[2].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[2].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Core User",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[1].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[1].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Cluster Coordinator",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[0].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
            "assignments_review": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "prev_assigned_to",
                            "column_label": "Previously Assigned To",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target Unique ID"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Target Status",
                        }
                    ],
                    "group_label": None,
                },
            ],
            "assignments_surveyors": [
                {
                    "columns": [
                        {
                            "column_key": "name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "surveyor_status", "column_label": "Status"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_assigned_targets",
                            "column_label": "Total Assigned Targets",
                        },
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_pending_targets",
                            "column_label": "Total Pending Targets",
                        },
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_completed_targets",
                            "column_label": "Total Completed Targets",
                        },
                    ],
                    "group_label": "Form Productivity (Agrifieldnet Main Form)",
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "home_address", "column_label": "Address"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile (Secondary)']",
                            "column_label": "Mobile (Secondary)",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Age']", "column_label": "Age"}
                    ],
                    "group_label": None,
                },
            ],
            "surveyors": [
                {
                    "columns": [{"column_key": "name", "column_label": "Name"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "enumerator_id", "column_label": "ID"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "surveyor_status", "column_label": "Status"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "email", "column_label": "Email"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "mobile_primary", "column_label": "Mobile"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "home_address", "column_label": "Address"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile (Secondary)']",
                            "column_label": "Mobile (Secondary)",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Age']", "column_label": "Age"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[2].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[2].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Core User",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[1].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[1].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Cluster Coordinator",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[0].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
            "targets": [
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target ID"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Name']", "column_label": "Name"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Address']",
                            "column_label": "Address",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Final Survey Status",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "revisit_sections",
                            "column_label": "Revisit Sections",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "num_attempts", "column_label": "Total Attempts"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[2].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[2].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Core User",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[1].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[1].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Cluster Coordinator",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[0].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
        }

        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_table_config_default_no_custom_fields(
        self,
        client,
        login_test_user,
        upload_enumerators_csv_no_custom_fields,
        upload_targets_csv_no_custom_fields,
        add_user_hierarchy,
        create_enumerator_column_config_no_custom_fields,
        create_target_column_config_no_custom_fields,
        csrf_token,
    ):
        """
        Test the default response from the table config endpoint when no custom fields are present
        """

        response = client.get(
            "/api/assignments/table-config", query_string={"form_uid": 1}
        )

        assert response.status_code == 200

        expected_response = {
            "assignments_main": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target ID"},
                        {"column_key": "gender", "column_label": "Gender"},
                        {"column_key": "language", "column_label": "Language"},
                    ],
                    "group_label": "Target Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "District Name",
                        },
                        {
                            "column_key": "target_locations[1].location_id",
                            "column_label": "Mandal ID",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "Mandal Name",
                        },
                        {
                            "column_key": "target_locations[2].location_id",
                            "column_label": "PSU ID",
                        },
                        {
                            "column_key": "target_locations[2].location_name",
                            "column_label": "PSU Name",
                        },
                    ],
                    "group_label": "Target Location Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Final Survey Status",
                        },
                        {
                            "column_key": "revisit_sections",
                            "column_label": "Revisit Sections",
                        },
                        {
                            "column_key": "num_attempts",
                            "column_label": "Total Attempts",
                        },
                    ],
                    "group_label": "Target Status Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[2].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[2].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Core User",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[1].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[1].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Cluster Coordinator",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[0].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
            "assignments_review": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "prev_assigned_to",
                            "column_label": "Previously Assigned To",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target Unique ID"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Target Status",
                        }
                    ],
                    "group_label": None,
                },
            ],
            "assignments_surveyors": [
                {
                    "columns": [
                        {
                            "column_key": "name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "surveyor_status", "column_label": "Status"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "District Name",
                        },
                    ],
                    "group_label": "Surveyor Working Location",
                },
                {
                    "columns": [
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_assigned_targets",
                            "column_label": "Total Assigned Targets",
                        },
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_pending_targets",
                            "column_label": "Total Pending Targets",
                        },
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_completed_targets",
                            "column_label": "Total Completed Targets",
                        },
                    ],
                    "group_label": "Form Productivity (Agrifieldnet Main Form)",
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "home_address", "column_label": "Address"}
                    ],
                    "group_label": None,
                },
            ],
            "surveyors": [
                {
                    "columns": [{"column_key": "name", "column_label": "Name"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "enumerator_id", "column_label": "ID"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "surveyor_status", "column_label": "Status"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "District Name",
                        },
                    ],
                    "group_label": "Surveyor Working Location",
                },
                {
                    "columns": [{"column_key": "email", "column_label": "Email"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "mobile_primary", "column_label": "Mobile"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "home_address", "column_label": "Address"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[2].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[2].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Core User",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[1].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[1].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Cluster Coordinator",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[0].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
            "targets": [
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target ID"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "District Name",
                        },
                        {
                            "column_key": "target_locations[1].location_id",
                            "column_label": "Mandal ID",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "Mandal Name",
                        },
                        {
                            "column_key": "target_locations[2].location_id",
                            "column_label": "PSU ID",
                        },
                        {
                            "column_key": "target_locations[2].location_name",
                            "column_label": "PSU Name",
                        },
                    ],
                    "group_label": "Target Location Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Final Survey Status",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "revisit_sections",
                            "column_label": "Revisit Sections",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "num_attempts", "column_label": "Total Attempts"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[2].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[2].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Core User",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[1].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[1].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Cluster Coordinator",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        },
                        {
                            "column_key": "supervisors[0].supervisor_email",
                            "column_label": "Email",
                        },
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
        }

        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_table_config_default_no_roles(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        create_enumerator_column_config,
        create_target_column_config,
        csrf_token,
    ):
        """
        Test the default response from the table config endpoint with no roles
        """

        response = client.get(
            "/api/assignments/table-config", query_string={"form_uid": 1}
        )

        print(response.json)
        assert response.status_code == 200

        expected_response = {
            "assignments_main": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target ID"},
                        {"column_key": "gender", "column_label": "Gender"},
                        {"column_key": "language", "column_label": "Language"},
                    ],
                    "group_label": "Target Details",
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Name']", "column_label": "Name"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Address']",
                            "column_label": "Address",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "District Name",
                        },
                        {
                            "column_key": "target_locations[1].location_id",
                            "column_label": "Mandal ID",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "Mandal Name",
                        },
                        {
                            "column_key": "target_locations[2].location_id",
                            "column_label": "PSU ID",
                        },
                        {
                            "column_key": "target_locations[2].location_name",
                            "column_label": "PSU Name",
                        },
                    ],
                    "group_label": "Target Location Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Final Survey Status",
                        },
                        {
                            "column_key": "revisit_sections",
                            "column_label": "Revisit Sections",
                        },
                        {
                            "column_key": "num_attempts",
                            "column_label": "Total Attempts",
                        },
                    ],
                    "group_label": "Target Status Details",
                },
            ],
            "assignments_review": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "prev_assigned_to",
                            "column_label": "Previously Assigned To",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target Unique ID"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Target Status",
                        }
                    ],
                    "group_label": None,
                },
            ],
            "assignments_surveyors": [
                {
                    "columns": [
                        {
                            "column_key": "name",
                            "column_label": "Surveyor Name",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "surveyor_status", "column_label": "Status"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "District Name",
                        },
                    ],
                    "group_label": "Surveyor Working Location",
                },
                {
                    "columns": [
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_assigned_targets",
                            "column_label": "Total Assigned Targets",
                        },
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_pending_targets",
                            "column_label": "Total Pending Targets",
                        },
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_completed_targets",
                            "column_label": "Total Completed Targets",
                        },
                    ],
                    "group_label": "Form Productivity (Agrifieldnet Main Form)",
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "home_address", "column_label": "Address"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile (Secondary)']",
                            "column_label": "Mobile (Secondary)",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Age']", "column_label": "Age"}
                    ],
                    "group_label": None,
                },
            ],
            "surveyors": [
                {
                    "columns": [{"column_key": "name", "column_label": "Name"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "enumerator_id", "column_label": "ID"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "surveyor_status", "column_label": "Status"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "District Name",
                        },
                    ],
                    "group_label": "Surveyor Working Location",
                },
                {
                    "columns": [{"column_key": "email", "column_label": "Email"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "mobile_primary", "column_label": "Mobile"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "home_address", "column_label": "Address"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile (Secondary)']",
                            "column_label": "Mobile (Secondary)",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Age']", "column_label": "Age"}
                    ],
                    "group_label": None,
                },
            ],
            "targets": [
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target ID"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "gender", "column_label": "Gender"}],
                    "group_label": None,
                },
                {
                    "columns": [{"column_key": "language", "column_label": "Language"}],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "custom_fields['Name']", "column_label": "Name"}
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Address']",
                            "column_label": "Address",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "District Name",
                        },
                        {
                            "column_key": "target_locations[1].location_id",
                            "column_label": "Mandal ID",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "Mandal Name",
                        },
                        {
                            "column_key": "target_locations[2].location_id",
                            "column_label": "PSU ID",
                        },
                        {
                            "column_key": "target_locations[2].location_name",
                            "column_label": "PSU Name",
                        },
                    ],
                    "group_label": "Target Location Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Final Survey Status",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "revisit_sections",
                            "column_label": "Revisit Sections",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {"column_key": "num_attempts", "column_label": "Total Attempts"}
                    ],
                    "group_label": None,
                },
            ],
        }

        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_create_table_config(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        create_enumerator_column_config,
        create_target_column_config,
        csrf_token,
    ):
        """
        Test creating a new table config for each table type
        """

        payload = {
            "form_uid": 1,
            "table_name": "assignments_main",
            "table_config": [
                {
                    "group_label": "Details",
                    "column_key": "assigned_enumerator_id",
                    "column_label": "Enumerator id",
                },
                {
                    "group_label": "Details",
                    "column_key": "assigned_enumerator_name",
                    "column_label": "Enumerator name",
                },
                {
                    "group_label": None,
                    "column_key": "custom_fields['Mobile no.']",
                    "column_label": "Target Mobile no.",
                },
                {
                    "group_label": None,
                    "column_key": "assigned_enumerator_custom_fields['Age']",
                    "column_label": "Enumerator Age",
                },
                {
                    "group_label": "Locations",
                    "column_key": "target_locations[0].location_name",
                    "column_label": "State",
                },
                {
                    "group_label": "Locations",
                    "column_key": "target_locations[1].location_name",
                    "column_label": "District",
                },
                {
                    "group_label": "Core User",
                    "column_key": "supervisors[2].supervisor_name",
                    "column_label": "Name",
                },
                {
                    "group_label": "Cluster Coordinator",
                    "column_key": "supervisors[1].supervisor_name",
                    "column_label": "Name",
                },
                {
                    "group_label": "Regional Coordinator",
                    "column_key": "supervisors[0].supervisor_name",
                    "column_label": "Name",
                },
            ],
        }

        response = client.put(
            "/api/assignments/table-config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        payload = {
            "form_uid": 1,
            "table_name": "assignments_surveyors",
            "table_config": [
                {
                    "group_label": "Details",
                    "column_key": "enumerator_id",
                    "column_label": "Enumerator id",
                },
                {
                    "group_label": "Details",
                    "column_key": "name",
                    "column_label": "Enumerator name",
                },
                {
                    "group_label": None,
                    "column_key": "custom_fields['Age']",
                    "column_label": "Enumerator Age",
                },
                {
                    "group_label": "Locations",
                    "column_key": "surveyor_locations[0].location_name",
                    "column_label": "State",
                },
                {
                    "group_label": "Form productivity",
                    "column_key": "form_productivity.test_scto_input_output.total_assigned_targets",
                    "column_label": "Total Assigned",
                },
            ],
        }

        response = client.put(
            "/api/assignments/table-config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)

        assert response.status_code == 200

        payload = {
            "form_uid": 1,
            "table_name": "assignments_review",
            "table_config": [
                {
                    "group_label": "Details",
                    "column_key": "assigned_enumerator_name",
                    "column_label": "Enumerator name",
                },
                {
                    "group_label": "Details",
                    "column_key": "target_id",
                    "column_label": "Target ID",
                },
            ],
        }

        response = client.put(
            "/api/assignments/table-config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        payload = {
            "form_uid": 1,
            "table_name": "surveyors",
            "table_config": [
                {
                    "group_label": "Details",
                    "column_key": "enumerator_id",
                    "column_label": "Enumerator id",
                },
                {
                    "group_label": "Details",
                    "column_key": "name",
                    "column_label": "Enumerator name",
                },
                {
                    "group_label": None,
                    "column_key": "custom_fields['Age']",
                    "column_label": "Enumerator Age",
                },
                {
                    "group_label": "Locations",
                    "column_key": "surveyor_locations[0].location_name",
                    "column_label": "State",
                },
            ],
        }

        response = client.put(
            "/api/assignments/table-config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        payload = {
            "form_uid": 1,
            "table_name": "targets",
            "table_config": [
                {
                    "group_label": "Details",
                    "column_key": "target_id",
                    "column_label": "Target id",
                },
                {
                    "group_label": None,
                    "column_key": "custom_fields['Mobile no.']",
                    "column_label": "Target Mobile no.",
                },
                {
                    "group_label": "Locations",
                    "column_key": "target_locations[0].location_name",
                    "column_label": "State",
                },
                {
                    "group_label": "Locations",
                    "column_key": "target_locations[1].location_name",
                    "column_label": "District",
                },
            ],
        }

        response = client.put(
            "/api/assignments/table-config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        response = client.get(
            "/api/assignments/table-config",
            query_string={"form_uid": 1, "table_name": "assignments_main"},
        )

        assert response.status_code == 200

        expected_response = {
            "assignments_main": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_id",
                            "column_label": "Enumerator id",
                        },
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Enumerator name",
                        },
                    ],
                    "group_label": "Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Target Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_custom_fields['Age']",
                            "column_label": "Enumerator Age",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "State",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "District",
                        },
                    ],
                    "group_label": "Locations",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[2].supervisor_name",
                            "column_label": "Name",
                        }
                    ],
                    "group_label": "Core User",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[1].supervisor_name",
                            "column_label": "Name",
                        }
                    ],
                    "group_label": "Cluster Coordinator",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        }
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
            "assignments_review": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Enumerator name",
                        },
                        {"column_key": "target_id", "column_label": "Target ID"},
                    ],
                    "group_label": "Details",
                }
            ],
            "assignments_surveyors": [
                {
                    "columns": [
                        {
                            "column_key": "enumerator_id",
                            "column_label": "Enumerator id",
                        },
                        {"column_key": "name", "column_label": "Enumerator name"},
                    ],
                    "group_label": "Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Age']",
                            "column_label": "Enumerator Age",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "State",
                        }
                    ],
                    "group_label": "Locations",
                },
                {
                    "columns": [
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_assigned_targets",
                            "column_label": "Total Assigned",
                        }
                    ],
                    "group_label": "Form productivity",
                },
            ],
            "surveyors": [
                {
                    "columns": [
                        {
                            "column_key": "enumerator_id",
                            "column_label": "Enumerator id",
                        },
                        {"column_key": "name", "column_label": "Enumerator name"},
                    ],
                    "group_label": "Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Age']",
                            "column_label": "Enumerator Age",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "State",
                        }
                    ],
                    "group_label": "Locations",
                },
            ],
            "targets": [
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target id"}
                    ],
                    "group_label": "Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Target Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "State",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "District",
                        },
                    ],
                    "group_label": "Locations",
                },
            ],
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        print(response.json)

        assert checkdiff == {}

    def test_create_table_config_fsl1_login(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy_with_fsl_1_login,
        create_enumerator_column_config,
        create_target_column_config,
        test_user_credentials,
        csrf_token,
    ):
        """
        Test creating a new table config for each table type with FS L1 login
        """
        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[1],  # FS L1 role
        )

        login_user(client, test_user_credentials)

        payload = {
            "form_uid": 1,
            "table_name": "assignments_main",
            "table_config": [
                {
                    "group_label": "Details",
                    "column_key": "assigned_enumerator_id",
                    "column_label": "Enumerator id",
                },
                {
                    "group_label": "Details",
                    "column_key": "assigned_enumerator_name",
                    "column_label": "Enumerator name",
                },
                {
                    "group_label": None,
                    "column_key": "custom_fields['Mobile no.']",
                    "column_label": "Target Mobile no.",
                },
                {
                    "group_label": None,
                    "column_key": "assigned_enumerator_custom_fields['Age']",
                    "column_label": "Enumerator Age",
                },
                {
                    "group_label": "Locations",
                    "column_key": "target_locations[0].location_name",
                    "column_label": "State",
                },
                {
                    "group_label": "Locations",
                    "column_key": "target_locations[1].location_name",
                    "column_label": "District",
                },
                {
                    "group_label": "Core User",
                    "column_key": "supervisors[2].supervisor_name",
                    "column_label": "Name",
                },
                {
                    "group_label": "Cluster Coordinator",
                    "column_key": "supervisors[1].supervisor_name",
                    "column_label": "Name",
                },
                {
                    "group_label": "Regional Coordinator",
                    "column_key": "supervisors[0].supervisor_name",
                    "column_label": "Name",
                },
            ],
        }

        response = client.put(
            "/api/assignments/table-config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        payload = {
            "form_uid": 1,
            "table_name": "assignments_surveyors",
            "table_config": [
                {
                    "group_label": "Details",
                    "column_key": "enumerator_id",
                    "column_label": "Enumerator id",
                },
                {
                    "group_label": "Details",
                    "column_key": "name",
                    "column_label": "Enumerator name",
                },
                {
                    "group_label": None,
                    "column_key": "custom_fields['Age']",
                    "column_label": "Enumerator Age",
                },
                {
                    "group_label": "Locations",
                    "column_key": "surveyor_locations[0].location_name",
                    "column_label": "State",
                },
                {
                    "group_label": "Form productivity",
                    "column_key": "form_productivity.test_scto_input_output.total_assigned_targets",
                    "column_label": "Total Assigned",
                },
            ],
        }

        response = client.put(
            "/api/assignments/table-config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)

        assert response.status_code == 200

        payload = {
            "form_uid": 1,
            "table_name": "assignments_review",
            "table_config": [
                {
                    "group_label": "Details",
                    "column_key": "assigned_enumerator_name",
                    "column_label": "Enumerator name",
                },
                {
                    "group_label": "Details",
                    "column_key": "target_id",
                    "column_label": "Target ID",
                },
            ],
        }

        response = client.put(
            "/api/assignments/table-config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        payload = {
            "form_uid": 1,
            "table_name": "surveyors",
            "table_config": [
                {
                    "group_label": "Details",
                    "column_key": "enumerator_id",
                    "column_label": "Enumerator id",
                },
                {
                    "group_label": "Details",
                    "column_key": "name",
                    "column_label": "Enumerator name",
                },
                {
                    "group_label": None,
                    "column_key": "custom_fields['Age']",
                    "column_label": "Enumerator Age",
                },
                {
                    "group_label": "Locations",
                    "column_key": "surveyor_locations[0].location_name",
                    "column_label": "State",
                },
            ],
        }

        response = client.put(
            "/api/assignments/table-config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        payload = {
            "form_uid": 1,
            "table_name": "targets",
            "table_config": [
                {
                    "group_label": "Details",
                    "column_key": "target_id",
                    "column_label": "Target id",
                },
                {
                    "group_label": None,
                    "column_key": "custom_fields['Mobile no.']",
                    "column_label": "Target Mobile no.",
                },
                {
                    "group_label": "Locations",
                    "column_key": "target_locations[0].location_name",
                    "column_label": "State",
                },
                {
                    "group_label": "Locations",
                    "column_key": "target_locations[1].location_name",
                    "column_label": "District",
                },
            ],
        }

        response = client.put(
            "/api/assignments/table-config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        # Fetch with no filter_supervisors flag
        response = client.get(
            "/api/assignments/table-config",
            query_string={"form_uid": 1},
        )

        assert response.status_code == 200

        expected_response = {
            "assignments_main": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_id",
                            "column_label": "Enumerator id",
                        },
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Enumerator name",
                        },
                    ],
                    "group_label": "Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Target Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_custom_fields['Age']",
                            "column_label": "Enumerator Age",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "State",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "District",
                        },
                    ],
                    "group_label": "Locations",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[2].supervisor_name",
                            "column_label": "Name",
                        }
                    ],
                    "group_label": "Core User",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[1].supervisor_name",
                            "column_label": "Name",
                        }
                    ],
                    "group_label": "Cluster Coordinator",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        }
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
            "assignments_review": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Enumerator name",
                        },
                        {"column_key": "target_id", "column_label": "Target ID"},
                    ],
                    "group_label": "Details",
                }
            ],
            "assignments_surveyors": [
                {
                    "columns": [
                        {
                            "column_key": "enumerator_id",
                            "column_label": "Enumerator id",
                        },
                        {"column_key": "name", "column_label": "Enumerator name"},
                    ],
                    "group_label": "Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Age']",
                            "column_label": "Enumerator Age",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "State",
                        }
                    ],
                    "group_label": "Locations",
                },
                {
                    "columns": [
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_assigned_targets",
                            "column_label": "Total Assigned",
                        }
                    ],
                    "group_label": "Form productivity",
                },
            ],
            "surveyors": [
                {
                    "columns": [
                        {
                            "column_key": "enumerator_id",
                            "column_label": "Enumerator id",
                        },
                        {"column_key": "name", "column_label": "Enumerator name"},
                    ],
                    "group_label": "Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Age']",
                            "column_label": "Enumerator Age",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "State",
                        }
                    ],
                    "group_label": "Locations",
                },
            ],
            "targets": [
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target id"}
                    ],
                    "group_label": "Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Target Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "State",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "District",
                        },
                    ],
                    "group_label": "Locations",
                },
            ],
        }
        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

        # Fetch with filter_supervisors flag
        response = client.get(
            "/api/assignments/table-config",
            query_string={"form_uid": 1, "filter_supervisors": True},
        )

        assert response.status_code == 200

        expected_response = {
            "assignments_main": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_id",
                            "column_label": "Enumerator id",
                        },
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Enumerator name",
                        },
                    ],
                    "group_label": "Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Target Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_custom_fields['Age']",
                            "column_label": "Enumerator Age",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "State",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "District",
                        },
                    ],
                    "group_label": "Locations",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[1].supervisor_name",
                            "column_label": "Name",
                        }
                    ],
                    "group_label": "Cluster Coordinator",
                },
                {
                    "columns": [
                        {
                            "column_key": "supervisors[0].supervisor_name",
                            "column_label": "Name",
                        }
                    ],
                    "group_label": "Regional Coordinator",
                },
            ],
            "assignments_review": [
                {
                    "columns": [
                        {
                            "column_key": "assigned_enumerator_name",
                            "column_label": "Enumerator name",
                        },
                        {"column_key": "target_id", "column_label": "Target ID"},
                    ],
                    "group_label": "Details",
                }
            ],
            "assignments_surveyors": [
                {
                    "columns": [
                        {
                            "column_key": "enumerator_id",
                            "column_label": "Enumerator id",
                        },
                        {"column_key": "name", "column_label": "Enumerator name"},
                    ],
                    "group_label": "Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Age']",
                            "column_label": "Enumerator Age",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "State",
                        }
                    ],
                    "group_label": "Locations",
                },
                {
                    "columns": [
                        {
                            "column_key": "form_productivity.test_scto_input_output.total_assigned_targets",
                            "column_label": "Total Assigned",
                        }
                    ],
                    "group_label": "Form productivity",
                },
            ],
            "surveyors": [
                {
                    "columns": [
                        {
                            "column_key": "enumerator_id",
                            "column_label": "Enumerator id",
                        },
                        {"column_key": "name", "column_label": "Enumerator name"},
                    ],
                    "group_label": "Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Age']",
                            "column_label": "Enumerator Age",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "State",
                        }
                    ],
                    "group_label": "Locations",
                },
            ],
            "targets": [
                {
                    "columns": [
                        {"column_key": "target_id", "column_label": "Target id"}
                    ],
                    "group_label": "Details",
                },
                {
                    "columns": [
                        {
                            "column_key": "custom_fields['Mobile no.']",
                            "column_label": "Target Mobile no.",
                        }
                    ],
                    "group_label": None,
                },
                {
                    "columns": [
                        {
                            "column_key": "target_locations[0].location_name",
                            "column_label": "State",
                        },
                        {
                            "column_key": "target_locations[1].location_name",
                            "column_label": "District",
                        },
                    ],
                    "group_label": "Locations",
                },
            ],
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_table_config_default_no_geo_levels_error(
        self,
        client,
        login_test_user,
        create_form,
        create_enumerator_column_config,
        create_target_column_config,
        csrf_token,
    ):
        """
        Test that an error is raised when the column configs contain locations but the survey has no geo levels
        """

        response = client.get(
            "/api/assignments/table-config", query_string={"form_uid": 1}
        )

        assert response.status_code == 422

        expected_response = {
            "errors": {
                "geo_level_hierarchy": [
                    "Cannot create the location type hierarchy because no location types have been defined for the survey."
                ]
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_table_config_default_no_prime_geo_level_error(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        create_enumerator_column_config,
        create_target_column_config,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that an error is raised when the column configs contain locations but the survey has no prime geo level defined
        """

        # Update the survey
        payload = payload = {
            "survey_uid": 1,
            "survey_id": "test_survey",
            "survey_name": "Test Survey",
            "survey_description": "A test survey",
            "project_name": "Test Project",
            "surveying_method": "in-person",
            "irb_approval": "Yes",
            "planned_start_date": "2021-01-01",
            "planned_end_date": "2021-12-31",
            "state": "Draft",
            "prime_geo_level_uid": None,
            "config_status": "In Progress - Configuration",
            "created_by_user_uid": test_user_credentials["user_uid"],
        }

        response = client.put(
            "/api/surveys/1/basic-information",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        response = client.get(
            "/api/assignments/table-config", query_string={"form_uid": 1}
        )

        assert response.status_code == 422

        expected_response = {
            "errors": "The prime_geo_level_uid is not configured for this survey but is found as a column in the enumerator_column_config table.",
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_table_config_default_prime_geo_level_not_in_geo_levels_error(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        create_enumerator_column_config,
        create_target_column_config,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that an error is raised when the column configs contain locations but the prime geo level is not in the geo levels
        """

        # Update the survey
        payload = payload = {
            "survey_uid": 1,
            "survey_id": "test_survey",
            "survey_name": "Test Survey",
            "survey_description": "A test survey",
            "project_name": "Test Project",
            "surveying_method": "in-person",
            "irb_approval": "Yes",
            "planned_start_date": "2021-01-01",
            "planned_end_date": "2021-12-31",
            "state": "Draft",
            "prime_geo_level_uid": 20,
            "config_status": "In Progress - Configuration",
            "created_by_user_uid": test_user_credentials["user_uid"],
        }

        response = client.put(
            "/api/surveys/1/basic-information",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        response = client.get(
            "/api/assignments/table-config", query_string={"form_uid": 1}
        )

        assert response.status_code == 422

        expected_response = {
            "errors": "The prime_geo_level_uid '20' is not in the location type hierarchy for this survey.",
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_table_config_validations_no_locations_configured(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        create_enumerator_column_config_no_locations,
        create_target_column_config_no_locations,
        csrf_token,
    ):
        """
        Test creating invalid table configs to trigger each type of validation error
        This test is for when no locations are configured in the target/enumerator column configs but the table config contains locations
        """

        payload = {
            "form_uid": 1,
            "table_name": "assignments_surveyors",
            "table_config": [
                {
                    "group_label": "Locations",
                    "column_key": "surveyor_locations[0].location_name",
                    "column_label": "State",
                }
            ],
        }

        response = client.put(
            "/api/assignments/table-config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        expected_response = {
            "errors": [
                "The column_key 'surveyor_locations[0].location_name' is invalid. Location is not defined in the enumerator_column_config table for this form.",
            ],
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)

        print(response.json)
        assert checkdiff == {}

        payload = {
            "form_uid": 1,
            "table_name": "assignments_main",
            "table_config": [
                {
                    "group_label": "Locations",
                    "column_key": "target_locations[0].location_name",
                    "column_label": "State",
                }
            ],
        }

        response = client.put(
            "/api/assignments/table-config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        expected_response = {
            "errors": [
                "The column_key 'target_locations[0].location_name' is invalid. Location is not defined in the target_column_config table for this form."
            ],
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_table_config_validations_no_roles_configured(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        create_enumerator_column_config_no_locations,
        create_target_column_config_no_locations,
        csrf_token,
    ):
        """
        Test creating invalid table configs to trigger each type of validation error
        This test is for when no roles are configured but the table config contains supervisor roles
        """

        payload = {
            "form_uid": 1,
            "table_name": "assignments_main",
            "table_config": [
                {
                    "group_label": "Core User",
                    "column_key": "supervisors[2].supervisor_name",
                    "column_label": "Name",
                }
            ],
        }

        response = client.put(
            "/api/assignments/table-config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        expected_response = {
            "errors": [
                "The column_key 'supervisors[2].supervisor_name' is invalid. Roles are not defined for this survey."
            ],
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)

        print(response.json)
        assert checkdiff == {}

    def test_table_config_validations(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        create_enumerator_column_config,
        create_target_column_config,
        csrf_token,
    ):
        """
        Test creating invalid table configs to trigger each type of validation error

        Add a not allowed key
        Use surveyor_locations key in assignments_main where it is not allowed
        Try different incorrect formats for target_locations
        Check for out of range index in target_locations
        Check for out of range index in surveyor_locations
        Try different incorrect formats for custom_fields and assigned_enumerator_custom_fields
        Try non-existent keys for custom_fields and assigned_enumerator_custom_fields
        Check for non-existent keys in assignments_surveyors custom fields
        Try different incorrect formats for form productivity
        Check for non-existent scto_form_id in form productivity
        Check for non-existing supervisor index in assignments_main
        """

        payload = {
            "form_uid": 1,
            "table_name": "assignments_main",
            "table_config": [
                {
                    "group_label": "Details",
                    "column_key": "assigned_enumerator_id_asdf",
                    "column_label": "Enumerator id",
                },
                {
                    "group_label": "Details",
                    "column_key": "assigned_enumerator_name",
                    "column_label": "Enumerator name",
                },
                {
                    "group_label": None,
                    "column_key": "custom_fields['Mobile no.']",
                    "column_label": "Target Mobile no.",
                },
                {
                    "group_label": None,
                    "column_key": "assigned_enumerator_custom_fields['Age']",
                    "column_label": "Enumerator Age",
                },
                {
                    "group_label": "Locations",
                    "column_key": "target_locations[0].location_name",
                    "column_label": "State",
                },
                {
                    "group_label": "Locations",
                    "column_key": "target_locations_asdf[0].location_name",
                    "column_label": "State",
                },
                {
                    "group_label": "Locations",
                    "column_key": "target_locations[-1].location_name",
                    "column_label": "State",
                },
                {
                    "group_label": "Locations",
                    "column_key": "target_locations[].location_name",
                    "column_label": "State",
                },
                {
                    "group_label": "Locations",
                    "column_key": "target_locations[asf].location_name",
                    "column_label": "State",
                },
                {
                    "group_label": "Locations",
                    "column_key": "target_locations[0].location_name_asdf",
                    "column_label": "State",
                },
                {
                    "group_label": "Locations",
                    "column_key": "target_locations[0]",
                    "column_label": "State",
                },
                {
                    "group_label": "Locations",
                    "column_key": "target_locations[10].location_name",
                    "column_label": "State",
                },
                {
                    "group_label": "Locations",
                    "column_key": "surveyor_locations[0].location_name",
                    "column_label": "District",
                },
                {
                    "group_label": None,
                    "column_key": "custom_fields_asdf['Hotel']",
                    "column_label": "Hotel",
                },
                {
                    "group_label": None,
                    "column_key": "custom_fields[Hotel]",
                    "column_label": "Hotel",
                },
                {
                    "group_label": None,
                    "column_key": "custom_fields['Hotel']asdf",
                    "column_label": "Hotel",
                },
                {
                    "group_label": None,
                    "column_key": "assigned_enumerator_custom_fields_asdf['Hotel']asdf",
                    "column_label": "Hotel",
                },
                {
                    "group_label": None,
                    "column_key": "custom_fields['Hotel']",
                    "column_label": "Hotel",
                },
                {
                    "group_label": None,
                    "column_key": "assigned_enumerator_custom_fields['Hotel']",
                    "column_label": "Hotel",
                },
                {
                    "group_label": None,
                    "column_key": "scto_fields.my-horse",
                    "column_label": "Horse",
                },
                {
                    "group_label": None,
                    "column_key": "scto_fields.horse",
                    "column_label": "Horse",
                },
                {
                    "group_label": "Core User",
                    "column_key": "supervisors[3].supervisor_name",
                    "column_label": "Name",
                },
            ],
        }

        response = client.put(
            "/api/assignments/table-config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        expected_response = {
            "errors": [
                "'assigned_enumerator_id_asdf' is not an allowed key for the assignments_main table configuration",
                "'target_locations_asdf[0].location_name' is not in the correct format. It should follow the pattern target_locations[<index:int>].location_id or target_locations[<index>].location_name>",
                "'target_locations[-1].location_name' is not in the correct format. It should follow the pattern target_locations[<index:int>].location_id or target_locations[<index>].location_name>",
                "'target_locations[].location_name' is not in the correct format. It should follow the pattern target_locations[<index:int>].location_id or target_locations[<index>].location_name>",
                "'target_locations[asf].location_name' is not in the correct format. It should follow the pattern target_locations[<index:int>].location_id or target_locations[<index>].location_name>",
                "'target_locations[0].location_name_asdf' is not in the correct format. It should follow the pattern target_locations[<index:int>].location_id or target_locations[<index>].location_name>",
                "'target_locations[0]' is not in the correct format. It should follow the pattern target_locations[<index:int>].location_id or target_locations[<index>].location_name>",
                "The location index of 10 for target_locations[10].location_name is invalid. It must be in the range [0:2] because there are 3 geo levels defined for the survey.",
                "custom_fields_asdf['Hotel'] is not in the correct format. It should follow the pattern custom_fields['<custom_field_name>']",
                "custom_fields[Hotel] is not in the correct format. It should follow the pattern custom_fields['<custom_field_name>']",
                "custom_fields['Hotel']asdf is not in the correct format. It should follow the pattern custom_fields['<custom_field_name>']",
                "assigned_enumerator_custom_fields_asdf['Hotel']asdf is not in the correct format. It should follow the pattern assigned_enumerator_custom_fields['<custom_field_name>']",
                "The custom field 'Hotel' is not defined in the target_column_config table for this form.",
                "The enumerator custom field 'Hotel' is not defined in the enumerator_column_config table for this form.",
                "'scto_fields.my-horse' is not in the correct format. It should follow the pattern scto_fields.<surveycto_field_name> (allowed characters are a-z, A-Z, 0-9, _).",
                "The SurveyCTO field 'my-horse' was not found in the form definition for this form.",
                "The SurveyCTO field 'horse' was not found in the form definition for this form.",
                "The supervisor index of 3 for supervisors[3].supervisor_name is invalid. It must be in the range [0:2] because there are 3 supervisors defined for the survey.",
            ],
            "success": False,
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        print(response.json)
        assert checkdiff == {}

        payload = {
            "form_uid": 1,
            "table_name": "assignments_surveyors",
            "table_config": [
                {
                    "group_label": "Locations",
                    "column_key": "surveyor_locations[10].location_name",
                    "column_label": "State",
                },
                {
                    "group_label": None,
                    "column_key": "custom_fields['Hotel']",
                    "column_label": "Hotel",
                },
                {
                    "group_label": "Form productivity",
                    "column_key": "form_productivity.test_scto_input_output.total_assigned",
                    "column_label": "Total Assigned",
                },
                {
                    "group_label": "Form productivity",
                    "column_key": "form_productivity.total_assigned_targets",
                    "column_label": "Total Assigned",
                },
                {
                    "group_label": "Form productivity",
                    "column_key": "form_productivity.fake_scto_form.total_assigned_targets",
                    "column_label": "Total Assigned",
                },
            ],
        }

        response = client.put(
            "/api/assignments/table-config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        expected_response = {
            "errors": [
                "The location index of 10 for surveyor_locations[10].location_name is invalid. It must be in the range [0:0] because 0 is the index of the prime geo level defined for the survey.",
                "The custom field 'Hotel' is not defined in the enumerator_column_config table for this form.",
                "form_productivity.test_scto_input_output.total_assigned is not in the correct format. It should follow the pattern form_productivity.<surveycto_form_id>.<total_assigned_target|total_completed_targets|total_pending_targets>",
                "form_productivity.total_assigned_targets is not in the correct format. It should follow the pattern form_productivity.<surveycto_form_id>.<total_assigned_target|total_completed_targets|total_pending_targets>",
                "The surveycto_form_id 'fake_scto_form' is not found in the forms defined for this survey.",
            ],
            "success": False,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_upload_assignments_merge_csv(
        self,
        client,
        login_test_user,
        create_assignments,
        csrf_token,
        user_permissions_with_upload,
        request,
        create_email_config,
        create_email_schedule,
        create_email_template,
    ):
        """
        Function to test uploading asssignments csv with merge mode

        """

        user_fixture, expected_permission = user_permissions_with_upload
        request.getfixturevalue(user_fixture)

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_assignments_merge.csv"
        )

        # Read the targets.csv file and convert it to base64
        with open(filepath, "rb") as f:
            assignments_csv = f.read()
            assignments_csv_encoded = base64.b64encode(assignments_csv).decode("utf-8")

        # Try to upload the targets csv
        payload = {
            "column_mapping": {
                "target_id": "target_id1",
                "enumerator_id": "enumerator_id1",
            },
            "file": assignments_csv_encoded,
            "mode": "merge",
            "validate_mapping": True,
        }

        response = client.post(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        current_datetime = datetime.now()
        formatted_date = current_datetime.strftime("%a, %d %b %Y") + " 00:00:00 GMT"
        current_time = datetime.now().strftime("%H:%M")

        # Define the format corresponding to the date string
        date_format = "%a, %d %b %Y %H:%M:%S %Z"

        if expected_permission:
            if user_fixture != "user_with_assignment_upload_permissions":
                assert response.status_code == 200
                assert datetime.strptime(
                    response.json["data"]["email_schedule"][0]["schedule_date"],
                    date_format,
                ) >= datetime.strptime(formatted_date, date_format)
                expected_put_response = {
                    "data": {
                        "assignments_count": 1,
                        "new_assignments_count": 0,
                        "no_changes_count": 0,
                        "re_assignments_count": 1,
                        "email_schedule": [
                            {
                                "config_name": "AssignmentsConfig",
                                "dates": response.json["data"]["email_schedule"][0][
                                    "dates"
                                ],
                                "schedule_date": response.json["data"][
                                    "email_schedule"
                                ][0]["schedule_date"],
                                "current_time": current_time,
                                "email_schedule_uid": response.json["data"][
                                    "email_schedule"
                                ][0]["email_schedule_uid"],
                                "email_config_uid": 1,
                                "time": response.json["data"]["email_schedule"][0][
                                    "time"
                                ],
                            }
                        ],
                    },
                    "message": "Success",
                }
                checkdiff = jsondiff.diff(expected_put_response, response.json)
                assert checkdiff == {}

                expected_response = {
                    "data": [
                        {
                            "assigned_enumerator_custom_fields": {
                                "Age": "4",
                                "Mobile (Secondary)": "1123456789",
                                "column_mapping": {
                                    "custom_fields": [
                                        {
                                            "column_name": "mobile_secondary1",
                                            "field_label": "Mobile (Secondary)",
                                        },
                                        {"column_name": "age1", "field_label": "Age"},
                                    ],
                                    "email": "email1",
                                    "enumerator_id": "enumerator_id1",
                                    "enumerator_type": "enumerator_type1",
                                    "gender": "gender1",
                                    "home_address": "home_address1",
                                    "language": "language1",
                                    "location_id_column": "district_id1",
                                    "mobile_primary": "mobile_primary1",
                                    "name": "name1",
                                },
                            },
                            "assigned_enumerator_email": "griffin.muteti@idinsight.org",
                            "assigned_enumerator_gender": "Male",
                            "assigned_enumerator_home_address": "my house",
                            "assigned_enumerator_id": "0294615",
                            "assigned_enumerator_language": "Swahili",
                            "assigned_enumerator_mobile_primary": "0123456789",
                            "assigned_enumerator_name": "Griffin Muteti",
                            "assigned_enumerator_uid": 4,
                            "completed_flag": None,
                            "custom_fields": {
                                "Address": "Hyderabad",
                                "Mobile no.": "1234567890",
                                "Name": "Anil",
                                "column_mapping": {
                                    "custom_fields": [
                                        {
                                            "column_name": "mobile_primary1",
                                            "field_label": "Mobile no.",
                                        },
                                        {"column_name": "name1", "field_label": "Name"},
                                        {
                                            "column_name": "address1",
                                            "field_label": "Address",
                                        },
                                    ],
                                    "gender": "gender1",
                                    "language": "language1",
                                    "location_id_column": "psu_id1",
                                    "target_id": "target_id1",
                                },
                            },
                            "form_uid": 1,
                            "gender": "Male",
                            "language": "Telugu",
                            "last_attempt_survey_status": None,
                            "last_attempt_survey_status_label": "Not Attempted",
                            "final_survey_status": None,
                            "final_survey_status_label": "Not Attempted",
                            "scto_fields": None,
                            "supervisors": [
                                {
                                    "role_name": "Regional Coordinator",
                                    "role_uid": 3,
                                    "supervisor_email": "newuser3@example.com",
                                    "supervisor_name": "John Doe",
                                },
                                {
                                    "role_name": "Cluster Coordinator",
                                    "role_uid": 2,
                                    "supervisor_email": "newuser2@example.com",
                                    "supervisor_name": "Ron Doe",
                                },
                                {
                                    "role_name": "Core User",
                                    "role_uid": 1,
                                    "supervisor_email": "newuser1@example.com",
                                    "supervisor_name": "Tim Doe",
                                },
                            ],
                            "location_uid": 4,
                            "num_attempts": 0,
                            "refusal_flag": None,
                            "revisit_sections": None,
                            "target_assignable": True,
                            "target_id": "1",
                            "target_locations": [
                                {
                                    "geo_level_name": "District",
                                    "geo_level_uid": 1,
                                    "location_id": "1",
                                    "location_name": "ADILABAD",
                                    "location_uid": 1,
                                },
                                {
                                    "geo_level_name": "Mandal",
                                    "geo_level_uid": 2,
                                    "location_id": "1101",
                                    "location_name": "ADILABAD RURAL",
                                    "location_uid": 2,
                                },
                                {
                                    "geo_level_name": "PSU",
                                    "geo_level_uid": 3,
                                    "location_id": "17101102",
                                    "location_name": "ANKOLI",
                                    "location_uid": 4,
                                },
                            ],
                            "target_uid": 1,
                            "webapp_tag_color": None,
                        },
                        {
                            "assigned_enumerator_custom_fields": {
                                "Age": "2",
                                "Mobile (Secondary)": "1123456789",
                                "column_mapping": {
                                    "custom_fields": [
                                        {
                                            "column_name": "mobile_secondary1",
                                            "field_label": "Mobile (Secondary)",
                                        },
                                        {"column_name": "age1", "field_label": "Age"},
                                    ],
                                    "email": "email1",
                                    "enumerator_id": "enumerator_id1",
                                    "enumerator_type": "enumerator_type1",
                                    "gender": "gender1",
                                    "home_address": "home_address1",
                                    "language": "language1",
                                    "location_id_column": "district_id1",
                                    "mobile_primary": "mobile_primary1",
                                    "name": "name1",
                                },
                            },
                            "assigned_enumerator_email": "jahnavi.meher@idinsight.org",
                            "assigned_enumerator_gender": "Female",
                            "assigned_enumerator_home_address": "my house",
                            "assigned_enumerator_id": "0294613",
                            "assigned_enumerator_language": "Telugu",
                            "assigned_enumerator_mobile_primary": "0123456789",
                            "assigned_enumerator_name": "Jahnavi Meher",
                            "assigned_enumerator_uid": 2,
                            "completed_flag": None,
                            "custom_fields": {
                                "Address": "South Delhi",
                                "Mobile no.": "1234567891",
                                "Name": "Anupama",
                                "column_mapping": {
                                    "custom_fields": [
                                        {
                                            "column_name": "mobile_primary1",
                                            "field_label": "Mobile no.",
                                        },
                                        {"column_name": "name1", "field_label": "Name"},
                                        {
                                            "column_name": "address1",
                                            "field_label": "Address",
                                        },
                                    ],
                                    "gender": "gender1",
                                    "language": "language1",
                                    "location_id_column": "psu_id1",
                                    "target_id": "target_id1",
                                },
                            },
                            "form_uid": 1,
                            "gender": "Female",
                            "language": "Hindi",
                            "last_attempt_survey_status": None,
                            "last_attempt_survey_status_label": "Not Attempted",
                            "final_survey_status": None,
                            "final_survey_status_label": "Not Attempted",
                            "scto_fields": None,
                            "supervisors": [
                                {
                                    "role_name": "Regional Coordinator",
                                    "role_uid": 3,
                                    "supervisor_email": "newuser3@example.com",
                                    "supervisor_name": "John Doe",
                                },
                                {
                                    "role_name": "Cluster Coordinator",
                                    "role_uid": 2,
                                    "supervisor_email": "newuser2@example.com",
                                    "supervisor_name": "Ron Doe",
                                },
                                {
                                    "role_name": "Core User",
                                    "role_uid": 1,
                                    "supervisor_email": "newuser1@example.com",
                                    "supervisor_name": "Tim Doe",
                                },
                            ],
                            "location_uid": 4,
                            "num_attempts": 0,
                            "refusal_flag": None,
                            "revisit_sections": None,
                            "target_assignable": True,
                            "target_id": "2",
                            "target_locations": [
                                {
                                    "geo_level_name": "District",
                                    "geo_level_uid": 1,
                                    "location_id": "1",
                                    "location_name": "ADILABAD",
                                    "location_uid": 1,
                                },
                                {
                                    "geo_level_name": "Mandal",
                                    "geo_level_uid": 2,
                                    "location_id": "1101",
                                    "location_name": "ADILABAD RURAL",
                                    "location_uid": 2,
                                },
                                {
                                    "geo_level_name": "PSU",
                                    "geo_level_uid": 3,
                                    "location_id": "17101102",
                                    "location_name": "ANKOLI",
                                    "location_uid": 4,
                                },
                            ],
                            "target_uid": 2,
                            "webapp_tag_color": None,
                        },
                    ],
                    "success": True,
                }

                # Check the response
                response = client.get("/api/assignments", query_string={"form_uid": 1})

                checkdiff = jsondiff.diff(expected_response, response.json)
                assert checkdiff == {}
            else:
                assert response.status_code == 422

                expected_response = {
                    "success": False,
                    "errors": {
                        "record_errors": {
                            "summary": {
                                "total_rows": 1,
                                "total_correct_rows": 0,
                                "total_rows_with_errors": 1,
                                "error_count": 2,
                            },
                            "summary_by_error_type": [
                                {
                                    "error_type": "Not mapped target_id's",
                                    "error_message": "The file contains 1 target_id(s) that are not mapped to current logged in user and hence cannot be assigned by this user. The following row numbers contain such target_id's: 2",
                                    "error_count": 1,
                                    "row_numbers_with_errors": [2],
                                    "can_be_ignored": False,
                                },
                                {
                                    "error_type": "Incorrectly mapped target and enumerator id's",
                                    "error_message": "The file contains 1 target_id(s) that are assigned to enumerators mapped to a different supervisor or the target/enumerator/both are not mapped. The following row numbers contain such target_id's: 2",
                                    "error_count": 1,
                                    "row_numbers_with_errors": [2],
                                    "can_be_ignored": True,
                                },
                            ],
                            "invalid_records": {
                                "ordered_columns": [
                                    "row_number",
                                    "target_id1",
                                    "enumerator_id1",
                                    "errors",
                                ],
                                "records": [
                                    {
                                        "target_id1": "1",
                                        "enumerator_id1": "0294615",
                                        "errors": "Target is not mapped to current logged in user and hence cannot be assigned; Target is assigned to an enumerator mapped to a different supervisor",
                                        "row_number": 2,
                                    }
                                ],
                            },
                        }
                    },
                }
                print(response.json)
                checkdiff = jsondiff.diff(expected_response, response.json)
                assert checkdiff == {}

        else:
            assert response.status_code == 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: WRITE Assignments Upload",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_upload_assignments_overwrite_csv(
        self,
        client,
        login_test_user,
        create_assignments,
        csrf_token,
        user_permissions_with_upload,
        request,
        create_email_config,
        create_email_schedule,
        create_email_template,
    ):
        """
        Function to test uploading asssignments csv with overwrite mode
        """

        user_fixture, expected_permission = user_permissions_with_upload
        request.getfixturevalue(user_fixture)

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_assignments.csv"
        )

        # Read the targets.csv file and convert it to base64
        with open(filepath, "rb") as f:
            assignments_csv = f.read()
            assignments_csv_encoded = base64.b64encode(assignments_csv).decode("utf-8")

        # Try to upload the targets csv
        payload = {
            "column_mapping": {
                "target_id": "target_id1",
                "enumerator_id": "enumerator_id1",
            },
            "file": assignments_csv_encoded,
            "mode": "overwrite",
            "validate_mapping": True,
        }

        response = client.post(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        current_datetime = datetime.now()
        formatted_date = current_datetime.strftime("%a, %d %b %Y") + " 00:00:00 GMT"
        current_time = datetime.now().strftime("%H:%M")

        # Define the format corresponding to the date string
        date_format = "%a, %d %b %Y %H:%M:%S %Z"

        if expected_permission:
            if user_fixture != "user_with_assignment_upload_permissions":
                assert response.status_code == 200
                assert datetime.strptime(
                    response.json["data"]["email_schedule"][0]["schedule_date"],
                    date_format,
                ) >= datetime.strptime(formatted_date, date_format)
                expected_put_response = {
                    "data": {
                        "assignments_count": 2,
                        "new_assignments_count": 2,
                        "no_changes_count": 0,
                        "re_assignments_count": 0,
                        "email_schedule": [
                            {
                                "config_name": "AssignmentsConfig",
                                "dates": response.json["data"]["email_schedule"][0][
                                    "dates"
                                ],
                                "schedule_date": response.json["data"][
                                    "email_schedule"
                                ][0]["schedule_date"],
                                "current_time": current_time,
                                "email_schedule_uid": response.json["data"][
                                    "email_schedule"
                                ][0]["email_schedule_uid"],
                                "email_config_uid": 1,
                                "time": response.json["data"]["email_schedule"][0][
                                    "time"
                                ],
                            }
                        ],
                    },
                    "message": "Success",
                }

                checkdiff = jsondiff.diff(expected_put_response, response.json)
                assert checkdiff == {}

                expected_response = {
                    "data": [
                        {
                            "assigned_enumerator_custom_fields": {
                                "Age": "2",
                                "Mobile (Secondary)": "1123456789",
                                "column_mapping": {
                                    "custom_fields": [
                                        {
                                            "column_name": "mobile_secondary1",
                                            "field_label": "Mobile (Secondary)",
                                        },
                                        {"column_name": "age1", "field_label": "Age"},
                                    ],
                                    "email": "email1",
                                    "enumerator_id": "enumerator_id1",
                                    "enumerator_type": "enumerator_type1",
                                    "gender": "gender1",
                                    "home_address": "home_address1",
                                    "language": "language1",
                                    "location_id_column": "district_id1",
                                    "mobile_primary": "mobile_primary1",
                                    "name": "name1",
                                },
                            },
                            "assigned_enumerator_email": "jahnavi.meher@idinsight.org",
                            "assigned_enumerator_gender": "Female",
                            "assigned_enumerator_home_address": "my house",
                            "assigned_enumerator_id": "0294613",
                            "assigned_enumerator_language": "Telugu",
                            "assigned_enumerator_mobile_primary": "0123456789",
                            "assigned_enumerator_name": "Jahnavi Meher",
                            "assigned_enumerator_uid": 2,
                            "completed_flag": None,
                            "custom_fields": {
                                "Address": "Hyderabad",
                                "Mobile no.": "1234567890",
                                "Name": "Anil",
                                "column_mapping": {
                                    "custom_fields": [
                                        {
                                            "column_name": "mobile_primary1",
                                            "field_label": "Mobile no.",
                                        },
                                        {"column_name": "name1", "field_label": "Name"},
                                        {
                                            "column_name": "address1",
                                            "field_label": "Address",
                                        },
                                    ],
                                    "gender": "gender1",
                                    "language": "language1",
                                    "location_id_column": "psu_id1",
                                    "target_id": "target_id1",
                                },
                            },
                            "form_uid": 1,
                            "gender": "Male",
                            "language": "Telugu",
                            "last_attempt_survey_status": None,
                            "last_attempt_survey_status_label": "Not Attempted",
                            "final_survey_status": None,
                            "final_survey_status_label": "Not Attempted",
                            "scto_fields": None,
                            "supervisors": [
                                {
                                    "role_name": "Regional Coordinator",
                                    "role_uid": 3,
                                    "supervisor_email": "newuser3@example.com",
                                    "supervisor_name": "John Doe",
                                },
                                {
                                    "role_name": "Cluster Coordinator",
                                    "role_uid": 2,
                                    "supervisor_email": "newuser2@example.com",
                                    "supervisor_name": "Ron Doe",
                                },
                                {
                                    "role_name": "Core User",
                                    "role_uid": 1,
                                    "supervisor_email": "newuser1@example.com",
                                    "supervisor_name": "Tim Doe",
                                },
                            ],
                            "location_uid": 4,
                            "num_attempts": 0,
                            "refusal_flag": None,
                            "revisit_sections": None,
                            "target_assignable": True,
                            "target_id": "1",
                            "target_locations": [
                                {
                                    "geo_level_name": "District",
                                    "geo_level_uid": 1,
                                    "location_id": "1",
                                    "location_name": "ADILABAD",
                                    "location_uid": 1,
                                },
                                {
                                    "geo_level_name": "Mandal",
                                    "geo_level_uid": 2,
                                    "location_id": "1101",
                                    "location_name": "ADILABAD RURAL",
                                    "location_uid": 2,
                                },
                                {
                                    "geo_level_name": "PSU",
                                    "geo_level_uid": 3,
                                    "location_id": "17101102",
                                    "location_name": "ANKOLI",
                                    "location_uid": 4,
                                },
                            ],
                            "target_uid": 1,
                            "webapp_tag_color": None,
                        },
                        {
                            "assigned_enumerator_custom_fields": {
                                "Age": "4",
                                "Mobile (Secondary)": "1123456789",
                                "column_mapping": {
                                    "custom_fields": [
                                        {
                                            "column_name": "mobile_secondary1",
                                            "field_label": "Mobile (Secondary)",
                                        },
                                        {"column_name": "age1", "field_label": "Age"},
                                    ],
                                    "email": "email1",
                                    "enumerator_id": "enumerator_id1",
                                    "enumerator_type": "enumerator_type1",
                                    "gender": "gender1",
                                    "home_address": "home_address1",
                                    "language": "language1",
                                    "location_id_column": "district_id1",
                                    "mobile_primary": "mobile_primary1",
                                    "name": "name1",
                                },
                            },
                            "assigned_enumerator_email": "griffin.muteti@idinsight.org",
                            "assigned_enumerator_gender": "Male",
                            "assigned_enumerator_home_address": "my house",
                            "assigned_enumerator_id": "0294615",
                            "assigned_enumerator_language": "Swahili",
                            "assigned_enumerator_mobile_primary": "0123456789",
                            "assigned_enumerator_name": "Griffin Muteti",
                            "assigned_enumerator_uid": 4,
                            "completed_flag": None,
                            "custom_fields": {
                                "Address": "South Delhi",
                                "Mobile no.": "1234567891",
                                "Name": "Anupama",
                                "column_mapping": {
                                    "custom_fields": [
                                        {
                                            "column_name": "mobile_primary1",
                                            "field_label": "Mobile no.",
                                        },
                                        {"column_name": "name1", "field_label": "Name"},
                                        {
                                            "column_name": "address1",
                                            "field_label": "Address",
                                        },
                                    ],
                                    "gender": "gender1",
                                    "language": "language1",
                                    "location_id_column": "psu_id1",
                                    "target_id": "target_id1",
                                },
                            },
                            "form_uid": 1,
                            "gender": "Female",
                            "language": "Hindi",
                            "last_attempt_survey_status": None,
                            "last_attempt_survey_status_label": "Not Attempted",
                            "final_survey_status": None,
                            "final_survey_status_label": "Not Attempted",
                            "scto_fields": None,
                            "supervisors": [
                                {
                                    "role_name": "Regional Coordinator",
                                    "role_uid": 3,
                                    "supervisor_email": "newuser3@example.com",
                                    "supervisor_name": "John Doe",
                                },
                                {
                                    "role_name": "Cluster Coordinator",
                                    "role_uid": 2,
                                    "supervisor_email": "newuser2@example.com",
                                    "supervisor_name": "Ron Doe",
                                },
                                {
                                    "role_name": "Core User",
                                    "role_uid": 1,
                                    "supervisor_email": "newuser1@example.com",
                                    "supervisor_name": "Tim Doe",
                                },
                            ],
                            "location_uid": 4,
                            "num_attempts": 0,
                            "refusal_flag": None,
                            "revisit_sections": None,
                            "target_assignable": True,
                            "target_id": "2",
                            "target_locations": [
                                {
                                    "geo_level_name": "District",
                                    "geo_level_uid": 1,
                                    "location_id": "1",
                                    "location_name": "ADILABAD",
                                    "location_uid": 1,
                                },
                                {
                                    "geo_level_name": "Mandal",
                                    "geo_level_uid": 2,
                                    "location_id": "1101",
                                    "location_name": "ADILABAD RURAL",
                                    "location_uid": 2,
                                },
                                {
                                    "geo_level_name": "PSU",
                                    "geo_level_uid": 3,
                                    "location_id": "17101102",
                                    "location_name": "ANKOLI",
                                    "location_uid": 4,
                                },
                            ],
                            "target_uid": 2,
                            "webapp_tag_color": None,
                        },
                    ],
                    "success": True,
                }

                # Check the response
                response = client.get("/api/assignments", query_string={"form_uid": 1})

                checkdiff = jsondiff.diff(expected_response, response.json)
                assert checkdiff == {}
            else:
                assert response.status_code == 422

                expected_response = {
                    "success": False,
                    "errors": {
                        "record_errors": {
                            "summary": {
                                "total_rows": 2,
                                "total_correct_rows": 0,
                                "total_rows_with_errors": 2,
                                "error_count": 4,
                            },
                            "summary_by_error_type": [
                                {
                                    "error_type": "Not mapped target_id's",
                                    "error_message": "The file contains 2 target_id(s) that are not mapped to current logged in user and hence cannot be assigned by this user. The following row numbers contain such target_id's: 2, 3",
                                    "error_count": 2,
                                    "row_numbers_with_errors": [2, 3],
                                    "can_be_ignored": False,
                                },
                                {
                                    "error_type": "Incorrectly mapped target and enumerator id's",
                                    "error_message": "The file contains 2 target_id(s) that are assigned to enumerators mapped to a different supervisor or the target/enumerator/both are not mapped. The following row numbers contain such target_id's: 2, 3",
                                    "error_count": 2,
                                    "row_numbers_with_errors": [2, 3],
                                    "can_be_ignored": True,
                                },
                            ],
                            "invalid_records": {
                                "ordered_columns": [
                                    "row_number",
                                    "target_id1",
                                    "enumerator_id1",
                                    "errors",
                                ],
                                "records": [
                                    {
                                        "target_id1": "1",
                                        "enumerator_id1": "0294613",
                                        "errors": "Target is not mapped to current logged in user and hence cannot be assigned; Target is assigned to an enumerator mapped to a different supervisor",
                                        "row_number": 2,
                                    },
                                    {
                                        "target_id1": "2",
                                        "enumerator_id1": "0294615",
                                        "errors": "Target is not mapped to current logged in user and hence cannot be assigned; Target is assigned to an enumerator mapped to a different supervisor",
                                        "row_number": 3,
                                    },
                                ],
                            },
                        }
                    },
                }

                print(response.json)
                checkdiff = jsondiff.diff(expected_response, response.json)
                assert checkdiff == {}
        else:
            assert response.status_code == 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: WRITE Assignments Upload",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_upload_assignments_csv_invalid_ids(
        self,
        client,
        login_test_user,
        create_assignments,
        csrf_token,
        create_email_config,
        create_email_schedule,
        create_email_template,
    ):
        """
        Function to test uploading asssignments csv with invalid target_id and enumerator_id
        errors
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_assignments_errors.csv"
        )

        # Read the targets.csv file and convert it to base64
        with open(filepath, "rb") as f:
            assignments_csv = f.read()
            assignments_csv_encoded = base64.b64encode(assignments_csv).decode("utf-8")

        # Try to upload the targets csv
        payload = {
            "column_mapping": {
                "target_id": "target_id1",
                "enumerator_id": "enumerator_id1",
            },
            "file": assignments_csv_encoded,
            "mode": "merge",
        }

        response = client.post(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        expected_put_response = {
            "errors": {
                "record_errors": {
                    "invalid_records": {
                        "ordered_columns": [
                            "row_number",
                            "target_id1",
                            "enumerator_id1",
                            "errors",
                        ],
                        "records": [
                            {
                                "enumerator_id1": "0294614",
                                "errors": "Enumerator id not found in uploaded enumerators data for the form",
                                "row_number": 2,
                                "target_id1": "1",
                            },
                            {
                                "enumerator_id1": "0294612",
                                "errors": "Target id not found in uploaded targets data for the form",
                                "row_number": 3,
                                "target_id1": "3",
                            },
                        ],
                    },
                    "summary": {
                        "error_count": 2,
                        "total_correct_rows": 0,
                        "total_rows": 2,
                        "total_rows_with_errors": 2,
                    },
                    "summary_by_error_type": [
                        {
                            "error_count": 1,
                            "error_message": "The file contains 1 target_id(s) that were not found in the uploaded targets data. The following row numbers contain invalid target_id's: 3",
                            "error_type": "Invalid target_id's",
                            "row_numbers_with_errors": [3],
                            "can_be_ignored": False,
                        },
                        {
                            "error_count": 1,
                            "error_message": "The file contains 1 enumerator_id(s) that were not found in the uploaded enumerators data. The following row numbers contain invalid enumerator_id's: 2",
                            "error_type": "Invalid enumerator_id's",
                            "row_numbers_with_errors": [2],
                            "can_be_ignored": False,
                        },
                    ],
                }
            },
            "success": False,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_put_response, response.json)
        assert checkdiff == {}

    def test_upload_assignments_csv_dropout_enumerator(
        self,
        client,
        login_test_user,
        create_assignments,
        csrf_token,
        create_email_config,
        create_email_schedule,
        create_email_template,
    ):
        """
        #     Function to test uploading asssignments csv with enumerator who has dropped out of the survey
        #"""
        # Update an enumerator's status to Dropout
        payload = {
            "status": "Dropout",
            "form_uid": 1,
            "enumerator_type": "surveyor",
        }

        response = client.patch(
            "/api/enumerators/2/roles/status",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_assignments.csv"
        )

        # Read the targets.csv file and convert it to base64
        with open(filepath, "rb") as f:
            assignments_csv = f.read()
            assignments_csv_encoded = base64.b64encode(assignments_csv).decode("utf-8")

        # Try to upload the targets csv
        payload = {
            "column_mapping": {
                "target_id": "target_id1",
                "enumerator_id": "enumerator_id1",
            },
            "file": assignments_csv_encoded,
            "mode": "overwrite",
        }

        response = client.post(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        expected_put_response = {
            "errors": {
                "record_errors": {
                    "invalid_records": {
                        "ordered_columns": [
                            "row_number",
                            "target_id1",
                            "enumerator_id1",
                            "errors",
                        ],
                        "records": [
                            {
                                "enumerator_id1": "0294613",
                                "errors": "Enumerator id has status 'Dropout' and are ineligible for assignment",
                                "row_number": 2,
                                "target_id1": "1",
                            }
                        ],
                    },
                    "summary": {
                        "error_count": 1,
                        "total_correct_rows": 1,
                        "total_rows": 2,
                        "total_rows_with_errors": 1,
                    },
                    "summary_by_error_type": [
                        {
                            "error_count": 1,
                            "error_message": "The file contains 1 enumerator_id(s) that have status 'Dropout' and are ineligible for assignment. The following row numbers contain dropout enumerator_id's: 2",
                            "error_type": "Dropout enumerator_id's",
                            "row_numbers_with_errors": [2],
                            "can_be_ignored": False,
                        }
                    ],
                }
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_put_response, response.json)
        assert checkdiff == {}

    def test_upload_assignments_csv_unassignable_target(
        self,
        app,
        client,
        login_test_user,
        create_assignments,
        csrf_token,
        create_email_config,
        create_email_schedule,
        create_email_template,
    ):
        """
        Function to test uploading asssignments csv with target that is not assignable
        """
        # Update a target's assignable status to False
        set_target_assignable_status(app, db, 1, False)

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_assignments.csv"
        )

        # Read the targets.csv file and convert it to base64
        with open(filepath, "rb") as f:
            assignments_csv = f.read()
            assignments_csv_encoded = base64.b64encode(assignments_csv).decode("utf-8")

        # Try to upload the targets csv
        payload = {
            "column_mapping": {
                "target_id": "target_id1",
                "enumerator_id": "enumerator_id1",
            },
            "file": assignments_csv_encoded,
            "mode": "overwrite",
        }

        response = client.post(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        expected_put_response = {
            "errors": {
                "record_errors": {
                    "invalid_records": {
                        "ordered_columns": [
                            "row_number",
                            "target_id1",
                            "enumerator_id1",
                            "errors",
                        ],
                        "records": [
                            {
                                "enumerator_id1": "0294613",
                                "errors": "Target id not assignable for this form (most likely because they are complete)",
                                "row_number": 2,
                                "target_id1": "1",
                            }
                        ],
                    },
                    "summary": {
                        "error_count": 1,
                        "total_correct_rows": 1,
                        "total_rows": 2,
                        "total_rows_with_errors": 1,
                    },
                    "summary_by_error_type": [
                        {
                            "error_count": 1,
                            "error_message": "The file contains 1 target_id(s) that were not assignable for this form (most likely because they are complete). The following row numbers contain not assignable target_id's: 2",
                            "error_type": "Not Assignable target_id's",
                            "row_numbers_with_errors": [2],
                            "can_be_ignored": False,
                        }
                    ],
                }
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_put_response, response.json)
        assert checkdiff == {}

    def test_upload_assignments_csv_unmapped_column(
        self,
        client,
        login_test_user,
        create_assignments,
        csrf_token,
        create_email_config,
        create_email_schedule,
        create_email_template,
    ):
        """
        Upload the enumerators csv with unmapped enumerator id column
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_assignments_errors.csv"
        )

        # Read the enumerators.csv file and convert it to base64
        with open(filepath, "rb") as f:
            assignments_csv = f.read()
            assignments_csv_encoded = base64.b64encode(assignments_csv).decode("utf-8")

        # Try to upload the enumerators csv
        payload = {
            "column_mapping": {
                "target_id": "target_id",
            },
            "file": assignments_csv_encoded,
            "mode": "overwrite",
        }

        response = client.post(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        # enumerator_id is needed
        assert response.status_code == 422

        expected_response = {
            "message": {
                "column_mapping": {"enumerator_id": ["This field is required."]}
            },
            "success": False,
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_assignments_csv_missing_enumerator(
        self,
        client,
        login_test_user,
        create_assignments,
        csrf_token,
        create_email_config,
        create_email_schedule,
        create_email_template,
    ):
        """
        Function to test uploading asssignments csv with missing enumerator id
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_assignments_missing_enumerator.csv"
        )

        # Read the targets.csv file and convert it to base64
        with open(filepath, "rb") as f:
            assignments_csv = f.read()
            assignments_csv_encoded = base64.b64encode(assignments_csv).decode("utf-8")

        # Try to upload the targets csv
        payload = {
            "column_mapping": {
                "target_id": "target_id1",
                "enumerator_id": "enumerator_id1",
            },
            "file": assignments_csv_encoded,
            "mode": "merge",
        }

        response = client.post(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        expected_response = {
            "errors": {
                "record_errors": {
                    "invalid_records": {
                        "ordered_columns": [
                            "row_number",
                            "target_id1",
                            "enumerator_id1",
                            "errors",
                        ],
                        "records": [
                            {
                                "enumerator_id1": "",
                                "errors": "Blank field(s) found in the following column(s): enumerator_id1. The column(s) cannot contain blank fields.; Enumerator id not found in uploaded enumerators data for the form",
                                "row_number": 3,
                                "target_id1": "2",
                            }
                        ],
                    },
                    "summary": {
                        "error_count": 2,
                        "total_correct_rows": 1,
                        "total_rows": 2,
                        "total_rows_with_errors": 1,
                    },
                    "summary_by_error_type": [
                        {
                            "error_count": 1,
                            "error_message": "Blank values are not allowed in the following columns: enumerator_id1, target_id1. Blank values in these columns were found for the following row(s): 3",
                            "error_type": "Blank field",
                            "row_numbers_with_errors": [3],
                            "can_be_ignored": False,
                        },
                        {
                            "error_count": 1,
                            "error_message": "The file contains 1 enumerator_id(s) that were not found in the uploaded enumerators data. The following row numbers contain invalid enumerator_id's: 3",
                            "error_type": "Invalid enumerator_id's",
                            "row_numbers_with_errors": [3],
                            "can_be_ignored": False,
                        },
                    ],
                }
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_assignments_csv_duplicate_column(
        self,
        client,
        login_test_user,
        create_assignments,
        csrf_token,
        create_email_config,
        create_email_schedule,
        create_email_template,
    ):
        """
        Function to test uploading asssignments csv with duplicate column
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_assignments_duplicate_column.csv"
        )

        # Read the targets.csv file and convert it to base64
        with open(filepath, "rb") as f:
            assignments_csv = f.read()
            assignments_csv_encoded = base64.b64encode(assignments_csv).decode("utf-8")

        # Try to upload the targets csv
        payload = {
            "column_mapping": {
                "target_id": "target_id1",
                "enumerator_id": "enumerator_id1",
            },
            "file": assignments_csv_encoded,
            "mode": "merge",
        }

        response = client.post(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 422

        expected_response = {
            "errors": {
                "file_structure_errors": [
                    "Column name 'target_id1' from the column mapping appears 2 time(s) in the uploaded file. It should appear exactly once."
                ]
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_assignments_csv_column_mapping_error(
        self,
        client,
        login_test_user,
        create_assignments,
        csrf_token,
        create_email_config,
        create_email_schedule,
        create_email_template,
    ):
        """
        Upload the enumerators csv with same column mapped twice
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_assignments_errors.csv"
        )

        # Read the enumerators.csv file and convert it to base64
        with open(filepath, "rb") as f:
            assignments_csv = f.read()
            assignments_csv_encoded = base64.b64encode(assignments_csv).decode("utf-8")

        # Try to upload the enumerators csv
        payload = {
            "column_mapping": {
                "target_id": "target_id1",
                "enumerator_id": "target_id1",
            },
            "file": assignments_csv_encoded,
            "mode": "overwrite",
        }

        response = client.post(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 422

        # Order of the columns in the error message is not guaranteed, so we need to check both possible responses
        expected_response_1 = {
            "errors": {
                "column_mapping": [
                    "Column name 'target_id1' is mapped to multiple fields: (enumerator_id, target_id). Column names should only be mapped once."
                ]
            },
            "success": False,
        }
        expected_response_2 = {
            "errors": {
                "column_mapping": [
                    "Column name 'target_id1' is mapped to multiple fields: (target_id, enumerator_id). Column names should only be mapped once."
                ]
            },
            "success": False,
        }

        checkdiff_1 = jsondiff.diff(expected_response_1, response.json)
        checkdiff_2 = jsondiff.diff(expected_response_2, response.json)

        assert checkdiff_1 == {} or checkdiff_2 == {}

    def test_upload_assignments_csv_blank_headers(
        self,
        client,
        login_test_user,
        create_assignments,
        csrf_token,
        create_email_config,
        create_email_schedule,
        create_email_template,
    ):
        """
        Upload the enumerators csv with blank header row
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_assignments_blank_headers.csv"
        )

        # Read the enumerators.csv file and convert it to base64
        with open(filepath, "rb") as f:
            assignments_csv = f.read()
            assignments_csv_encoded = base64.b64encode(assignments_csv).decode("utf-8")

        # Try to upload the enumerators csv
        payload = {
            "column_mapping": {
                "target_id": "target_id1",
                "enumerator_id": "enumerator_id1",
            },
            "file": assignments_csv_encoded,
            "mode": "overwrite",
        }

        response = client.post(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        expected_response = {
            "errors": {
                "file_structure_errors": [
                    "Column names were not found in the file. Make sure the first row of the file contains column names."
                ]
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_mismatched_supervisor_assignment_upload(
        self,
        client,
        login_test_user,
        create_assignments,
        csrf_token,
        update_target_mapping_criteria,
        request,
    ):
        """
        Test uploading assignments with mismatched supervisor
        """
        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_assignments_mismatched_supervisor.csv"
        )

        # Read the targets.csv file and convert it to base64
        with open(filepath, "rb") as f:
            assignments_csv = f.read()
            assignments_csv_encoded = base64.b64encode(assignments_csv).decode("utf-8")

        # Try to upload the targets csv
        payload = {
            "column_mapping": {
                "target_id": "target_id1",
                "enumerator_id": "enumerator_id1",
            },
            "file": assignments_csv_encoded,
            "mode": "merge",
            "validate_mapping": True,
        }

        response = client.post(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 422
        expected_response = {
            "errors": {
                "record_errors": {
                    "invalid_records": {
                        "ordered_columns": [
                            "row_number",
                            "target_id1",
                            "enumerator_id1",
                            "errors",
                        ],
                        "records": [
                            {
                                "enumerator_id1": "0294615",
                                "errors": "Target is assigned to an enumerator mapped to a different supervisor",
                                "row_number": 2,
                                "target_id1": "1",
                            }
                        ],
                    },
                    "summary": {
                        "error_count": 1,
                        "total_correct_rows": 0,
                        "total_rows": 1,
                        "total_rows_with_errors": 1,
                    },
                    "summary_by_error_type": [
                        {
                            "error_count": 1,
                            "error_message": "The file contains 1 target_id(s) that are assigned to enumerators mapped to a different supervisor or the target/enumerator/both are not mapped. The following row numbers contain such target_id's: 2",
                            "error_type": "Incorrectly mapped target and enumerator id's",
                            "row_numbers_with_errors": [2],
                            "can_be_ignored": True,
                        }
                    ],
                }
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_available_columns(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        create_enumerator_column_config,
        create_target_column_config,
        csrf_token,
    ):
        """
        Test the available columns endpoint
        """

        response = client.get(
            "/api/assignments/table-config/available-columns",
            query_string={"form_uid": 1},
        )

        assert response.status_code == 200

        expected_response = {
            "assignments_main": [
                {
                    "column_key": "assigned_enumerator_name",
                    "column_label": "Surveyor Name",
                },
                {"column_key": "assigned_enumerator_id", "column_label": "Surveyor ID"},
                {
                    "column_key": "assigned_enumerator_home_address",
                    "column_label": "Surveyor Address",
                },
                {
                    "column_key": "assigned_enumerator_gender",
                    "column_label": "Surveyor Gender",
                },
                {
                    "column_key": "assigned_enumerator_language",
                    "column_label": "Surveyor Language",
                },
                {
                    "column_key": "assigned_enumerator_email",
                    "column_label": "Surveyor Email",
                },
                {
                    "column_key": "assigned_enumerator_mobile_primary",
                    "column_label": "Surveyor Mobile",
                },
                {
                    "column_key": "assigned_enumerator_custom_fields['Mobile (Secondary)']",
                    "column_label": "Mobile (Secondary)",
                },
                {
                    "column_key": "assigned_enumerator_custom_fields['Age']",
                    "column_label": "Age",
                },
                {"column_key": "target_id", "column_label": "Target ID"},
                {"column_key": "gender", "column_label": "Gender"},
                {"column_key": "language", "column_label": "Language"},
                {"column_key": "custom_fields['Name']", "column_label": "Name"},
                {
                    "column_key": "custom_fields['Mobile no.']",
                    "column_label": "Mobile no.",
                },
                {"column_key": "custom_fields['Address']", "column_label": "Address"},
                {
                    "column_key": "target_locations[0].location_id",
                    "column_label": "District ID",
                },
                {
                    "column_key": "target_locations[0].location_name",
                    "column_label": "District Name",
                },
                {
                    "column_key": "target_locations[1].location_id",
                    "column_label": "Mandal ID",
                },
                {
                    "column_key": "target_locations[1].location_name",
                    "column_label": "Mandal Name",
                },
                {
                    "column_key": "target_locations[2].location_id",
                    "column_label": "PSU ID",
                },
                {
                    "column_key": "target_locations[2].location_name",
                    "column_label": "PSU Name",
                },
                {
                    "column_key": "final_survey_status_label",
                    "column_label": "Final Survey Status",
                },
                {
                    "column_key": "final_survey_status",
                    "column_label": "Final Survey Status Code",
                },
                {"column_key": "revisit_sections", "column_label": "Revisit Sections"},
                {"column_key": "num_attempts", "column_label": "Total Attempts"},
                {"column_key": "refusal_flag", "column_label": "Refused"},
                {"column_key": "completed_flag", "column_label": "Completed"},
                {
                    "column_key": "supervisors[2].supervisor_name",
                    "column_label": "Core User Name",
                },
                {
                    "column_key": "supervisors[2].supervisor_email",
                    "column_label": "Core User Email",
                },
                {
                    "column_key": "supervisors[1].supervisor_name",
                    "column_label": "Cluster Coordinator Name",
                },
                {
                    "column_key": "supervisors[1].supervisor_email",
                    "column_label": "Cluster Coordinator Email",
                },
                {
                    "column_key": "supervisors[0].supervisor_name",
                    "column_label": "Regional Coordinator Name",
                },
                {
                    "column_key": "supervisors[0].supervisor_email",
                    "column_label": "Regional Coordinator Email",
                },
            ],
            "assignments_review": [
                {
                    "column_key": "assigned_enumerator_name",
                    "column_label": "Surveyor Name",
                },
                {
                    "column_key": "prev_assigned_to",
                    "column_label": "Previously Assigned To",
                },
                {"column_key": "assigned_enumerator_id", "column_label": "Surveyor ID"},
                {
                    "column_key": "assigned_enumerator_home_address",
                    "column_label": "Surveyor Address",
                },
                {
                    "column_key": "assigned_enumerator_gender",
                    "column_label": "Surveyor Gender",
                },
                {
                    "column_key": "assigned_enumerator_language",
                    "column_label": "Surveyor Language",
                },
                {
                    "column_key": "assigned_enumerator_email",
                    "column_label": "Surveyor Email",
                },
                {
                    "column_key": "assigned_enumerator_mobile_primary",
                    "column_label": "Surveyor Mobile",
                },
                {
                    "column_key": "assigned_enumerator_custom_fields['Mobile (Secondary)']",
                    "column_label": "Mobile (Secondary)",
                },
                {
                    "column_key": "assigned_enumerator_custom_fields['Age']",
                    "column_label": "Age",
                },
                {"column_key": "target_id", "column_label": "Target ID"},
                {"column_key": "gender", "column_label": "Gender"},
                {"column_key": "language", "column_label": "Language"},
                {"column_key": "custom_fields['Name']", "column_label": "Name"},
                {
                    "column_key": "custom_fields['Mobile no.']",
                    "column_label": "Mobile no.",
                },
                {"column_key": "custom_fields['Address']", "column_label": "Address"},
                {
                    "column_key": "target_locations[0].location_id",
                    "column_label": "District ID",
                },
                {
                    "column_key": "target_locations[0].location_name",
                    "column_label": "District Name",
                },
                {
                    "column_key": "target_locations[1].location_id",
                    "column_label": "Mandal ID",
                },
                {
                    "column_key": "target_locations[1].location_name",
                    "column_label": "Mandal Name",
                },
                {
                    "column_key": "target_locations[2].location_id",
                    "column_label": "PSU ID",
                },
                {
                    "column_key": "target_locations[2].location_name",
                    "column_label": "PSU Name",
                },
                {
                    "column_key": "final_survey_status_label",
                    "column_label": "Final Survey Status",
                },
                {
                    "column_key": "final_survey_status",
                    "column_label": "Final Survey Status Code",
                },
                {"column_key": "revisit_sections", "column_label": "Revisit Sections"},
                {"column_key": "num_attempts", "column_label": "Total Attempts"},
                {"column_key": "refusal_flag", "column_label": "Refused"},
                {"column_key": "completed_flag", "column_label": "Completed"},
                {
                    "column_key": "supervisors[2].supervisor_name",
                    "column_label": "Core User Name",
                },
                {
                    "column_key": "supervisors[2].supervisor_email",
                    "column_label": "Core User Email",
                },
                {
                    "column_key": "supervisors[1].supervisor_name",
                    "column_label": "Cluster Coordinator Name",
                },
                {
                    "column_key": "supervisors[1].supervisor_email",
                    "column_label": "Cluster Coordinator Email",
                },
                {
                    "column_key": "supervisors[0].supervisor_name",
                    "column_label": "Regional Coordinator Name",
                },
                {
                    "column_key": "supervisors[0].supervisor_email",
                    "column_label": "Regional Coordinator Email",
                },
            ],
            "assignments_surveyors": [
                {"column_key": "enumerator_id", "column_label": "ID"},
                {"column_key": "name", "column_label": "Name"},
                {"column_key": "surveyor_status", "column_label": "Status"},
                {
                    "column_key": "surveyor_locations[0].location_id",
                    "column_label": "District ID",
                },
                {
                    "column_key": "surveyor_locations[0].location_name",
                    "column_label": "District Name",
                },
                {
                    "column_key": "form_productivity.test_scto_input_output.total_assigned_targets",
                    "column_label": "Total Assigned Targets",
                },
                {
                    "column_key": "form_productivity.test_scto_input_output.total_pending_targets",
                    "column_label": "Total Pending Targets",
                },
                {
                    "column_key": "form_productivity.test_scto_input_output.total_completed_targets",
                    "column_label": "Total Completed Targets",
                },
                {"column_key": "gender", "column_label": "Gender"},
                {"column_key": "language", "column_label": "Language"},
                {"column_key": "home_address", "column_label": "Address"},
                {"column_key": "email", "column_label": "Email"},
                {"column_key": "mobile_primary", "column_label": "Mobile"},
                {
                    "column_key": "custom_fields['Mobile (Secondary)']",
                    "column_label": "Mobile (Secondary)",
                },
                {"column_key": "custom_fields['Age']", "column_label": "Age"},
            ],
            "surveyors": [
                {"column_key": "name", "column_label": "Name"},
                {"column_key": "enumerator_id", "column_label": "ID"},
                {"column_key": "surveyor_status", "column_label": "Status"},
                {
                    "column_key": "surveyor_locations[0].location_id",
                    "column_label": "District ID",
                },
                {
                    "column_key": "surveyor_locations[0].location_name",
                    "column_label": "District Name",
                },
                {"column_key": "email", "column_label": "Email"},
                {"column_key": "mobile_primary", "column_label": "Mobile"},
                {"column_key": "gender", "column_label": "Gender"},
                {"column_key": "language", "column_label": "Language"},
                {"column_key": "home_address", "column_label": "Address"},
                {
                    "column_key": "custom_fields['Mobile (Secondary)']",
                    "column_label": "Mobile (Secondary)",
                },
                {"column_key": "custom_fields['Age']", "column_label": "Age"},
                {
                    "column_key": "supervisors[2].supervisor_name",
                    "column_label": "Core User Name",
                },
                {
                    "column_key": "supervisors[2].supervisor_email",
                    "column_label": "Core User Email",
                },
                {
                    "column_key": "supervisors[1].supervisor_name",
                    "column_label": "Cluster Coordinator Name",
                },
                {
                    "column_key": "supervisors[1].supervisor_email",
                    "column_label": "Cluster Coordinator Email",
                },
                {
                    "column_key": "supervisors[0].supervisor_name",
                    "column_label": "Regional Coordinator Name",
                },
                {
                    "column_key": "supervisors[0].supervisor_email",
                    "column_label": "Regional Coordinator Email",
                },
            ],
            "targets": [
                {"column_key": "target_id", "column_label": "Target ID"},
                {"column_key": "gender", "column_label": "Gender"},
                {"column_key": "language", "column_label": "Language"},
                {"column_key": "custom_fields['Name']", "column_label": "Name"},
                {
                    "column_key": "custom_fields['Mobile no.']",
                    "column_label": "Mobile no.",
                },
                {"column_key": "custom_fields['Address']", "column_label": "Address"},
                {
                    "column_key": "target_locations[0].location_id",
                    "column_label": "District ID",
                },
                {
                    "column_key": "target_locations[0].location_name",
                    "column_label": "District Name",
                },
                {
                    "column_key": "target_locations[1].location_id",
                    "column_label": "Mandal ID",
                },
                {
                    "column_key": "target_locations[1].location_name",
                    "column_label": "Mandal Name",
                },
                {
                    "column_key": "target_locations[2].location_id",
                    "column_label": "PSU ID",
                },
                {
                    "column_key": "target_locations[2].location_name",
                    "column_label": "PSU Name",
                },
                {
                    "column_key": "final_survey_status_label",
                    "column_label": "Final Survey Status",
                },
                {
                    "column_key": "final_survey_status",
                    "column_label": "Final Survey Status Code",
                },
                {"column_key": "revisit_sections", "column_label": "Revisit Sections"},
                {"column_key": "num_attempts", "column_label": "Total Attempts"},
                {"column_key": "refusal_flag", "column_label": "Refused"},
                {"column_key": "completed_flag", "column_label": "Completed"},
                {
                    "column_key": "supervisors[2].supervisor_name",
                    "column_label": "Core User Name",
                },
                {
                    "column_key": "supervisors[2].supervisor_email",
                    "column_label": "Core User Email",
                },
                {
                    "column_key": "supervisors[1].supervisor_name",
                    "column_label": "Cluster Coordinator Name",
                },
                {
                    "column_key": "supervisors[1].supervisor_email",
                    "column_label": "Cluster Coordinator Email",
                },
                {
                    "column_key": "supervisors[0].supervisor_name",
                    "column_label": "Regional Coordinator Name",
                },
                {
                    "column_key": "supervisors[0].supervisor_email",
                    "column_label": "Regional Coordinator Email",
                },
            ],
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_assignments_non_core_user_login_without_assignments(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
        test_user_credentials,
        request,
    ):
        """
        Test the assignments endpoint response with a non core user login without
        any mapped targets
        """

        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[2],
        )

        login_user(client, test_user_credentials)

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        expected_response = {
            "data": [],
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignments_fsl_1_login(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy_with_fsl_1_login,
        test_user_credentials,
        csrf_token,
        request,
    ):
        """
        Test the assignments endpoint response with a field level supervisor 1 login
        """
        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[1],  # FS L1 role
        )

        login_user(client, test_user_credentials)

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        expected_response = {
            "data": [
                {
                    "assigned_enumerator_custom_fields": None,
                    "assigned_enumerator_email": None,
                    "assigned_enumerator_gender": None,
                    "assigned_enumerator_home_address": None,
                    "assigned_enumerator_id": None,
                    "assigned_enumerator_language": None,
                    "assigned_enumerator_mobile_primary": None,
                    "assigned_enumerator_name": None,
                    "assigned_enumerator_uid": None,
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "South Delhi",
                        "Mobile no.": "1234567891",
                        "Name": "Anupama",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {
                                    "column_name": "address1",
                                    "field_label": "Address",
                                },
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                    ],
                    "location_uid": 4,
                    "num_attempts": 0,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": True,
                    "target_id": "2",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 2,
                    "webapp_tag_color": None,
                },
                {
                    "assigned_enumerator_custom_fields": None,
                    "assigned_enumerator_email": None,
                    "assigned_enumerator_gender": None,
                    "assigned_enumerator_home_address": None,
                    "assigned_enumerator_id": None,
                    "assigned_enumerator_language": None,
                    "assigned_enumerator_mobile_primary": None,
                    "assigned_enumerator_name": None,
                    "assigned_enumerator_uid": None,
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "Hyderabad",
                        "Mobile no.": "1234567890",
                        "Name": "Anil",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {
                                    "column_name": "address1",
                                    "field_label": "Address",
                                },
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                    ],
                    "location_uid": 4,
                    "num_attempts": 0,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": True,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 1,
                    "webapp_tag_color": None,
                },
            ],
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignments_fsl_2_login(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy_with_fsl_2_login,
        csrf_token,
        test_user_credentials,
        request,
    ):
        """
        Test the assignments endpoint response with a field level supervisor 2 login
        """
        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[2],  # FS L2 role
        )

        login_user(client, test_user_credentials)

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        expected_response = {
            "data": [
                {
                    "assigned_enumerator_custom_fields": None,
                    "assigned_enumerator_email": None,
                    "assigned_enumerator_gender": None,
                    "assigned_enumerator_home_address": None,
                    "assigned_enumerator_id": None,
                    "assigned_enumerator_language": None,
                    "assigned_enumerator_mobile_primary": None,
                    "assigned_enumerator_name": None,
                    "assigned_enumerator_uid": None,
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "South Delhi",
                        "Mobile no.": "1234567891",
                        "Name": "Anupama",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {
                                    "column_name": "address1",
                                    "field_label": "Address",
                                },
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                    ],
                    "location_uid": 4,
                    "num_attempts": 0,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": True,
                    "target_id": "2",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 2,
                    "webapp_tag_color": None,
                },
                {
                    "assigned_enumerator_custom_fields": None,
                    "assigned_enumerator_email": None,
                    "assigned_enumerator_gender": None,
                    "assigned_enumerator_home_address": None,
                    "assigned_enumerator_id": None,
                    "assigned_enumerator_language": None,
                    "assigned_enumerator_mobile_primary": None,
                    "assigned_enumerator_name": None,
                    "assigned_enumerator_uid": None,
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "Hyderabad",
                        "Mobile no.": "1234567890",
                        "Name": "Anil",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {
                                    "column_name": "address1",
                                    "field_label": "Address",
                                },
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                    ],
                    "location_uid": 4,
                    "num_attempts": 0,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": True,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 1,
                    "webapp_tag_color": None,
                },
            ],
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignments_fsl_3_login_with_custom_mapping(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy_with_fsl_3_login,
        add_custom_target_mapping_test_user,
        csrf_token,
        test_user_credentials,
        request,
    ):
        """
        Test the assignments endpoint response with a field level 3 supervisor login
        with access to only a subset of the targets
        """

        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[3],  # FS L3 role
            location_uids=[1],
        )

        login_user(client, test_user_credentials)

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        expected_response = {
            "data": [
                {
                    "assigned_enumerator_custom_fields": None,
                    "assigned_enumerator_email": None,
                    "assigned_enumerator_gender": None,
                    "assigned_enumerator_home_address": None,
                    "assigned_enumerator_id": None,
                    "assigned_enumerator_language": None,
                    "assigned_enumerator_mobile_primary": None,
                    "assigned_enumerator_name": None,
                    "assigned_enumerator_uid": None,
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "Hyderabad",
                        "Mobile no.": "1234567890",
                        "Name": "Anil",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {
                                    "column_name": "address1",
                                    "field_label": "Address",
                                },
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "scto_fields": None,
                    "supervisors": [],
                    "location_uid": 4,
                    "num_attempts": 0,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": True,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 1,
                    "webapp_tag_color": None,
                }
            ],
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_eligible_enumerators_non_core_user_login(
        self,
        app,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        test_user_credentials,
        csrf_token,
    ):
        """
        Test the assignable enumerators endpoint with a non-core user login
        without any mapped surveyors
        """

        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[2],
        )

        login_user(client, test_user_credentials)

        expected_response = {
            "data": [],
            "success": True,
        }
        response = client.get(
            "/api/assignments/enumerators", query_string={"form_uid": 1}
        )

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_eligible_enumerators_fsl_1_login(
        self,
        app,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy_with_fsl_1_login,
        test_user_credentials,
        csrf_token,
    ):
        """
        Test the assignable enumerators endpoint with a field level supervisor 1 login
        We will also check that the productivity stats are correct
        """

        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[1],  # FS L1 role
        )

        login_user(client, test_user_credentials)

        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 1},
                {"target_uid": 2, "enumerator_uid": 2},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 200

        set_target_assignable_status(app, db, 1, True)
        set_target_assignable_status(app, db, 2, False)

        # Check the response

        expected_response = {
            "data": [
                {
                    "custom_fields": {
                        "Age": "1",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "email": "eric.dodge@idinsight.org",
                    "enumerator_id": "0294612",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "geo_level_uid": 1,
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "enumerator_uid": 1,
                    "form_productivity": {
                        "test_scto_input_output": {
                            "form_name": "Agrifieldnet Main Form",
                            "scto_form_id": "test_scto_input_output",
                            "total_assigned_targets": 1,
                            "total_completed_targets": 0,
                            "total_pending_targets": 1,
                            "avg_num_completed_per_day": 0,
                            "avg_num_submissions_per_day": 0,
                        }
                    },
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "English",
                    "mobile_primary": "0123456789",
                    "name": "Eric Dodge",
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                    ],
                    "surveyor_status": "Active",
                },
                {
                    "custom_fields": {
                        "Age": "2",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "email": "jahnavi.meher@idinsight.org",
                    "enumerator_id": "0294613",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "geo_level_uid": 1,
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "enumerator_uid": 2,
                    "form_productivity": {
                        "test_scto_input_output": {
                            "form_name": "Agrifieldnet Main Form",
                            "scto_form_id": "test_scto_input_output",
                            "total_assigned_targets": 1,
                            "total_completed_targets": 1,
                            "total_pending_targets": 0,
                            "avg_num_completed_per_day": 0,
                            "avg_num_submissions_per_day": 0,
                        }
                    },
                    "gender": "Female",
                    "home_address": "my house",
                    "language": "Telugu",
                    "mobile_primary": "0123456789",
                    "name": "Jahnavi Meher",
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                    ],
                    "surveyor_status": "Active",
                },
                {
                    "custom_fields": {
                        "Age": "4",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "email": "griffin.muteti@idinsight.org",
                    "enumerator_id": "0294615",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "geo_level_uid": 1,
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "enumerator_uid": 4,
                    "form_productivity": {
                        "test_scto_input_output": {
                            "form_name": "Agrifieldnet Main Form",
                            "scto_form_id": "test_scto_input_output",
                            "total_assigned_targets": 0,
                            "total_completed_targets": 0,
                            "total_pending_targets": 0,
                            "avg_num_completed_per_day": 0,
                            "avg_num_submissions_per_day": 0,
                        }
                    },
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Swahili",
                    "mobile_primary": "0123456789",
                    "name": "Griffin Muteti",
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                    ],
                    "surveyor_status": "Active",
                },
            ],
            "success": True,
        }

        response = client.get(
            "/api/assignments/enumerators", query_string={"form_uid": 1}
        )

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_eligible_enumerators_fsl_2_login(
        self,
        app,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy_with_fsl_2_login,
        test_user_credentials,
        csrf_token,
    ):
        """
        Test the assignable enumerators endpoint with a field level supervisor 2 login
        We will also check that the productivity stats are correct
        """

        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[2],  # FS L2 role
        )

        login_user(client, test_user_credentials)

        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 1},
                {"target_uid": 2, "enumerator_uid": 2},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 200

        set_target_assignable_status(app, db, 1, True)
        set_target_assignable_status(app, db, 2, False)

        # Check the response

        expected_response = {
            "data": [
                {
                    "custom_fields": {
                        "Age": "1",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "email": "eric.dodge@idinsight.org",
                    "enumerator_id": "0294612",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "geo_level_uid": 1,
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "enumerator_uid": 1,
                    "form_productivity": {
                        "test_scto_input_output": {
                            "form_name": "Agrifieldnet Main Form",
                            "scto_form_id": "test_scto_input_output",
                            "total_assigned_targets": 1,
                            "total_completed_targets": 0,
                            "total_pending_targets": 1,
                            "avg_num_completed_per_day": 0,
                            "avg_num_submissions_per_day": 0,
                        }
                    },
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "English",
                    "mobile_primary": "0123456789",
                    "name": "Eric Dodge",
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        }
                    ],
                    "surveyor_status": "Active",
                },
                {
                    "custom_fields": {
                        "Age": "2",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "email": "jahnavi.meher@idinsight.org",
                    "enumerator_id": "0294613",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "geo_level_uid": 1,
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "enumerator_uid": 2,
                    "form_productivity": {
                        "test_scto_input_output": {
                            "form_name": "Agrifieldnet Main Form",
                            "scto_form_id": "test_scto_input_output",
                            "total_assigned_targets": 1,
                            "total_completed_targets": 1,
                            "total_pending_targets": 0,
                            "avg_num_completed_per_day": 0,
                            "avg_num_submissions_per_day": 0,
                        }
                    },
                    "gender": "Female",
                    "home_address": "my house",
                    "language": "Telugu",
                    "mobile_primary": "0123456789",
                    "name": "Jahnavi Meher",
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        }
                    ],
                    "surveyor_status": "Active",
                },
                {
                    "custom_fields": {
                        "Age": "4",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "email": "griffin.muteti@idinsight.org",
                    "enumerator_id": "0294615",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "geo_level_uid": 1,
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "enumerator_uid": 4,
                    "form_productivity": {
                        "test_scto_input_output": {
                            "form_name": "Agrifieldnet Main Form",
                            "scto_form_id": "test_scto_input_output",
                            "total_assigned_targets": 0,
                            "total_completed_targets": 0,
                            "total_pending_targets": 0,
                            "avg_num_completed_per_day": 0,
                            "avg_num_submissions_per_day": 0,
                        }
                    },
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Swahili",
                    "mobile_primary": "0123456789",
                    "name": "Griffin Muteti",
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        }
                    ],
                    "surveyor_status": "Active",
                },
            ],
            "success": True,
        }

        response = client.get(
            "/api/assignments/enumerators", query_string={"form_uid": 1}
        )

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_eligible_enumerators_fsl_3_login_with_custom_mapping(
        self,
        app,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy_with_fsl_3_login,
        add_custom_target_mapping_test_user,
        add_custom_surveyor_mapping_test_user,
        test_user_credentials,
        csrf_token,
    ):
        """
        Test the assignable enumerators endpoint with a field level supervisor 3 login
        with access to only a subset of enumerators
        We will also check that the productivity stats are correct
        """

        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[3],  # FS L3 role
            location_uids=[1],
        )

        login_user(client, test_user_credentials)

        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 1},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 200

        set_target_assignable_status(app, db, 1, True)

        # Check the response

        expected_response = {
            "data": [
                {
                    "custom_fields": {
                        "Age": "1",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "email": "eric.dodge@idinsight.org",
                    "enumerator_id": "0294612",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "geo_level_uid": 1,
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "enumerator_uid": 1,
                    "form_productivity": {
                        "test_scto_input_output": {
                            "form_name": "Agrifieldnet Main Form",
                            "scto_form_id": "test_scto_input_output",
                            "total_assigned_targets": 1,
                            "total_completed_targets": 0,
                            "total_pending_targets": 1,
                            "avg_num_completed_per_day": 0,
                            "avg_num_submissions_per_day": 0,
                        }
                    },
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "English",
                    "mobile_primary": "0123456789",
                    "name": "Eric Dodge",
                    "supervisors": [],
                    "surveyor_status": "Active",
                }
            ],
            "success": True,
        }

        response = client.get(
            "/api/assignments/enumerators", query_string={"form_uid": 1}
        )

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_asssignment_targets(
        self,
        app,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        user_permissions,
        csrf_token,
        request,
    ):
        """
        Test the assignable targets endpoint
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get("/api/assignments/targets", query_string={"form_uid": 1})

        if expected_permission:
            if user_fixture != "user_with_assignment_permissions":
                response.status_code == 200

                # Check the response
                expected_response = {
                    "data": [
                        {
                            "completed_flag": None,
                            "custom_fields": {
                                "Address": "Hyderabad",
                                "Mobile no.": "1234567890",
                                "Name": "Anil",
                                "column_mapping": {
                                    "custom_fields": [
                                        {
                                            "column_name": "mobile_primary1",
                                            "field_label": "Mobile no.",
                                        },
                                        {"column_name": "name1", "field_label": "Name"},
                                        {
                                            "column_name": "address1",
                                            "field_label": "Address",
                                        },
                                    ],
                                    "gender": "gender1",
                                    "language": "language1",
                                    "location_id_column": "psu_id1",
                                    "target_id": "target_id1",
                                },
                            },
                            "final_survey_status": None,
                            "final_survey_status_label": None,
                            "form_uid": 1,
                            "gender": "Male",
                            "language": "Telugu",
                            "last_attempt_survey_status": None,
                            "last_attempt_survey_status_label": None,
                            "location_uid": 4,
                            "num_attempts": None,
                            "refusal_flag": None,
                            "revisit_sections": None,
                            "scto_fields": None,
                            "supervisors": [
                                {
                                    "role_name": "Regional Coordinator",
                                    "role_uid": 3,
                                    "supervisor_email": "newuser3@example.com",
                                    "supervisor_name": "John Doe",
                                },
                                {
                                    "role_name": "Cluster Coordinator",
                                    "role_uid": 2,
                                    "supervisor_email": "newuser2@example.com",
                                    "supervisor_name": "Ron Doe",
                                },
                                {
                                    "role_name": "Core User",
                                    "role_uid": 1,
                                    "supervisor_email": "newuser1@example.com",
                                    "supervisor_name": "Tim Doe",
                                },
                            ],
                            "target_assignable": None,
                            "target_id": "1",
                            "target_locations": [
                                {
                                    "geo_level_name": "District",
                                    "geo_level_uid": 1,
                                    "location_id": "1",
                                    "location_name": "ADILABAD",
                                    "location_uid": 1,
                                },
                                {
                                    "geo_level_name": "Mandal",
                                    "geo_level_uid": 2,
                                    "location_id": "1101",
                                    "location_name": "ADILABAD RURAL",
                                    "location_uid": 2,
                                },
                                {
                                    "geo_level_name": "PSU",
                                    "geo_level_uid": 3,
                                    "location_id": "17101102",
                                    "location_name": "ANKOLI",
                                    "location_uid": 4,
                                },
                            ],
                            "target_uid": 1,
                            "webapp_tag_color": None,
                        },
                        {
                            "completed_flag": None,
                            "custom_fields": {
                                "Address": "South Delhi",
                                "Mobile no.": "1234567891",
                                "Name": "Anupama",
                                "column_mapping": {
                                    "custom_fields": [
                                        {
                                            "column_name": "mobile_primary1",
                                            "field_label": "Mobile no.",
                                        },
                                        {"column_name": "name1", "field_label": "Name"},
                                        {
                                            "column_name": "address1",
                                            "field_label": "Address",
                                        },
                                    ],
                                    "gender": "gender1",
                                    "language": "language1",
                                    "location_id_column": "psu_id1",
                                    "target_id": "target_id1",
                                },
                            },
                            "final_survey_status": None,
                            "final_survey_status_label": None,
                            "form_uid": 1,
                            "gender": "Female",
                            "language": "Hindi",
                            "last_attempt_survey_status": None,
                            "last_attempt_survey_status_label": None,
                            "location_uid": 4,
                            "num_attempts": None,
                            "refusal_flag": None,
                            "revisit_sections": None,
                            "scto_fields": None,
                            "supervisors": [
                                {
                                    "role_name": "Regional Coordinator",
                                    "role_uid": 3,
                                    "supervisor_email": "newuser3@example.com",
                                    "supervisor_name": "John Doe",
                                },
                                {
                                    "role_name": "Cluster Coordinator",
                                    "role_uid": 2,
                                    "supervisor_email": "newuser2@example.com",
                                    "supervisor_name": "Ron Doe",
                                },
                                {
                                    "role_name": "Core User",
                                    "role_uid": 1,
                                    "supervisor_email": "newuser1@example.com",
                                    "supervisor_name": "Tim Doe",
                                },
                            ],
                            "target_assignable": None,
                            "target_id": "2",
                            "target_locations": [
                                {
                                    "geo_level_name": "District",
                                    "geo_level_uid": 1,
                                    "location_id": "1",
                                    "location_name": "ADILABAD",
                                    "location_uid": 1,
                                },
                                {
                                    "geo_level_name": "Mandal",
                                    "geo_level_uid": 2,
                                    "location_id": "1101",
                                    "location_name": "ADILABAD RURAL",
                                    "location_uid": 2,
                                },
                                {
                                    "geo_level_name": "PSU",
                                    "geo_level_uid": 3,
                                    "location_id": "17101102",
                                    "location_name": "ANKOLI",
                                    "location_uid": 4,
                                },
                            ],
                            "target_uid": 2,
                            "webapp_tag_color": None,
                        },
                    ],
                    "success": True,
                }

                print(response.json)
                checkdiff = jsondiff.diff(expected_response, response.json)
                assert checkdiff == {}
            else:
                response.status_code == 200

                # Check the response
                expected_response = {
                    "data": [],
                    "success": True,
                }
                print(response.json)
                checkdiff = jsondiff.diff(expected_response, response.json)
                assert checkdiff == {}
        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Assignments",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_assignment_targets_non_core_user_login(
        self,
        app,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        test_user_credentials,
        csrf_token,
    ):
        """
        Test the assignments targets endpoint with a non-core user login
        without any mapped targets
        """

        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[2],
        )

        login_user(client, test_user_credentials)

        expected_response = {
            "data": [],
            "success": True,
        }
        response = client.get("/api/assignments/targets", query_string={"form_uid": 1})

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignment_targets_fsl_1_login(
        self,
        app,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy_with_fsl_1_login,
        test_user_credentials,
        csrf_token,
    ):
        """
        Test the assignment targets endpoint with a field level supervisor 1 login
        """

        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[1],  # FS L1 role
        )

        login_user(client, test_user_credentials)

        # Check the response
        expected_response = {
            "data": [
                {
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "South Delhi",
                        "Mobile no.": "1234567891",
                        "Name": "Anupama",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {
                                    "column_name": "address1",
                                    "field_label": "Address",
                                },
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                    ],
                    "target_assignable": None,
                    "target_id": "2",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 2,
                    "webapp_tag_color": None,
                },
                {
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "Hyderabad",
                        "Mobile no.": "1234567890",
                        "Name": "Anil",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {
                                    "column_name": "address1",
                                    "field_label": "Address",
                                },
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                    ],
                    "target_assignable": None,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 1,
                    "webapp_tag_color": None,
                },
            ],
            "success": True,
        }

        response = client.get("/api/assignments/targets", query_string={"form_uid": 1})

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignment_targets_fsl_2_login(
        self,
        app,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy_with_fsl_2_login,
        test_user_credentials,
        csrf_token,
    ):
        """
        Test the assignable enumerators endpoint with a field level supervisor 2 login
        We will also check that the productivity stats are correct
        """

        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[2],  # FS L2 role
        )

        login_user(client, test_user_credentials)

        response = client.get("/api/assignments/targets", query_string={"form_uid": 1})

        # Check the response
        expected_response = {
            "data": [
                {
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "South Delhi",
                        "Mobile no.": "1234567891",
                        "Name": "Anupama",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {
                                    "column_name": "address1",
                                    "field_label": "Address",
                                },
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                    ],
                    "target_assignable": None,
                    "target_id": "2",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 2,
                    "webapp_tag_color": None,
                },
                {
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "Hyderabad",
                        "Mobile no.": "1234567890",
                        "Name": "Anil",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {
                                    "column_name": "address1",
                                    "field_label": "Address",
                                },
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                    ],
                    "target_assignable": None,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 1,
                    "webapp_tag_color": None,
                },
            ],
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignment_targets_fsl_3_login_with_custom_mapping(
        self,
        app,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy_with_fsl_3_login,
        add_custom_target_mapping_test_user,
        add_custom_surveyor_mapping_test_user,
        test_user_credentials,
        csrf_token,
    ):
        """
        Test the assignment targets endpoint with a field level supervisor 3 login
        with access to only a subset of targets
        """

        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[3],  # FS L3 role
            location_uids=[1],
        )

        login_user(client, test_user_credentials)

        response = client.get("/api/assignments/targets", query_string={"form_uid": 1})

        # Check the response
        expected_response = {
            "data": [
                {
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "Hyderabad",
                        "Mobile no.": "1234567890",
                        "Name": "Anil",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {
                                    "column_name": "address1",
                                    "field_label": "Address",
                                },
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "scto_fields": None,
                    "supervisors": [],
                    "target_assignable": None,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 1,
                    "webapp_tag_color": None,
                }
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}
        assert checkdiff == {}

    def test_assignments_not_started_state(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Test the module status endpoint for testing the not started state

        """
        # Test the survey was inserted correctly
        response = client.get("/api/module-status/1")
        assert response.status_code == 200

        expected_response = {
            "data": [
                {"config_status": "Done", "module_id": 1, "survey_uid": 1},
                {"config_status": "Done", "module_id": 2, "survey_uid": 1},
                {
                    "config_status": "In Progress - Incomplete",
                    "module_id": 3,
                    "survey_uid": 1,
                },
                {"config_status": "Done", "module_id": 4, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 9, "survey_uid": 1},
                {"config_status": "Done", "module_id": 14, "survey_uid": 1},
                {
                    "config_status": "In Progress - Incomplete",
                    "module_id": 17,
                    "survey_uid": 1,
                },
                {"config_status": "Done", "module_id": 7, "survey_uid": 1},
                {"config_status": "Done", "module_id": 5, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 16, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 8, "survey_uid": 1},
            ],
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignments_in_progress_state(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Test the module status endpoint for testing the in progress state

        """
        # Test the survey was inserted correctly
        response = client.get("/api/module-status/1")
        assert response.status_code == 200

        expected_response = {
            "data": [
                {"config_status": "Done", "module_id": 1, "survey_uid": 1},
                {"config_status": "Done", "module_id": 2, "survey_uid": 1},
                {
                    "config_status": "In Progress - Incomplete",
                    "module_id": 3,
                    "survey_uid": 1,
                },
                {"config_status": "Done", "module_id": 4, "survey_uid": 1},
                {"config_status": "In Progress", "module_id": 9, "survey_uid": 1},
                {"config_status": "Done", "module_id": 14, "survey_uid": 1},
                {
                    "config_status": "In Progress",
                    "module_id": 17,
                    "survey_uid": 1,
                },
                {"config_status": "Done", "module_id": 7, "survey_uid": 1},
                {"config_status": "Done", "module_id": 5, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 16, "survey_uid": 1},
                {"config_status": "Done", "module_id": 8, "survey_uid": 1},
            ],
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignments_live_state(
        self,
        client,
        login_test_user,
        create_scto_question_mapping,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Test the module status endpoint for testing the live state

        """

        payload = {
            "survey_uid": 1,
            "state": "Active",
        }

        response = client.put(
            "/api/surveys/1/state",
            headers={"X-CSRF-Token": csrf_token},
            json=payload,
        )
        print(response.json)

        assert response.status_code == 200

        # Test the survey was inserted correctly
        response = client.get("/api/module-status/1")
        assert response.status_code == 200

        expected_response = {
            "data": [
                {"config_status": "Done", "module_id": 1, "survey_uid": 1},
                {"config_status": "Done", "module_id": 2, "survey_uid": 1},
                {"config_status": "Done", "module_id": 3, "survey_uid": 1},
                {"config_status": "Done", "module_id": 4, "survey_uid": 1},
                {"config_status": "Live", "module_id": 9, "survey_uid": 1},
                {"config_status": "Done", "module_id": 14, "survey_uid": 1},
                {
                    "config_status": "In Progress",
                    "module_id": 17,
                    "survey_uid": 1,
                },
                {"config_status": "Done", "module_id": 7, "survey_uid": 1},
                {"config_status": "Done", "module_id": 5, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 16, "survey_uid": 1},
                {"config_status": "Done", "module_id": 8, "survey_uid": 1},
            ],
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignments_table_config_in_progress_state(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        create_enumerator_column_config,
        create_target_column_config,
        csrf_token,
    ):
        """
        Test the module status endpoint for testing the in progress state

        """
        # Add the table config
        payload = {
            "form_uid": 1,
            "table_name": "assignments_main",
            "table_config": [
                {
                    "group_label": "Details",
                    "column_key": "assigned_enumerator_id",
                    "column_label": "Enumerator id",
                },
                {
                    "group_label": "Details",
                    "column_key": "assigned_enumerator_name",
                    "column_label": "Enumerator name",
                },
                {
                    "group_label": None,
                    "column_key": "custom_fields['Mobile no.']",
                    "column_label": "Target Mobile no.",
                },
                {
                    "group_label": None,
                    "column_key": "assigned_enumerator_custom_fields['Age']",
                    "column_label": "Enumerator Age",
                },
                {
                    "group_label": "Locations",
                    "column_key": "target_locations[0].location_name",
                    "column_label": "State",
                },
                {
                    "group_label": "Locations",
                    "column_key": "target_locations[1].location_name",
                    "column_label": "District",
                },
                {
                    "group_label": "Core User",
                    "column_key": "supervisors[2].supervisor_name",
                    "column_label": "Name",
                },
                {
                    "group_label": "Cluster Coordinator",
                    "column_key": "supervisors[1].supervisor_name",
                    "column_label": "Name",
                },
                {
                    "group_label": "Regional Coordinator",
                    "column_key": "supervisors[0].supervisor_name",
                    "column_label": "Name",
                },
            ],
        }

        response = client.put(
            "/api/assignments/table-config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        # Test the survey was inserted correctly
        response = client.get("/api/module-status/1")
        assert response.status_code == 200

        expected_response = {
            "data": [
                {"config_status": "Done", "module_id": 1, "survey_uid": 1},
                {"config_status": "Done", "module_id": 2, "survey_uid": 1},
                {
                    "config_status": "In Progress - Incomplete",
                    "module_id": 3,
                    "survey_uid": 1,
                },
                {"config_status": "Done", "module_id": 4, "survey_uid": 1},
                {"config_status": "In Progress", "module_id": 9, "survey_uid": 1},
                {"config_status": "Done", "module_id": 14, "survey_uid": 1},
                {
                    "config_status": "In Progress",
                    "module_id": 17,
                    "survey_uid": 1,
                },
                {"config_status": "Done", "module_id": 7, "survey_uid": 1},
                {"config_status": "Done", "module_id": 5, "survey_uid": 1},
                {"config_status": "In Progress", "module_id": 16, "survey_uid": 1},
                {"config_status": "Done", "module_id": 8, "survey_uid": 1},
            ],
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}
