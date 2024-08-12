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
    update_logged_in_user_roles,
)

from app import db


@pytest.mark.mapping
class TestMapping:
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
    def user_with_mapping_permissions(self, client, test_user_credentials, csrf_token):
        # Assign new roles and permissions

        # Give one existing role permissions to write mapping
        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                    "permissions": [9, 27],
                },
                {
                    "role_uid": 2,
                    "role_name": "Regional Coordinator",
                    "reporting_role_uid": 1,
                    "permissions": [9],
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
            ("user_with_mapping_permissions", True),
            ("user_with_no_permissions", False),
        ],
        ids=[
            "super_admin_permissions",
            "survey_admin_permissions",
            "mapping_permissions",
            "no_permissions",
        ],
    )
    def user_permissions(self, request):
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
    def create_form(
        self, client, login_test_user, csrf_token, create_module_questionnaire
    ):
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
    def create_roles(self, client, login_test_user, csrf_token, create_locations):
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
                    "role_name": "Regional Coordinator",
                    "reporting_role_uid": 1,
                    "permissions": [9],
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

        yield

    @pytest.fixture()
    def add_user(self, client, login_test_user, csrf_token, create_roles):
        """
        Add a user at survey level with role
        """

        response = client.post(
            "/api/users",
            json={
                "survey_uid": 1,
                "email": "newuser1@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "roles": [2],
                "gender": "Male",
                "languages": ["Hindi"],
                "locations": [1],
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

    @pytest.fixture()
    def add_another_user(self, client, login_test_user, csrf_token, create_roles):
        """
        Add a user at survey level with role
        """

        response = client.post(
            "/api/users",
            json={
                "survey_uid": 1,
                "email": "newuser2@example.com",
                "first_name": "Tim",
                "last_name": "Doe",
                "roles": [2],
                "gender": "Male",
                "languages": ["Telugu"],
                "locations": [1],
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

    @pytest.fixture()
    def update_user_mutliple_languages(
        self, client, login_test_user, csrf_token, create_roles
    ):
        """
        Update the user to have more than one language
        """

        response = client.put(
            "/api/users/3",
            json={
                "survey_uid": 1,
                "email": "newuser1@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "roles": [2],
                "gender": "Male",
                "languages": ["Hindi", "Telugu"],
                "locations": [1],
                "active": True,
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

    @pytest.fixture()
    def update_user_role(self, client, login_test_user, csrf_token, create_roles):
        """
        Update the user to have more than one language
        """

        response = client.put(
            "/api/users/3",
            json={
                "survey_uid": 1,
                "email": "newuser1@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "roles": [],
                "gender": "Male",
                "languages": [],
                "locations": [],
                "active": True,
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

    @pytest.fixture()
    def update_roles(
        self, client, login_test_user, csrf_token, create_roles, update_user_role
    ):
        """
        Update roles
        """

        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                    "permissions": [9],
                }
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

        payload = {"roles": []}

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
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
                },
                {
                    "column_name": "language",
                    "column_type": "basic_details",
                    "bulk_editable": True,
                    "contains_pii": True,
                },
                {
                    "column_name": "gender",
                    "column_type": "basic_details",
                    "bulk_editable": False,
                    "contains_pii": True,
                },
                {
                    "column_name": "Name",
                    "column_type": "custom_fields",
                    "bulk_editable": False,
                    "contains_pii": True,
                },
                {
                    "column_name": "Mobile no.",
                    "column_type": "custom_fields",
                    "bulk_editable": False,
                    "contains_pii": True,
                },
                {
                    "column_name": "Address",
                    "column_type": "custom_fields",
                    "bulk_editable": True,
                    "contains_pii": True,
                },
                {
                    "column_name": "bottom_geo_level_location",
                    "column_type": "location",
                    "bulk_editable": True,
                    "contains_pii": True,
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
                },
                {
                    "column_name": "language",
                    "column_type": "basic_details",
                    "bulk_editable": True,
                    "contains_pii": True,
                },
                {
                    "column_name": "gender",
                    "column_type": "basic_details",
                    "bulk_editable": False,
                    "contains_pii": True,
                },
                {
                    "column_name": "Name",
                    "column_type": "custom_fields",
                    "bulk_editable": False,
                    "contains_pii": True,
                },
                {
                    "column_name": "Mobile no.",
                    "column_type": "custom_fields",
                    "bulk_editable": False,
                    "contains_pii": True,
                },
                {
                    "column_name": "Address",
                    "column_type": "custom_fields",
                    "bulk_editable": True,
                    "contains_pii": True,
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
        self, client, login_test_user, create_locations, add_user, csrf_token
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
    def upload_targets_csv_no_locations(
        self, client, login_test_user, create_locations, csrf_token
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

        assert response.status_code == 200

    ####################################################
    ## FIXTURES END HERE
    ####################################################

    def update_target_mapping_criteria(self, client, csrf_token, mapping_criteria):
        # Update target_mapping_criteria to language
        payload = {
            "assignment_process": "Manual",
            "language_location_mapping": False,
            "reassignment_required": False,
            "target_mapping_criteria": mapping_criteria,
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

    def test_get_location_based_target_mapping(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        user_permissions,
        request,
    ):
        """
        Test getting the target mapping populated when uploading targets - Location based mapping
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/mapping/targets-mapping",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "gender": "Female",
                        "language": "Hindi",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": "newuser1@example.com",
                        "supervisor_mapping_criteria_values": {
                            "Location": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                        },
                        "supervisor_name": "John Doe",
                        "supervisor_uid": 3,
                        "target_id": "2",
                        "target_mapping_criteria_values": {
                            "Location": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                        },
                        "target_uid": 2,
                    },
                    {
                        "gender": "Male",
                        "language": "Telugu",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": "newuser1@example.com",
                        "supervisor_mapping_criteria_values": {
                            "Location": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                        },
                        "supervisor_name": "John Doe",
                        "supervisor_uid": 3,
                        "target_id": "1",
                        "target_mapping_criteria_values": {
                            "Location": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                        },
                        "target_uid": 1,
                    },
                ],
                "success": True,
            }

            print(response.json)
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Mapping",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_get_location_based_target_mapping_config(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        user_permissions,
        request,
    ):
        """
        Test fetching the mapping config for targets

        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/mapping/targets-mapping-config",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "mapping_status": "Complete",
                        "supervisor": {
                            "Location": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                        },
                        "supervisor_count": 1,
                        "target": {
                            "Location": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                        },
                        "target_count": 2,
                    }
                ],
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Mapping",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_get_language_based_target_mapping(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        user_permissions,
        request,
        csrf_token,
    ):
        """
        Test getting the target mapping populated when uploading targets
        """

        # Update target_mapping_criteria to language
        self.update_target_mapping_criteria(client, csrf_token, ["Language"])

        # Test mapping
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/mapping/targets-mapping",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "gender": "Female",
                        "language": "Hindi",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": "newuser1@example.com",
                        "supervisor_mapping_criteria_values": {
                            "Language": "Hindi",
                        },
                        "supervisor_name": "John Doe",
                        "supervisor_uid": 3,
                        "target_id": "2",
                        "target_mapping_criteria_values": {
                            "Language": "Hindi",
                        },
                        "target_uid": 2,
                    },
                    {
                        "gender": "Male",
                        "language": "Telugu",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": None,
                        "supervisor_mapping_criteria_values": {
                            "Language": "Telugu",
                        },
                        "supervisor_name": None,
                        "supervisor_uid": None,
                        "target_id": "1",
                        "target_mapping_criteria_values": {
                            "Language": "Telugu",
                        },
                        "target_uid": 1,
                    },
                ],
                "success": True,
            }

            print(response.json)
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Mapping",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_get_language_based_target_mapping_config(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        user_permissions,
        request,
        csrf_token,
    ):
        """
        Test fetching the mapping config for targets

        """
        # Update target_mapping_criteria to language
        self.update_target_mapping_criteria(client, csrf_token, ["Language"])

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/mapping/targets-mapping-config",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "mapping_status": "Complete",
                        "supervisor": {
                            "Language": "Hindi",
                        },
                        "supervisor_count": 1,
                        "target": {
                            "Language": "Hindi",
                        },
                        "target_count": 1,
                    },
                    {
                        "mapping_status": "Pending",
                        "supervisor": None,
                        "supervisor_count": None,
                        "target": {
                            "Language": "Telugu",
                        },
                        "target_count": 1,
                    },
                ],
                "success": True,
            }
            print(response.json)

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Mapping",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_put_target_mapping_config(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        user_permissions,
        request,
        csrf_token,
    ):
        """
        Test adding a custom mapping to the target mapping config
        """

        # Update target_mapping_criteria to language
        self.update_target_mapping_criteria(client, csrf_token, ["Language"])

        # Test mapping
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        # Add custom mapping config
        payload = {
            "form_uid": 1,
            "target_mapping_config": [
                {
                    "mapping_values": [
                        {
                            "criteria": "Language",
                            "value": "Telugu",
                        }
                    ],
                    "mapped_to": [
                        {
                            "criteria": "Language",
                            "value": "Hindi",
                        }
                    ],
                }
            ],
        }

        response = client.put(
            "/api/mapping/targets-mapping-config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            assert response.status_code == 200

            print(response.json)

            response = client.get(
                "/api/mapping/targets-mapping",
                query_string={"form_uid": 1},
                content_type="application/json",
            )

            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "gender": "Female",
                        "language": "Hindi",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": "newuser1@example.com",
                        "supervisor_mapping_criteria_values": {
                            "Language": "Hindi",
                        },
                        "supervisor_name": "John Doe",
                        "supervisor_uid": 3,
                        "target_id": "2",
                        "target_mapping_criteria_values": {
                            "Language": "Hindi",
                        },
                        "target_uid": 2,
                    },
                    {
                        "gender": "Male",
                        "language": "Telugu",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": "newuser1@example.com",
                        "supervisor_mapping_criteria_values": {
                            "Language": "Hindi",
                        },
                        "supervisor_name": "John Doe",
                        "supervisor_uid": 3,
                        "target_id": "1",
                        "target_mapping_criteria_values": {
                            "Language": "Telugu",
                        },
                        "target_uid": 1,
                    },
                ],
                "success": True,
            }

            print(response.json)
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            response = client.get(
                "/api/mapping/targets-mapping-config",
                query_string={"form_uid": 1},
                content_type="application/json",
            )

            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "mapping_status": "Complete",
                        "supervisor": {
                            "Language": "Hindi",
                        },
                        "supervisor_count": 1,
                        "target": {
                            "Language": "Hindi",
                        },
                        "target_count": 1,
                    },
                    {
                        "mapping_status": "Complete",
                        "supervisor": {
                            "Language": "Hindi",
                        },
                        "supervisor_count": 1,
                        "target": {
                            "Language": "Telugu",
                        },
                        "target_count": 1,
                    },
                ],
                "success": True,
            }
            print(response.json)

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: WRITE Mapping",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_delete_target_mapping_config(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        user_permissions,
        request,
        csrf_token,
    ):
        """
        Test deleting a custom mapping to the target mapping config reverts back to old mapping
        """

        # Update target_mapping_criteria to language
        self.update_target_mapping_criteria(client, csrf_token, ["Language"])

        # Test mapping
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.delete(
            "/api/mapping/targets-mapping-config",
            query_string={"form_uid": 1},
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            print(response.json)
            assert response.status_code == 200

            response = client.get(
                "/api/mapping/targets-mapping",
                query_string={"form_uid": 1},
                content_type="application/json",
            )

            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "gender": "Female",
                        "language": "Hindi",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": "newuser1@example.com",
                        "supervisor_mapping_criteria_values": {
                            "Language": "Hindi",
                        },
                        "supervisor_name": "John Doe",
                        "supervisor_uid": 3,
                        "target_id": "2",
                        "target_mapping_criteria_values": {
                            "Language": "Hindi",
                        },
                        "target_uid": 2,
                    },
                    {
                        "gender": "Male",
                        "language": "Telugu",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": None,
                        "supervisor_mapping_criteria_values": {
                            "Language": "Telugu",
                        },
                        "supervisor_name": None,
                        "supervisor_uid": None,
                        "target_id": "1",
                        "target_mapping_criteria_values": {
                            "Language": "Telugu",
                        },
                        "target_uid": 1,
                    },
                ],
                "success": True,
            }

            print(response.json)
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            response = client.get(
                "/api/mapping/targets-mapping-config",
                query_string={"form_uid": 1},
                content_type="application/json",
            )

            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "mapping_status": "Complete",
                        "supervisor": {
                            "Language": "Hindi",
                        },
                        "supervisor_count": 1,
                        "target": {
                            "Language": "Hindi",
                        },
                        "target_count": 1,
                    },
                    {
                        "mapping_status": "Pending",
                        "supervisor": None,
                        "supervisor_count": None,
                        "target": {
                            "Language": "Telugu",
                        },
                        "target_count": 1,
                    },
                ],
                "success": True,
            }
            print(response.json)

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: WRITE Mapping",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_get_gender_based_target_mapping(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        user_permissions,
        request,
        csrf_token,
    ):
        """
        Test getting the target mapping populated when uploading targets
        """

        # Update target_mapping_criteria to language
        self.update_target_mapping_criteria(client, csrf_token, ["Gender"])

        # Test mapping
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/mapping/targets-mapping",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "gender": "Female",
                        "language": "Hindi",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": None,
                        "supervisor_mapping_criteria_values": {
                            "Gender": "Female",
                        },
                        "supervisor_name": None,
                        "supervisor_uid": None,
                        "target_id": "2",
                        "target_mapping_criteria_values": {
                            "Gender": "Female",
                        },
                        "target_uid": 2,
                    },
                    {
                        "gender": "Male",
                        "language": "Telugu",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": "newuser1@example.com",
                        "supervisor_mapping_criteria_values": {
                            "Gender": "Male",
                        },
                        "supervisor_name": "John Doe",
                        "supervisor_uid": 3,
                        "target_id": "1",
                        "target_mapping_criteria_values": {
                            "Gender": "Male",
                        },
                        "target_uid": 1,
                    },
                ],
                "success": True,
            }

            print(response.json)
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Mapping",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_get_gender_based_target_mapping_multiple_supervisors(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        add_another_user,
        user_permissions,
        request,
        csrf_token,
    ):
        """
        Test getting the target mapping populated when uploading targets
        """

        # Update target_mapping_criteria to language
        self.update_target_mapping_criteria(client, csrf_token, ["Gender"])

        # Test mapping
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/mapping/targets-mapping",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "gender": "Female",
                        "language": "Hindi",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": None,
                        "supervisor_mapping_criteria_values": {
                            "Gender": "Female",
                        },
                        "supervisor_name": None,
                        "supervisor_uid": None,
                        "target_id": "2",
                        "target_mapping_criteria_values": {
                            "Gender": "Female",
                        },
                        "target_uid": 2,
                    },
                    {
                        "gender": "Male",
                        "language": "Telugu",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": None,
                        "supervisor_mapping_criteria_values": {
                            "Gender": "Male",
                        },
                        "supervisor_name": None,
                        "supervisor_uid": None,
                        "target_id": "1",
                        "target_mapping_criteria_values": {
                            "Gender": "Male",
                        },
                        "target_uid": 1,
                    },
                ],
                "success": True,
            }

            print(response.json)
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Mapping",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_get_gender_based_target_mapping_config_multiple_supervisors(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        add_another_user,
        user_permissions,
        request,
        csrf_token,
    ):
        """
        Test getting the target mapping populated when uploading targets
        """

        # Update target_mapping_criteria to language
        self.update_target_mapping_criteria(client, csrf_token, ["Gender"])

        # Test mapping
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/mapping/targets-mapping-config",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "mapping_status": "Pending",
                        "supervisor": None,
                        "supervisor_count": None,
                        "target": {
                            "Gender": "Female",
                        },
                        "target_count": 1,
                    },
                    {
                        "mapping_status": "Pending",
                        "supervisor": {
                            "Gender": "Male",
                        },
                        "supervisor_count": 2,
                        "target": {
                            "Gender": "Male",
                        },
                        "target_count": 1,
                    },
                ],
                "success": True,
            }

            print(response.json)
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Mapping",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_put_target_mapping(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        add_another_user,
        user_permissions,
        request,
        csrf_token,
    ):
        """
        Test adding mapping when there are multiple supervisors per mapping criteria
        """

        # Update target_mapping_criteria to language
        self.update_target_mapping_criteria(client, csrf_token, ["Gender"])

        # Test mapping
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        # Add mapping
        payload = {
            "form_uid": 1,
            "mappings": [
                {
                    "target_uid": 1,
                    "supervisor_uid": 3,
                }
            ],
        }
        response = client.put(
            "/api/mapping/targets-mapping",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            print(response.json)
            assert response.status_code == 200

            response = client.get(
                "/api/mapping/targets-mapping",
                query_string={"form_uid": 1},
                content_type="application/json",
            )

            expected_response = {
                "data": [
                    {
                        "gender": "Female",
                        "language": "Hindi",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": None,
                        "supervisor_mapping_criteria_values": {
                            "Gender": "Female",
                        },
                        "supervisor_name": None,
                        "supervisor_uid": None,
                        "target_id": "2",
                        "target_mapping_criteria_values": {
                            "Gender": "Female",
                        },
                        "target_uid": 2,
                    },
                    {
                        "gender": "Male",
                        "language": "Telugu",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": "newuser1@example.com",
                        "supervisor_mapping_criteria_values": {
                            "Gender": "Male",
                        },
                        "supervisor_name": "John Doe",
                        "supervisor_uid": 3,
                        "target_id": "1",
                        "target_mapping_criteria_values": {
                            "Gender": "Male",
                        },
                        "target_uid": 1,
                    },
                ],
                "success": True,
            }

            print(response.json)
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            response = client.get(
                "/api/mapping/targets-mapping-config",
                query_string={"form_uid": 1},
                content_type="application/json",
            )

            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "mapping_status": "Pending",
                        "supervisor": None,
                        "supervisor_count": None,
                        "target": {
                            "Gender": "Female",
                        },
                        "target_count": 1,
                    },
                    {
                        "mapping_status": "Complete",
                        "supervisor": {
                            "Gender": "Male",
                        },
                        "supervisor_count": 2,
                        "target": {
                            "Gender": "Male",
                        },
                        "target_count": 1,
                    },
                ],
                "success": True,
            }

            print(response.json)
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: WRITE Mapping",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_remove_invalid_mappings(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        user_permissions,
        request,
        csrf_token,
    ):
        """
        Test invalid mappings due to change in mapping criteria get removed

        """

        # Update target_mapping_criteria to language
        self.update_target_mapping_criteria(client, csrf_token, ["Language"])

        # Test mapping
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/mapping/targets-mapping",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "gender": "Female",
                        "language": "Hindi",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": "newuser1@example.com",
                        "supervisor_mapping_criteria_values": {
                            "Language": "Hindi",
                        },
                        "supervisor_name": "John Doe",
                        "supervisor_uid": 3,
                        "target_id": "2",
                        "target_mapping_criteria_values": {
                            "Language": "Hindi",
                        },
                        "target_uid": 2,
                    },
                    {
                        "gender": "Male",
                        "language": "Telugu",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": None,
                        "supervisor_mapping_criteria_values": {
                            "Language": "Telugu",
                        },
                        "supervisor_name": None,
                        "supervisor_uid": None,
                        "target_id": "1",
                        "target_mapping_criteria_values": {
                            "Language": "Telugu",
                        },
                        "target_uid": 1,
                    },
                ],
                "success": True,
            }

            print(response.json)
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Mapping",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_manual_target_mapping(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        user_permissions,
        request,
        csrf_token,
    ):
        """
        Test getting the target mapping populated when uploading targets with manual mapping criteria
        maps automatically when there is only one supervisor

        """

        # Update target_mapping_criteria to manual
        self.update_target_mapping_criteria(client, csrf_token, ["Manual"])

        # Test mapping
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/mapping/targets-mapping",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "gender": "Female",
                        "language": "Hindi",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": "newuser1@example.com",
                        "supervisor_mapping_criteria_values": {
                            "Manual": "manual",
                        },
                        "supervisor_name": "John Doe",
                        "supervisor_uid": 3,
                        "target_id": "2",
                        "target_mapping_criteria_values": {
                            "Manual": "manual",
                        },
                        "target_uid": 2,
                    },
                    {
                        "gender": "Male",
                        "language": "Telugu",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": "newuser1@example.com",
                        "supervisor_mapping_criteria_values": {
                            "Manual": "manual",
                        },
                        "supervisor_name": "John Doe",
                        "supervisor_uid": 3,
                        "target_id": "1",
                        "target_mapping_criteria_values": {
                            "Manual": "manual",
                        },
                        "target_uid": 1,
                    },
                ],
                "success": True,
            }

            print(response.json)
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Mapping",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_manual_target_mapping_multiple_supervisors(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        add_another_user,
        user_permissions,
        request,
        csrf_token,
    ):
        """
        Test getting the target mapping populated when uploading targets with manual mapping criteria
        doesn't do mapping if there are more than one supervisor

        """

        # Update target_mapping_criteria to manual
        self.update_target_mapping_criteria(client, csrf_token, ["Manual"])

        # Test mapping
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/mapping/targets-mapping",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "gender": "Female",
                        "language": "Hindi",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": None,
                        "supervisor_mapping_criteria_values": {
                            "Manual": "manual",
                        },
                        "supervisor_name": None,
                        "supervisor_uid": None,
                        "target_id": "2",
                        "target_mapping_criteria_values": {
                            "Manual": "manual",
                        },
                        "target_uid": 2,
                    },
                    {
                        "gender": "Male",
                        "language": "Telugu",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": None,
                        "supervisor_mapping_criteria_values": {
                            "Manual": "manual",
                        },
                        "supervisor_name": None,
                        "supervisor_uid": None,
                        "target_id": "1",
                        "target_mapping_criteria_values": {
                            "Manual": "manual",
                        },
                        "target_uid": 1,
                    },
                ],
                "success": True,
            }

            print(response.json)
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Mapping",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_language_and_location_based_target_mapping_multiple_supervisors(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        add_another_user,
        user_permissions,
        request,
        csrf_token,
    ):
        """
        Test getting the target mapping populated when uploading targets with language and location mapping criteria
        """

        # Update target_mapping_criteria to manual
        self.update_target_mapping_criteria(
            client, csrf_token, ["Language", "Location"]
        )

        # Test mapping
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/mapping/targets-mapping",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "gender": "Female",
                        "language": "Hindi",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": "newuser1@example.com",
                        "supervisor_mapping_criteria_values": {
                            "Language": "Hindi",
                            "Location": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                        },
                        "supervisor_name": "John Doe",
                        "supervisor_uid": 3,
                        "target_id": "2",
                        "target_mapping_criteria_values": {
                            "Language": "Hindi",
                            "Location": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                        },
                        "target_uid": 2,
                    },
                    {
                        "gender": "Male",
                        "language": "Telugu",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": "newuser2@example.com",
                        "supervisor_mapping_criteria_values": {
                            "Language": "Telugu",
                            "Location": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                        },
                        "supervisor_name": "Tim Doe",
                        "supervisor_uid": 4,
                        "target_id": "1",
                        "target_mapping_criteria_values": {
                            "Language": "Telugu",
                            "Location": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                        },
                        "target_uid": 1,
                    },
                ],
                "success": True,
            }

            print(response.json)
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Mapping",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_mapping_with_user_with_multiple_languages(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        update_user_mutliple_languages,
        user_permissions,
        request,
        csrf_token,
    ):
        """
        Test getting the target mapping populated when uploading targets
        """

        # Update target_mapping_criteria to language
        self.update_target_mapping_criteria(client, csrf_token, ["Language"])

        # Test mapping
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/mapping/targets-mapping",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "gender": "Female",
                        "language": "Hindi",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": "newuser1@example.com",
                        "supervisor_mapping_criteria_values": {
                            "Language": "Hindi",
                        },
                        "supervisor_name": "John Doe",
                        "supervisor_uid": 3,
                        "target_id": "2",
                        "target_mapping_criteria_values": {
                            "Language": "Hindi",
                        },
                        "target_uid": 2,
                    },
                    {
                        "gender": "Male",
                        "language": "Telugu",
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "supervisor_email": "newuser1@example.com",
                        "supervisor_mapping_criteria_values": {
                            "Language": "Telugu",
                        },
                        "supervisor_name": "John Doe",
                        "supervisor_uid": 3,
                        "target_id": "1",
                        "target_mapping_criteria_values": {
                            "Language": "Telugu",
                        },
                        "target_uid": 1,
                    },
                ],
                "success": True,
            }

            print(response.json)
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Mapping",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_mapping_with_no_mapping_criteria(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        csrf_token,
    ):
        """
        Test getting the target mapping when mapping criteria is not set
        """

        # Update target_mapping_criteria to blank
        self.update_target_mapping_criteria(client, csrf_token, None)

        response = client.get(
            "/api/mapping/targets-mapping",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        print(response.json)
        assert response.status_code == 422
        expected_response = {
            "errors": {
                "mapping_errors": "Supervisor to target mapping criteria not found."
            },
            "success": False,
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_mapping_with_no_roles(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        update_roles,
        csrf_token,
    ):
        """
        Test getting the target mapping when roles are not set

        """

        response = client.get(
            "/api/mapping/targets-mapping",
            query_string={"form_uid": 1},
            content_type="application/json",
        )
        assert response.status_code == 422
        expected_response = {
            "errors": {
                "mapping_errors": "Roles not configured for the survey. Cannot perform supervisor to target mapping without roles."
            },
            "success": False,
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_location_mapping_with_no_prime_geo_level(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        update_roles,
        csrf_token,
    ):
        """
        Test getting the target mapping when roles are not set

        """
        # Remove prime geo level
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
            "config_status": "In Progress - Configuration",
        }

        response = client.put(
            "/api/surveys/1/basic-information",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        response = client.get(
            "/api/mapping/targets-mapping",
            query_string={"form_uid": 1},
            content_type="application/json",
        )
        assert response.status_code == 422
        expected_response = {
            "errors": {
                "mapping_errors": "Prime geo level not configured for the survey. Cannot perform supervisor to target mapping based on location without a prime geo level."
            },
            "success": False,
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_target_mapping_paginate(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        request,
    ):
        """
        Test getting the target mapping with pagination
        """
        response = client.get(
            "/api/mapping/targets-mapping",
            query_string={"form_uid": 1, "page": 1, "per_page": 1},
            content_type="application/json",
        )

        assert response.status_code == 200
        expected_response = {
            "data": [
                {
                    "gender": "Male",
                    "language": "Telugu",
                    "location_id": "1",
                    "location_name": "ADILABAD",
                    "supervisor_email": "newuser1@example.com",
                    "supervisor_mapping_criteria_values": {
                        "Location": 1,
                        "location_id": "1",
                        "location_name": "ADILABAD",
                    },
                    "supervisor_name": "John Doe",
                    "supervisor_uid": 3,
                    "target_id": "1",
                    "target_mapping_criteria_values": {
                        "Location": 1,
                        "location_id": "1",
                        "location_name": "ADILABAD",
                    },
                    "target_uid": 1,
                }
            ],
            "success": True,
            "pagination": {"count": 2, "page": 1, "pages": 2, "per_page": 1},
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}
