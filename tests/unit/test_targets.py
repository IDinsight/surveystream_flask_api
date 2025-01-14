import base64
from pathlib import Path

import jsondiff
import pandas as pd
import pytest
from utils import (
    create_new_survey_role_with_permissions,
    login_user,
    update_logged_in_user_roles,
)


@pytest.mark.targets
class TestTargets:
    # RBAC fixtures
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
    def user_with_target_permissions(self, client, test_user_credentials):
        # Assign new roles and permissions
        new_role = create_new_survey_role_with_permissions(
            # 7 - WRITE Targets
            client,
            test_user_credentials,
            "Targets Role",
            [7],
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
            ("user_with_target_permissions", True),
            ("user_with_no_permissions", False),
        ],
        ids=[
            "super_admin_permissions",
            "survey_admin_permissions",
            "target_permissions",
            "no_permissions",
        ],
    )
    def user_permissions(self, request):
        return request.param

    @pytest.fixture()
    def create_survey(self, client, login_test_user, csrf_token, test_user_credentials):
        """
        Insert new survey as a setup step for the survey tests
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
        print(response.json)
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_form(
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

    @pytest.fixture()
    def create_geo_levels_for_targets_file(
        self, client, login_test_user, csrf_token, create_form
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
        print(response.json)

        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_locations_for_targets_file(
        self,
        client,
        login_test_user,
        create_geo_levels_for_targets_file,
        csrf_token,
    ):
        """
        Upload locations csv as a setup step for the targets upload tests
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
    def create_locations_for_dynamic_targets(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
    ):
        """
        Upload locations csv as a setup step for the targets upload tests
        """

        payload = {
            "geo_levels": [
                {
                    "geo_level_uid": None,
                    "geo_level_name": "State",
                    "parent_geo_level_uid": None,
                },
                {
                    "geo_level_uid": None,
                    "geo_level_name": "District",
                    "parent_geo_level_uid": 1,
                },
                {
                    "geo_level_uid": None,
                    "geo_level_name": "Block",
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

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_locations_dynamic_targets.csv"
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
                    "location_name_column": "state_name",
                    "location_id_column": "state_id",
                },
                {
                    "geo_level_uid": 2,
                    "location_name_column": "district_name",
                    "location_id_column": "district_id",
                },
                {
                    "geo_level_uid": 3,
                    "location_name_column": "block_name",
                    "location_id_column": "block_id",
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
        print(response.json)
        assert response.status_code == 200

        df = pd.read_csv(filepath, dtype=str)
        df.rename(
            columns={
                "state_id": "State ID",
                "state_name": "State Name",
                "district_id": "District ID",
                "district_name": "District Name",
                "block_id": "Block ID",
                "block_name": "Block Name",
            },
            inplace=True,
        )

        expected_response = {
            "data": {
                "ordered_columns": [
                    "State ID",
                    "State Name",
                    "District ID",
                    "District Name",
                    "Block ID",
                    "Block Name",
                ],
                "records": df.to_dict(orient="records"),
            },
            "success": True,
        }
        # Check the response
        response = client.get("/api/locations", query_string={"survey_uid": 1})

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        yield

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
    def upload_targets_csv(
        self, client, login_test_user, create_locations_for_targets_file, csrf_token
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
    def upload_target_status(
        self, client, login_test_user, upload_targets_csv, csrf_token
    ):
        """
        Insert new target status as a setup step for the target status tests
        """

        payload = {
            "form_uid": 1,
            "target_status": [
                {
                    "target_id": "1",
                    "completed_flag": False,
                    "refusal_flag": False,
                    "num_attempts": 1,
                    "last_attempt_survey_status": 2,
                    "last_attempt_survey_status_label": "Partially complete - revisit",
                    "final_survey_status": 2,
                    "final_survey_status_label": "Partially complete - revisit",
                    "target_assignable": True,
                    "webapp_tag_color": "gold",
                    "revisit_sections": ["section1", "section2"],
                    "scto_fields": {"field1": "value1", "field2": "value2"},
                },
                {
                    "target_id": "2",
                    "completed_flag": True,
                    "refusal_flag": False,
                    "num_attempts": 5,
                    "last_attempt_survey_status": 1,
                    "last_attempt_survey_status_label": "Fully complete",
                    "final_survey_status": 1,
                    "final_survey_status_label": "Fully complete",
                    "target_assignable": False,
                    "webapp_tag_color": "green",
                    "revisit_sections": [],
                    "scto_fields": {"field1": "value3", "field2": "value4"},
                },
            ],
        }

        response = client.put(
            "/api/targets/target-status",
            query_string={"form_uid": 1},
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
        create_locations_for_targets_file,
        update_target_mapping_criteria_to_language,
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

        assert response.status_code == 200

    @pytest.fixture()
    def upload_targets_csv_no_custom_fields(
        self, client, login_test_user, create_locations_for_targets_file, csrf_token
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

    @pytest.fixture()
    def update_target_mapping_criteria_to_language(
        self, login_test_user, client, csrf_token, create_survey
    ):
        """
        Method to update the mapping criteria to Langauge
        """

        # Update target_mapping_criteria to gender
        payload = {
            "assignment_process": "Manual",
            "language_location_mapping": False,
            "reassignment_required": False,
            "target_mapping_criteria": ["Language"],
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
        print(response.json)
        assert response.status_code == 200

    @pytest.fixture()
    def update_target_mapping_criteria_to_gender(self, client, csrf_token):
        """
        Method to update the mapping criteria to Gender
        """

        # Update target_mapping_criteria to gender
        payload = {
            "assignment_process": "Manual",
            "language_location_mapping": False,
            "reassignment_required": False,
            "target_mapping_criteria": ["Gender"],
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

    @pytest.fixture()
    def update_target_mapping_criteria_to_none(self, client, csrf_token):
        """
        Method to update the mapping criteria to none
        """

        # Update target_mapping_criteria to None
        payload = {
            "assignment_process": "Manual",
            "language_location_mapping": False,
            "reassignment_required": False,
            "target_mapping_criteria": None,
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

    @pytest.fixture()
    def create_target_config(self, client, csrf_token, login_test_user, create_form):
        """
        Load target config table for tests with form inputs
        """

        payload = {
            "form_uid": 1,
            "target_source": "scto",
            "scto_input_type": "form",
            "scto_input_id": "test_scto_input_output",
            "scto_encryption_flag": False,
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
    def create_target_config_for_dynamic_targets(
        self, client, csrf_token, login_test_user, create_form
    ):
        """
        Load target config table for tests with form inputs
        """

        payload = {
            "form_uid": 1,
            "target_source": "scto",
            "scto_input_type": "form",
            "scto_input_id": "test_scto_input_output",
            "scto_encryption_flag": False,
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
    def create_dynamic_target_column_config_with_filter(
        self,
        client,
        csrf_token,
        create_target_config_for_dynamic_targets,
        create_locations_for_dynamic_targets,
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
                    "column_source": "enum_id",
                },
                {
                    "column_name": "language",
                    "column_type": "basic_details",
                    "bulk_editable": True,
                    "contains_pii": True,
                    "column_source": "designation",
                },
                {
                    "column_name": "gender",
                    "column_type": "basic_details",
                    "bulk_editable": False,
                    "contains_pii": True,
                    "column_source": "dc_type",
                },
                {
                    "column_name": "Name",
                    "column_type": "custom_fields",
                    "bulk_editable": False,
                    "contains_pii": True,
                    "column_source": "enum_name",
                },
                {
                    "column_name": "bottom_geo_level_location",
                    "column_type": "location",
                    "bulk_editable": True,
                    "contains_pii": True,
                    "column_source": "block_id",
                },
            ],
            "filters": [
                {
                    "filter_group": [
                        {
                            "variable_name": "state_id",
                            "filter_operator": "Is",
                            "filter_value": "21",
                        }
                    ]
                }
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

    def test_load_dynamic_targets_from_scto(
        self,
        client,
        user_permissions,
        request,
        create_locations_for_dynamic_targets,
        update_target_mapping_criteria_to_language,
        create_target_config_for_dynamic_targets,
        csrf_token,
    ):
        """
        Test load dynamic targets from SCTO
        Expect Successfull with targets db updated
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "column_mapping": {
                "target_id": "enum_id",
                "gender": "designation",
                "language": "dc_type",
                "location_id_column": "block_id",
                "custom_fields": [
                    {
                        "field_label": "enum_name",
                        "column_name": "enum_name",
                    },
                ],
            },
            "file": " ",
            "mode": "overwrite",
            "load_from_scto": True,
        }

        response = client.post(
            "/api/targets",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        if expected_permission:
            assert response.status_code == 200
            get_targets_response = client.get(
                "/api/targets", query_string={"form_uid": 1}
            )
            expected_response = {
                "success": True,
                "data": [
                    {
                        "target_uid": 1,
                        "target_id": "6ce2457eec",
                        "language": "CHC_CHANDRAPUR",
                        "gender": "Cluster Coordinator",
                        "location_uid": 6,
                        "form_uid": 1,
                        "custom_fields": {
                            "enum_name": "Amit kumar padhi",
                            "column_mapping": {
                                "gender": "designation",
                                "language": "dc_type",
                                "target_id": "enum_id",
                                "custom_fields": [
                                    {
                                        "column_name": "enum_name",
                                        "field_label": "enum_name",
                                    }
                                ],
                                "location_id_column": "block_id",
                            },
                        },
                        "completed_flag": None,
                        "refusal_flag": None,
                        "num_attempts": None,
                        "last_attempt_survey_status": None,
                        "last_attempt_survey_status_label": None,
                        "final_survey_status": None,
                        "final_survey_status_label": None,
                        "target_assignable": None,
                        "webapp_tag_color": None,
                        "revisit_sections": None,
                        "scto_fields": None,
                        "target_locations": [
                            {
                                "location_id": "21",
                                "location_uid": 1,
                                "geo_level_uid": 1,
                                "location_name": "Odisha",
                                "geo_level_name": "State",
                            },
                            {
                                "location_id": "396",
                                "location_uid": 3,
                                "geo_level_uid": 2,
                                "location_name": "Rayagada",
                                "geo_level_name": "District",
                            },
                            {
                                "location_id": "2",
                                "location_uid": 6,
                                "geo_level_uid": 3,
                                "location_name": "Indira Nagar",
                                "geo_level_name": "Block",
                            },
                        ],
                    },
                    {
                        "target_uid": 2,
                        "target_id": "df950a3da8",
                        "language": "CHC_CHANDRAPUR",
                        "gender": "Regional Coordinator",
                        "location_uid": 6,
                        "form_uid": 1,
                        "custom_fields": {
                            "enum_name": "BABULA GARADIA",
                            "column_mapping": {
                                "gender": "designation",
                                "language": "dc_type",
                                "target_id": "enum_id",
                                "custom_fields": [
                                    {
                                        "column_name": "enum_name",
                                        "field_label": "enum_name",
                                    }
                                ],
                                "location_id_column": "block_id",
                            },
                        },
                        "completed_flag": None,
                        "refusal_flag": None,
                        "num_attempts": None,
                        "last_attempt_survey_status": None,
                        "last_attempt_survey_status_label": None,
                        "final_survey_status": None,
                        "final_survey_status_label": None,
                        "target_assignable": None,
                        "webapp_tag_color": None,
                        "revisit_sections": None,
                        "scto_fields": None,
                        "target_locations": [
                            {
                                "location_id": "21",
                                "location_uid": 1,
                                "geo_level_uid": 1,
                                "location_name": "Odisha",
                                "geo_level_name": "State",
                            },
                            {
                                "location_id": "396",
                                "location_uid": 3,
                                "geo_level_uid": 2,
                                "location_name": "Rayagada",
                                "geo_level_name": "District",
                            },
                            {
                                "location_id": "2",
                                "location_uid": 6,
                                "geo_level_uid": 3,
                                "location_name": "Indira Nagar",
                                "geo_level_name": "Block",
                            },
                        ],
                    },
                    {
                        "target_uid": 3,
                        "target_id": "89732bda71",
                        "language": "PHC_CHARDANA",
                        "gender": "Monitor",
                        "location_uid": 6,
                        "form_uid": 1,
                        "custom_fields": {
                            "enum_name": "Aman Kaur",
                            "column_mapping": {
                                "gender": "designation",
                                "language": "dc_type",
                                "target_id": "enum_id",
                                "custom_fields": [
                                    {
                                        "column_name": "enum_name",
                                        "field_label": "enum_name",
                                    }
                                ],
                                "location_id_column": "block_id",
                            },
                        },
                        "completed_flag": None,
                        "refusal_flag": None,
                        "num_attempts": None,
                        "last_attempt_survey_status": None,
                        "last_attempt_survey_status_label": None,
                        "final_survey_status": None,
                        "final_survey_status_label": None,
                        "target_assignable": None,
                        "webapp_tag_color": None,
                        "revisit_sections": None,
                        "scto_fields": None,
                        "target_locations": [
                            {
                                "location_id": "21",
                                "location_uid": 1,
                                "geo_level_uid": 1,
                                "location_name": "Odisha",
                                "geo_level_name": "State",
                            },
                            {
                                "location_id": "396",
                                "location_uid": 3,
                                "geo_level_uid": 2,
                                "location_name": "Rayagada",
                                "geo_level_name": "District",
                            },
                            {
                                "location_id": "2",
                                "location_uid": 6,
                                "geo_level_uid": 3,
                                "location_name": "Indira Nagar",
                                "geo_level_name": "Block",
                            },
                        ],
                    },
                ],
            }
            assert get_targets_response.status_code == 200
            assert get_targets_response.json == expected_response

            # Check if the targets loaded time is updated in the database
            get_target_config = client.get(
                "/api/targets/config", query_string={"form_uid": 1}
            )
            print(get_target_config.json)
            assert get_target_config.status_code == 200
            assert get_target_config.json["data"]["targets_last_uploaded"] is not None
        else:
            assert response.status_code == 403

    def test_load_dynamic_targets_from_scto_with_filters(
        self,
        client,
        user_permissions,
        request,
        create_dynamic_target_column_config_with_filter,
        update_target_mapping_criteria_to_language,
        csrf_token,
    ):
        """
        Test load dynamic targets from SCTO
        Expect Successfull with targets db updated
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "column_mapping": {
                "target_id": "enum_id",
                "gender": "designation",
                "language": "dc_type",
                "location_id_column": "block_id",
                "custom_fields": [
                    {
                        "field_label": "enum_name",
                        "column_name": "enum_name",
                    },
                ],
            },
            "filters": [
                {
                    "filter_group": [
                        {
                            "variable_name": "state_id",
                            "filter_operator": "Is",
                            "filter_value": "21",
                        }
                    ]
                }
            ],
            "file": " ",
            "mode": "overwrite",
            "load_from_scto": True,
        }

        response = client.post(
            "/api/targets",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        if expected_permission:
            assert response.status_code == 200
            get_targets_response = client.get(
                "/api/targets", query_string={"form_uid": 1}
            )
            print(get_targets_response.json)
            expected_response = {
                "success": True,
                "data": [
                    {
                        "target_uid": 1,
                        "target_id": "6ce2457eec",
                        "language": "CHC_CHANDRAPUR",
                        "gender": "Cluster Coordinator",
                        "location_uid": 6,
                        "form_uid": 1,
                        "custom_fields": {
                            "enum_name": "Amit kumar padhi",
                            "column_mapping": {
                                "gender": "designation",
                                "language": "dc_type",
                                "target_id": "enum_id",
                                "custom_fields": [
                                    {
                                        "column_name": "enum_name",
                                        "field_label": "enum_name",
                                    }
                                ],
                                "location_id_column": "block_id",
                            },
                        },
                        "completed_flag": None,
                        "refusal_flag": None,
                        "num_attempts": None,
                        "last_attempt_survey_status": None,
                        "last_attempt_survey_status_label": None,
                        "final_survey_status": None,
                        "final_survey_status_label": None,
                        "target_assignable": None,
                        "webapp_tag_color": None,
                        "revisit_sections": None,
                        "scto_fields": None,
                        "target_locations": [
                            {
                                "location_id": "21",
                                "location_uid": 1,
                                "geo_level_uid": 1,
                                "location_name": "Odisha",
                                "geo_level_name": "State",
                            },
                            {
                                "location_id": "396",
                                "location_uid": 3,
                                "geo_level_uid": 2,
                                "location_name": "Rayagada",
                                "geo_level_name": "District",
                            },
                            {
                                "location_id": "2",
                                "location_uid": 6,
                                "geo_level_uid": 3,
                                "location_name": "Indira Nagar",
                                "geo_level_name": "Block",
                            },
                        ],
                    },
                    {
                        "target_uid": 2,
                        "target_id": "df950a3da8",
                        "language": "CHC_CHANDRAPUR",
                        "gender": "Regional Coordinator",
                        "location_uid": 6,
                        "form_uid": 1,
                        "custom_fields": {
                            "enum_name": "BABULA GARADIA",
                            "column_mapping": {
                                "gender": "designation",
                                "language": "dc_type",
                                "target_id": "enum_id",
                                "custom_fields": [
                                    {
                                        "column_name": "enum_name",
                                        "field_label": "enum_name",
                                    }
                                ],
                                "location_id_column": "block_id",
                            },
                        },
                        "completed_flag": None,
                        "refusal_flag": None,
                        "num_attempts": None,
                        "last_attempt_survey_status": None,
                        "last_attempt_survey_status_label": None,
                        "final_survey_status": None,
                        "final_survey_status_label": None,
                        "target_assignable": None,
                        "webapp_tag_color": None,
                        "revisit_sections": None,
                        "scto_fields": None,
                        "target_locations": [
                            {
                                "location_id": "21",
                                "location_uid": 1,
                                "geo_level_uid": 1,
                                "location_name": "Odisha",
                                "geo_level_name": "State",
                            },
                            {
                                "location_id": "396",
                                "location_uid": 3,
                                "geo_level_uid": 2,
                                "location_name": "Rayagada",
                                "geo_level_name": "District",
                            },
                            {
                                "location_id": "2",
                                "location_uid": 6,
                                "geo_level_uid": 3,
                                "location_name": "Indira Nagar",
                                "geo_level_name": "Block",
                            },
                        ],
                    },
                ],
            }
            assert get_targets_response.status_code == 200
            assert get_targets_response.json == expected_response

        else:
            assert response.status_code == 403

    @pytest.fixture()
    def create_target_config_dataset(
        self, client, csrf_token, login_test_user, create_form
    ):
        """
        Load target config table for test with dataset inputs
        """

        payload = {
            "form_uid": 1,
            "target_source": "scto",
            "scto_input_type": "dataset",
            "scto_input_id": "test_attached_dataset",
            "scto_encryption_flag": False,
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
    def create_target_scto_column(
        self, client, csrf_token, login_test_user, create_target_config
    ):
        """
        Refresh Target SCTO Columns for form input
        """
        response = client.put(
            "/api/targets/config/scto-columns?form_uid=1",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

    @pytest.fixture()
    def create_target_scto_column_with_dataset(
        self, client, csrf_token, login_test_user, create_target_config_dataset
    ):
        """
        Refresh Target scto column for dataset input
        """
        response = client.put(
            "/api/targets/config/scto-columns?form_uid=1",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

    def test_get_target_scto_columns_with_dataset(
        self,
        client,
        csrf_token,
        create_target_scto_column_with_dataset,
        user_permissions,
        request,
    ):
        """
        Test get target scto columns

        Expect: Success with column list for surveycto dataset

        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/targets/config/scto-columns?form_uid=1",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.status_code)
        print(response.json)
        if expected_permission:
            assert response.status_code == 200
            expected_response = {"data": ["col1", "col2", "col3"], "success": True}
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            assert response.status_code == 403
            assert response.json == {
                "error": "User does not have the required permission: WRITE Targets",
                "success": False,
            }

    def test_get_target_scto_columns(
        self, client, csrf_token, create_target_scto_column, user_permissions, request
    ):
        """
        Test get target scto columns for form input

        Expect: Success with input column list for surveycto form
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/targets/config/scto-columns?form_uid=1",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.status_code)
        print(response.json)
        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": [
                    "starttime",
                    "endtime",
                    "deviceid",
                    "subscriberid",
                    "simid",
                    "devicephonenum",
                    "username",
                    "duration",
                    "caseid",
                    "text_audit",
                    "round_id",
                    "month",
                    "monitor_info",
                    "state_id",
                    "state_name",
                    "district_id",
                    "district_name",
                    "block_id",
                    "block_name",
                    "initial_id",
                    "enum_first_letter",
                    "enum_id",
                    "enum_name",
                    "designation_id",
                    "designation",
                    "monitor_id",
                    "monitor_name",
                    "monitor_info",
                    "dc_id",
                    "dc_id_long",
                    "dc_type",
                    "sc_dc_found",
                    "sc_dc_found_group",
                    "sc_dc_open",
                    "sc_dc_open_group",
                    "sc_intro",
                    "sc_paperscarry",
                    "sc_dc_form_access",
                    "sc_dc_form_access_group",
                    "sc_dc_fac_id",
                    "sc_dc_fac_id_long",
                    "sc_dc_facility_name",
                    "sc_dc_form_avail",
                    "sc_dc_form_month_conf",
                    "sc_dc_data_entry_group",
                    "fac_anc_reg_1_trim",
                    "fac_4anc",
                    "fac_4hb",
                    "fac_sev_anem_treat",
                    "fac_sba_birth",
                    "fac_insti_birth",
                    "fac_live_birth_m",
                    "fac_live_birth_uw",
                    "fac_bfeeding_1hr",
                    "fac_full_immu_f",
                    "sc_dc_fac_dataentry",
                    "sc_dc_fac_photo_consent",
                    "sc_dc_fac_photo_num",
                    "sc_dc_data_entry_group",
                    "sc_dc_form_access_group",
                    "sc_dc_open_group",
                    "sc_dc_found_group",
                    "sc_note1",
                    "sc_protocol_rate",
                    "sc_probing_rate",
                    "sc_comfort_rate",
                    "sc_speed_rate",
                    "sc_note2",
                    "sc_final_score",
                    "monitor_comments",
                    "sc_thankyou_note",
                    "instanceID",
                    "formdef_version",
                    "SubmissionDate",
                ],
                "success": True,
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            assert response.status_code == 403
            assert response.json == {
                "error": "User does not have the required permission: WRITE Targets",
                "success": False,
            }

    def test_get_target_scto_columns_exception(
        self, client, csrf_token, create_target_config, user_permissions, request
    ):
        """
        Test Get target scto columns when no target scto columns present in db

        Expect: Error 404: SurveyCTO columns not found for the form
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/targets/config/scto-columns?form_uid=1",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.status_code)
        print(response.json)
        if expected_permission:
            assert response.status_code == 404
            expected_response = {
                "success": False,
                "data": None,
                "message": "SurveyCTO columns not found for the form",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            assert response.status_code == 403
            assert response.json == {
                "error": "User does not have the required permission: WRITE Targets",
                "success": False,
            }

    def test_update_target_scto_columns(
        self, client, csrf_token, create_target_config, user_permissions, request
    ):
        """
        Test Update target scto columns
        Expect Success
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.put(
            "/api/targets/config/scto-columns?form_uid=1",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.status_code)
        print(response.json)
        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "message": "SurveyCTO input columns refreshed successfully",
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403
            assert response.json == {
                "error": "User does not have the required permission: WRITE Targets",
                "success": False,
            }

    def test_update_target_scto_columns_exception_no_target_config_present(
        self, client, csrf_token, create_form, user_permissions, request
    ):
        """
        Test Update target scto columns when no target config present for the form
        Expect Error 404: Target configuration not found for the form


        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.put(
            "/api/targets/config/scto-columns?form_uid=1",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.status_code)
        print(response.json)
        if expected_permission:
            assert response.status_code == 404
            expected_response = {
                "error": "Target configuration not found for the form.",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403
            assert response.json == {
                "error": "User does not have the required permission: WRITE Targets",
                "success": False,
            }

    def test_update_target_scto_columns_exception_no_scto_server_present(
        self, client, csrf_token, create_form, user_permissions, request
    ):
        """
        Test Update target scto columns when no scto server name present for the form
        Expect Error 404: SurveyCTO server name not provided for the form
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)
        payload = {
            "survey_uid": 1,
            "scto_form_id": "test_scto_input_output",
            "form_name": "Agrifieldnet Main Form",
            "tz_name": "Asia/Kolkata",
            "scto_server_name": None,
            "encryption_key_shared": True,
            "server_access_role_granted": True,
            "server_access_allowed": True,
            "form_type": "parent",
            "parent_form_uid": None,
            "dq_form_type": None,
        }

        response = client.put(
            "/api/forms/1",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            assert response.status_code == 200

            response = client.put(
                "/api/targets/config/scto-columns?form_uid=1",
                headers={"X-CSRF-Token": csrf_token},
            )
            print(response.status_code)
            print(response.json)
            assert response.status_code == 404
            expected_response = {
                "error": "SurveyCTO server name not provided for the form",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403
            assert response.json == {
                "error": "User does not have the required permission: WRITE Data Quality Forms, WRITE Admin Forms",
                "success": False,
            }

    def test_update_target_scto_columns_exception_no_scto_credentials_present(
        self, client, csrf_token, create_target_config, user_permissions, request
    ):
        """
        Test Update target scto columns when no scto credentials present for the server
        Expect Error 500: ResourceNotFoundException
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)
        payload = {
            "survey_uid": 1,
            "scto_form_id": "test_scto_input_output",
            "form_name": "Agrifieldnet Main Form",
            "tz_name": "Asia/Kolkata",
            "scto_server_name": "random_scto_server",
            "encryption_key_shared": True,
            "server_access_role_granted": True,
            "server_access_allowed": True,
            "form_type": "parent",
            "parent_form_uid": None,
            "dq_form_type": None,
        }

        response = client.put(
            "/api/forms/1",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            assert response.status_code == 200

            response = client.put(
                "/api/targets/config/scto-columns?form_uid=1",
                headers={"X-CSRF-Token": csrf_token},
            )
            print(response.status_code)
            print(response.json)

            assert response.status_code == 500
            expected_response = {
                "error": "An error occurred (ResourceNotFoundException) when calling the GetSecretValue operation: Secrets Manager can't find the specified secret."
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403
            assert response.json == {
                "error": "User does not have the required permission: WRITE Data Quality Forms, WRITE Admin Forms",
                "success": False,
            }

    def test_create_target_column_config_with_filter(
        self,
        client,
        user_permissions,
        request,
        create_geo_levels_for_targets_file,
        csrf_token,
    ):
        """
        Upload the targets column config
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

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
            "filters": [
                {
                    "filter_group": [
                        {
                            "variable_name": "target_sample",
                            "filter_operator": "Is",
                            "filter_value": "Valid",
                        }
                    ]
                }
            ],
        }

        response = client.put(
            "/api/targets/column-config",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            assert response.status_code == 200

            get_response = client.get(
                "/api/targets/column-config",
                query_string={"form_uid": 1},
                headers={"X-CSRF-Token": csrf_token},
            )
            print(get_response.json)
            expected_response = {
                "success": True,
                "data": {
                    "file_columns": [
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
                    "location_columns": [
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
                    "target_status_columns": [
                        {
                            "column_key": "num_attempts",
                            "column_label": "Number of Attempts",
                        },
                        {
                            "column_key": "final_survey_status",
                            "column_label": "Final Survey Status",
                        },
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Final Survey Status Label",
                        },
                        {
                            "column_key": "revisit_sections",
                            "column_label": "Revisit Sections",
                        },
                    ],
                    "target_scto_filter_list": [
                        {
                            "filter_group": [
                                {
                                    "filter_group_id": 1,
                                    "variable_name": "target_sample",
                                    "filter_operator": "Is",
                                    "filter_value": "Valid",
                                }
                            ]
                        }
                    ],
                },
            }
            assert get_response.status_code == 200
            checkdiff = jsondiff.diff(expected_response, get_response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: WRITE Targets",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_get_target_config(
        self, client, csrf_token, create_target_config, user_permissions, request
    ):
        """
        Test get target config
        Expect Success and data
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/targets/config",
            query_string={"form_uid": 1},
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "data": {
                    "form_uid": 1,
                    "scto_encryption_flag": False,
                    "scto_input_id": "test_scto_input_output",
                    "scto_input_type": "form",
                    "target_source": "scto",
                },
                "success": True,
                "message": "Target config retrieved successfully",
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.json == {
                "error": "User does not have the required permission: READ Targets",
                "success": False,
            }

    def test_update_target_config(
        self, client, csrf_token, create_target_config, user_permissions, request
    ):
        """
        Test update target config using put
        Expect Success and data
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "form_uid": 1,
            "target_source": "scto",
            "scto_input_type": "form",
            "scto_input_id": "test_dynmaic_target_dataset",
            "scto_encryption_flag": True,
        }

        response = client.put(
            "/api/targets/config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "data": {
                    "form_uid": 1,
                    "scto_encryption_flag": True,
                    "scto_input_id": "test_dynmaic_target_dataset",
                    "scto_input_type": "form",
                    "target_source": "scto",
                },
                "success": True,
                "message": "Target config retrieved successfully",
            }
            get_response = client.get(
                "/api/targets/config",
                query_string={"form_uid": 1},
                headers={"X-CSRF-Token": csrf_token},
            )
            print(get_response.json)

            checkdiff = jsondiff.diff(expected_response, get_response.json)
            assert checkdiff == {}
        else:
            assert response.json == {
                "error": "User does not have the required permission: WRITE Targets",
                "success": False,
            }

    def test_upload_targets_csv_for_super_admin_user(
        self,
        client,
        login_test_user,
        upload_targets_csv,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that the targets csv can be uploaded by a super admin user
            - uses the fixture(upload_targets_csv) to upload targets
        Expect success on get with data fetched similar to uploaded data by fixture
        """
        expected_response = {
            "data": [
                {
                    "custom_fields": {
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
                        "Address": "Hyderabad",
                        "Name": "Anil",
                        "Mobile no.": "1234567890",
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "location_uid": 4,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                            "geo_level_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                            "geo_level_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                            "geo_level_uid": 3,
                        },
                    ],
                    "target_uid": 1,
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
                {
                    "custom_fields": {
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
                        "Address": "South Delhi",
                        "Name": "Anupama",
                        "Mobile no.": "1234567891",
                    },
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "location_uid": 4,
                    "target_id": "2",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                            "geo_level_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                            "geo_level_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                            "geo_level_uid": 3,
                        },
                    ],
                    "target_uid": 2,
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/targets", query_string={"form_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_targets_csv_for_survey_admin_user(
        self,
        client,
        login_test_user,
        create_locations_for_targets_file,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that the targets csv can be uploaded by a survey admin user
            - use fixture create_locations_for_targets_file to setup targets for upload
            - update logged in user to survey_admin
            - attempt upload
        Expect success on get with data fetched similar to uploaded data
        """

        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=True,
            survey_uid=1,
            is_super_admin=False,
        )

        login_user(client, test_user_credentials)

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

        expected_response = {
            "data": [
                {
                    "custom_fields": {
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
                        "Address": "Hyderabad",
                        "Name": "Anil",
                        "Mobile no.": "1234567890",
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "location_uid": 4,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                            "geo_level_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                            "geo_level_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                            "geo_level_uid": 3,
                        },
                    ],
                    "target_uid": 1,
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
                {
                    "custom_fields": {
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
                        "Address": "South Delhi",
                        "Name": "Anupama",
                        "Mobile no.": "1234567891",
                    },
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "location_uid": 4,
                    "target_id": "2",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                            "geo_level_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                            "geo_level_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                            "geo_level_uid": 3,
                        },
                    ],
                    "target_uid": 2,
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/targets", query_string={"form_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        # revert user to super admin
        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_upload_targets_csv_for_non_admin_user_roles(
        self,
        client,
        login_test_user,
        create_locations_for_targets_file,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that the targets csv can be uploaded by a non-admin user with roles
            - use fixture create_locations_for_targets_file to setup targets for upload
            - update logged in user to non-admin
            - add new roles with WRITE Targets permissions
            - attempt upload
        Expect success on get with data fetched similar to uploaded data
        """

        new_role = create_new_survey_role_with_permissions(
            # 7 - WRITE Targets
            client,
            test_user_credentials,
            "Survey Role",
            [7],
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

        expected_response = {
            "data": [
                {
                    "custom_fields": {
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
                        "Address": "Hyderabad",
                        "Name": "Anil",
                        "Mobile no.": "1234567890",
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "location_uid": 4,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                            "geo_level_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                            "geo_level_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                            "geo_level_uid": 3,
                        },
                    ],
                    "target_uid": 1,
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
                {
                    "custom_fields": {
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
                        "Address": "South Delhi",
                        "Name": "Anupama",
                        "Mobile no.": "1234567891",
                    },
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "location_uid": 4,
                    "target_id": "2",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                            "geo_level_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                            "geo_level_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                            "geo_level_uid": 3,
                        },
                    ],
                    "target_uid": 2,
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/targets", query_string={"form_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        # revert user to super admin
        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_upload_targets_csv_for_non_admin_user_no_roles(
        self,
        client,
        login_test_user,
        create_locations_for_targets_file,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that the targets csv cannot be uploaded by a non-admin user without roles
            - use fixture create_locations_for_targets_file to setup targets for upload
            - update logged in user to non-admin
            - remove all roles
            - attempt upload
        Expect Fail with a 403
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
        assert response.status_code == 403

        expected_response = {
            "success": False,
            "error": f"User does not have the required permission: WRITE Targets",
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        # revert user to super admin
        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_paginate_targets(
        self, client, login_test_user, upload_targets_csv, csrf_token
    ):
        """
        Test that we can paginate the targets response
        """

        expected_response = {
            "data": [
                {
                    "custom_fields": {
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
                        "Address": "Hyderabad",
                        "Name": "Anil",
                        "Mobile no.": "1234567890",
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "location_uid": 4,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                            "geo_level_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                            "geo_level_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                            "geo_level_uid": 3,
                        },
                    ],
                    "target_uid": 1,
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
            ],
            "success": True,
            "pagination": {"count": 2, "page": 1, "pages": 2, "per_page": 1},
        }

        # Check the response
        response = client.get(
            "/api/targets", query_string={"form_uid": 1, "page": 1, "per_page": 1}
        )

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_targets_csv_no_locations(
        self, client, login_test_user, upload_targets_csv_no_locations, csrf_token
    ):
        """
        Test that we can upload a targets csv with no locations mapped
        """

        expected_response = {
            "data": [
                {
                    "custom_fields": {
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
                        "Address": "Hyderabad",
                        "Name": "Anil",
                        "Mobile no.": "1234567890",
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "location_uid": None,
                    "target_id": "1",
                    "target_locations": None,
                    "target_uid": 1,
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
                {
                    "custom_fields": {
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
                        "Address": "South Delhi",
                        "Name": "Anupama",
                        "Mobile no.": "1234567891",
                    },
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "location_uid": None,
                    "target_id": "2",
                    "target_locations": None,
                    "target_uid": 2,
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/targets", query_string={"form_uid": 1})

        assert response.status_code == 200

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_targets_csv_no_locations_no_geo_levels_defined(
        self,
        client,
        login_test_user,
        create_form,
        update_target_mapping_criteria_to_language,
        csrf_token,
    ):
        """
        Test that we can upload a targets csv with no locations mapped and no geo levels defined
        if location is not the mapping criteria
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

        expected_response = {
            "data": [
                {
                    "custom_fields": {
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
                        "Address": "Hyderabad",
                        "Name": "Anil",
                        "Mobile no.": "1234567890",
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "location_uid": None,
                    "target_id": "1",
                    "target_locations": None,
                    "target_uid": 1,
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
                {
                    "custom_fields": {
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
                        "Address": "South Delhi",
                        "Name": "Anupama",
                        "Mobile no.": "1234567891",
                    },
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "location_uid": None,
                    "target_id": "2",
                    "target_locations": None,
                    "target_uid": 2,
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/targets", query_string={"form_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_targets_csv_no_custom_fields(
        self,
        client,
        login_test_user,
        upload_targets_csv_no_custom_fields,
        csrf_token,
    ):
        """
        Test uploading targets csv without custom fields
        """

        expected_response = {
            "data": [
                {
                    "custom_fields": {
                        "column_mapping": {
                            "gender": "gender",
                            "language": "language",
                            "location_id_column": "psu_id",
                            "target_id": "target_id",
                        }
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "location_uid": 4,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                            "geo_level_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                            "geo_level_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                            "geo_level_uid": 3,
                        },
                    ],
                    "target_uid": 1,
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "gender": "gender",
                            "language": "language",
                            "location_id_column": "psu_id",
                            "target_id": "target_id",
                        }
                    },
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "location_uid": 4,
                    "target_id": "2",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                            "geo_level_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                            "geo_level_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                            "geo_level_uid": 3,
                        },
                    ],
                    "target_uid": 2,
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/targets", query_string={"form_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_targets_csv_record_errors(
        self,
        client,
        login_test_user,
        upload_targets_csv,
        csrf_token,
    ):
        """
        Test that the sheet validations are working
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_targets_errors.csv"
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
            "mode": "merge",
        }

        response = client.post(
            "/api/targets",
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
                            "target_id",
                            "language",
                            "gender",
                            "psu_id",
                            "mobile_primary",
                            "name",
                            "address",
                            "errors",
                        ],
                        "records": [
                            {
                                "address": "Hyderabad",
                                "errors": "Duplicate row; Duplicate target_id",
                                "gender": "Male",
                                "language": "Telugu",
                                "mobile_primary": "1234567890",
                                "name": "Anil",
                                "psu_id": "17101102",
                                "row_number": 2,
                                "target_id": "1",
                            },
                            {
                                "address": "Hyderabad",
                                "errors": "Duplicate row; Duplicate target_id",
                                "gender": "Male",
                                "language": "Telugu",
                                "mobile_primary": "1234567890",
                                "name": "Anil",
                                "psu_id": "17101102",
                                "row_number": 3,
                                "target_id": "1",
                            },
                            {
                                "address": "South Delhi",
                                "errors": "Blank field(s) found in the following column(s): target_id. The column(s) cannot contain blank fields.; Location id not found in uploaded locations data for the survey's bottom level geo level",
                                "gender": "Female",
                                "language": "Hindi",
                                "mobile_primary": "1234567891",
                                "name": "Anupama",
                                "psu_id": "1",
                                "row_number": 4,
                                "target_id": "",
                            },
                        ],
                    },
                    "summary": {
                        "error_count": 6,
                        "total_correct_rows": 1,
                        "total_rows": 4,
                        "total_rows_with_errors": 3,
                    },
                    "summary_by_error_type": [
                        {
                            "error_count": 1,
                            "error_message": "Blank values are not allowed in the following columns: target_id, psu_id. Blank values in these columns were found for the following row(s): 4",
                            "error_type": "Blank field",
                            "row_numbers_with_errors": [4],
                        },
                        {
                            "error_count": 2,
                            "error_message": "Data has 2 duplicate row(s). Duplicate rows are not allowed. The following row numbers are duplicates: 2, 3",
                            "error_type": "Duplicate rows",
                            "row_numbers_with_errors": [2, 3],
                        },
                        {
                            "error_count": 2,
                            "error_message": "Data has 2 duplicate target_id(s). The following row numbers contain target_id duplicates: 2, 3",
                            "error_type": "Duplicate target_id",
                            "row_numbers_with_errors": [2, 3],
                        },
                        {
                            "error_count": 1,
                            "error_message": "Data contains 1 location_id(s) that were not found in the uploaded locations data. The following row numbers contain invalid location_id's: 4",
                            "error_type": "Invalid location_id's",
                            "row_numbers_with_errors": [4],
                        },
                    ],
                }
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_targets_csv_load_successful(
        self,
        client,
        login_test_user,
        upload_targets_csv,
        csrf_token,
    ):
        """
        Test that with load successful flag, the successful targets are uploaded and endpoint returns errors
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_targets_errors.csv"
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
            "mode": "merge",
            "load_successful": True,
        }

        response = client.post(
            "/api/targets",
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
                            "target_id",
                            "language",
                            "gender",
                            "psu_id",
                            "mobile_primary",
                            "name",
                            "address",
                            "errors",
                        ],
                        "records": [
                            {
                                "address": "Hyderabad",
                                "errors": "Duplicate row; Duplicate target_id",
                                "gender": "Male",
                                "language": "Telugu",
                                "mobile_primary": "1234567890",
                                "name": "Anil",
                                "psu_id": "17101102",
                                "row_number": 2,
                                "target_id": "1",
                            },
                            {
                                "address": "Hyderabad",
                                "errors": "Duplicate row; Duplicate target_id",
                                "gender": "Male",
                                "language": "Telugu",
                                "mobile_primary": "1234567890",
                                "name": "Anil",
                                "psu_id": "17101102",
                                "row_number": 3,
                                "target_id": "1",
                            },
                            {
                                "address": "South Delhi",
                                "errors": "Blank field(s) found in the following column(s): target_id. The column(s) cannot contain blank fields.; Location id not found in uploaded locations data for the survey's bottom level geo level",
                                "gender": "Female",
                                "language": "Hindi",
                                "mobile_primary": "1234567891",
                                "name": "Anupama",
                                "psu_id": "1",
                                "row_number": 4,
                                "target_id": "",
                            },
                        ],
                    },
                    "summary": {
                        "error_count": 6,
                        "total_correct_rows": 1,
                        "total_rows": 4,
                        "total_rows_with_errors": 3,
                    },
                    "summary_by_error_type": [
                        {
                            "error_count": 1,
                            "error_message": "Blank values are not allowed in the following columns: target_id, psu_id. Blank values in these columns were found for the following row(s): 4",
                            "error_type": "Blank field",
                            "row_numbers_with_errors": [4],
                        },
                        {
                            "error_count": 2,
                            "error_message": "Data has 2 duplicate row(s). Duplicate rows are not allowed. The following row numbers are duplicates: 2, 3",
                            "error_type": "Duplicate rows",
                            "row_numbers_with_errors": [2, 3],
                        },
                        {
                            "error_count": 2,
                            "error_message": "Data has 2 duplicate target_id(s). The following row numbers contain target_id duplicates: 2, 3",
                            "error_type": "Duplicate target_id",
                            "row_numbers_with_errors": [2, 3],
                        },
                        {
                            "error_count": 1,
                            "error_message": "Data contains 1 location_id(s) that were not found in the uploaded locations data. The following row numbers contain invalid location_id's: 4",
                            "error_type": "Invalid location_id's",
                            "row_numbers_with_errors": [4],
                        },
                    ],
                }
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        # Fetch targets to check if the successful targets were uploaded
        # Combination of targets loaded using upload_targets_csv and the successful targets from the error file
        expected_response = {
            "data": [
                {
                    "custom_fields": {
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
                        "Address": "Hyderabad",
                        "Name": "Anil",
                        "Mobile no.": "1234567890",
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "location_uid": 4,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                            "geo_level_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                            "geo_level_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                            "geo_level_uid": 3,
                        },
                    ],
                    "target_uid": 1,
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
                {
                    "custom_fields": {
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
                        "Address": "South Delhi",
                        "Name": "Anupama",
                        "Mobile no.": "1234567891",
                    },
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "location_uid": 4,
                    "target_id": "2",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                            "geo_level_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                            "geo_level_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                            "geo_level_uid": 3,
                        },
                    ],
                    "target_uid": 2,
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
                {
                    "custom_fields": {
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
                            "location_id_column": "psu_id",
                            "target_id": "target_id",
                        },
                        "Address": "South Delhi",
                        "Name": "Akhil",
                        "Mobile no.": "1234567892",
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Hindi",
                    "location_uid": 4,
                    "target_id": "3",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                            "geo_level_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                            "geo_level_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                            "geo_level_uid": 3,
                        },
                    ],
                    "target_uid": 3,
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/targets", query_string={"form_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_column_config(
        self,
        client,
        login_test_user,
        create_target_column_config,
        create_geo_levels_for_targets_file,
        user_permissions,
        csrf_token,
        request,
    ):
        """
        Test uploading the targets column config for all users
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        # Check the response
        # Check the response
        response = client.get(
            "/api/targets/column-config",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        print(response.json)

        if expected_permission:
            expected_response = {
                "data": {
                    "file_columns": [
                        {
                            "bulk_editable": False,
                            "column_name": "target_id",
                            "column_type": "basic_details",
                            "contains_pii": False,
                            "column_source": "target_id1",
                        },
                        {
                            "bulk_editable": True,
                            "column_name": "language",
                            "column_type": "basic_details",
                            "contains_pii": True,
                            "column_source": "language",
                        },
                        {
                            "bulk_editable": False,
                            "column_name": "gender",
                            "column_type": "basic_details",
                            "contains_pii": True,
                            "column_source": "gender",
                        },
                        {
                            "bulk_editable": False,
                            "column_name": "Name",
                            "column_type": "custom_fields",
                            "contains_pii": True,
                            "column_source": "name",
                        },
                        {
                            "bulk_editable": False,
                            "column_name": "Mobile no.",
                            "column_type": "custom_fields",
                            "contains_pii": True,
                            "column_source": "mobile_primary",
                        },
                        {
                            "bulk_editable": True,
                            "column_name": "Address",
                            "column_type": "custom_fields",
                            "contains_pii": True,
                            "column_source": "address",
                        },
                        {
                            "bulk_editable": True,
                            "column_name": "bottom_geo_level_location",
                            "column_type": "location",
                            "contains_pii": True,
                            "column_source": "psu_id",
                        },
                    ],
                    "location_columns": [
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
                    "target_status_columns": [
                        {
                            "column_key": "num_attempts",
                            "column_label": "Number of Attempts",
                        },
                        {
                            "column_key": "final_survey_status",
                            "column_label": "Final Survey Status",
                        },
                        {
                            "column_key": "final_survey_status_label",
                            "column_label": "Final Survey Status Label",
                        },
                        {
                            "column_key": "revisit_sections",
                            "column_label": "Revisit Sections",
                        },
                    ],
                    "target_scto_filter_list": [],
                },
                "success": True,
            }

            assert response.status_code == 200
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Targets",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_update_target(
        self,
        client,
        login_test_user,
        upload_targets_csv,
        csrf_token,
        user_permissions,
        request,
    ):
        """
        Test that an individual target can be updated for all user permissions
        """

        # Update the target
        payload = {
            "target_id": "2",
            "gender": "Male",
            "language": "Hindi",
            "location_uid": 5,
            "custom_fields": {
                "Address": "North Delhi",
                "Name": "Anupama Srivastava",
                "Mobile no.": "0234567891",
            },
        }

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.put(
            "/api/targets/2",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "data": {
                    "custom_fields": {
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
                        "Address": "North Delhi",
                        "Mobile no.": "0234567891",
                        "Name": "Anupama Srivastava",
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Hindi",
                    "location_uid": 5,
                    "target_id": "2",
                    "target_uid": 2,
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "geo_level_uid": 1,
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "geo_level_uid": 2,
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "location_id": "17101107",
                            "location_name": "ANKAPUR",
                            "geo_level_uid": 3,
                            "location_uid": 5,
                        },
                    ],
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
                "success": True,
            }

            # Check the response
            response = client.get("/api/targets/2")

            assert response.status_code == 200
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: WRITE Targets",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_update_target_incorrect_custom_fields(
        self, client, login_test_user, upload_targets_csv, csrf_token
    ):
        """
        Test that an individual target cannot be updated with incorrect custom fields
        """

        # Update the target
        payload = {
            "target_id": "2",
            "gender": "Male",
            "language": "Hindi",
            "location_uid": 5,
            "custom_fields": {
                "Address": "North Delhi",
                "Name": "Anupama Srivastava",
                "Some key": "0234567891",
            },
        }

        response = client.put(
            "/api/targets/2",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

    def test_delete_target(
        self,
        client,
        login_test_user,
        upload_targets_csv,
        csrf_token,
        create_survey,
        user_permissions,
        request,
    ):
        """
        Test that an individual target can be deleted for all target user_permissions
        Expect success for the allowed permissions
        Expect 403 for the non permissions
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        if expected_permission:
            # Delete the target
            response = client.delete(
                "/api/targets/1", headers={"X-CSRF-Token": csrf_token}
            )

            assert response.status_code == 200

        else:
            # Delete the target
            response = client.delete(
                "/api/targets/1", headers={"X-CSRF-Token": csrf_token}
            )

            assert response.status_code == 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: WRITE Targets",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_delete_target_not_found(
        self,
        client,
        login_test_user,
        upload_targets_csv,
        csrf_token,
        create_survey,
    ):
        """
        Test missing target delete - super admin
        Expect 404 not found
        """
        response = client.delete(
            "/api/targets/100", headers={"X-CSRF-Token": csrf_token}
        )

        assert response.status_code == 404

        expected_response = {
            "error": f"Target not found",
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_bulk_update_targets(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        csrf_token,
        user_permissions,
        request,
    ):
        """
        Test that targets can be bulk updated
        """

        # Update the target
        payload = {
            "target_uids": [1, 2],
            "form_uid": 1,
            "language": "English",
            "Address": "North Delhi",
            "location_uid": 5,
        }

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.patch(
            "/api/targets",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "data": [
                    {
                        "custom_fields": {
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
                            "Address": "North Delhi",
                            "Mobile no.": "1234567890",
                            "Name": "Anil",
                        },
                        "form_uid": 1,
                        "gender": "Male",
                        "language": "English",
                        "location_uid": 5,
                        "target_id": "1",
                        "target_locations": [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            },
                            {
                                "geo_level_name": "Mandal",
                                "location_id": "1101",
                                "location_name": "ADILABAD RURAL",
                                "geo_level_uid": 2,
                                "location_uid": 2,
                            },
                            {
                                "geo_level_name": "PSU",
                                "location_id": "17101107",
                                "location_name": "ANKAPUR",
                                "geo_level_uid": 3,
                                "location_uid": 5,
                            },
                        ],
                        "target_uid": 1,
                        "completed_flag": None,
                        "last_attempt_survey_status": None,
                        "last_attempt_survey_status_label": None,
                        "final_survey_status": None,
                        "final_survey_status_label": None,
                        "num_attempts": None,
                        "refusal_flag": None,
                        "revisit_sections": None,
                        "target_assignable": None,
                        "webapp_tag_color": None,
                        "scto_fields": None,
                    },
                    {
                        "custom_fields": {
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
                            "Address": "North Delhi",
                            "Mobile no.": "1234567891",
                            "Name": "Anupama",
                        },
                        "form_uid": 1,
                        "gender": "Female",
                        "language": "English",
                        "location_uid": 5,
                        "target_id": "2",
                        "target_locations": [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            },
                            {
                                "geo_level_name": "Mandal",
                                "location_id": "1101",
                                "location_name": "ADILABAD RURAL",
                                "geo_level_uid": 2,
                                "location_uid": 2,
                            },
                            {
                                "geo_level_name": "PSU",
                                "location_id": "17101107",
                                "location_name": "ANKAPUR",
                                "geo_level_uid": 3,
                                "location_uid": 5,
                            },
                        ],
                        "target_uid": 2,
                        "completed_flag": None,
                        "last_attempt_survey_status": None,
                        "last_attempt_survey_status_label": None,
                        "final_survey_status": None,
                        "final_survey_status_label": None,
                        "num_attempts": None,
                        "refusal_flag": None,
                        "revisit_sections": None,
                        "target_assignable": None,
                        "webapp_tag_color": None,
                        "scto_fields": None,
                    },
                ],
                "success": True,
            }

            # Check the response
            response = client.get("/api/targets", query_string={"form_uid": 1})

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: WRITE Targets",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_unmapped_columns(
        self, client, login_test_user, create_locations_for_targets_file, csrf_token
    ):
        """
        Test that we can leave columns unmapped
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_targets_no_language_no_gender.csv"
        )

        # Read the targets.csv file and convert it to base64
        with open(filepath, "rb") as f:
            targets_csv = f.read()
            targets_csv_encoded = base64.b64encode(targets_csv).decode("utf-8")

        # Try to upload the targets csv
        payload = {
            "column_mapping": {
                "target_id": "target_id",
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

    def test_merge_csv(
        self,
        client,
        login_test_user,
        upload_targets_csv,
        create_target_column_config,
        update_target_mapping_criteria_to_language,
        csrf_token,
    ):
        """
        Test the merge functionality

        Expected behaviour:
        New target_id's should be appended
        New mapped columns should be added for all rows
        Existing target_id's should be updated for mapped columns
        Make sure to check that the custom fields get added and updated correctly
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_targets_merge.csv"
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
                "custom_fields": [
                    {
                        "field_label": "Mobile no. (Alternate)",
                        "column_name": "mobile_primary2",
                    },
                    {
                        "field_label": "Address",
                        "column_name": "address1",
                    },
                ],
            },
            "file": targets_csv_encoded,
            "mode": "merge",
        }

        response = client.post(
            "/api/targets",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        expected_response = {
            "data": [
                {
                    "custom_fields": {
                        "column_mapping": {
                            "target_id": "target_id1",
                            "language": "language1",
                            "custom_fields": [
                                {
                                    "field_label": "Mobile no. (Alternate)",
                                    "column_name": "mobile_primary2",
                                },
                                {
                                    "field_label": "Address",
                                    "column_name": "address1",
                                },
                            ],
                        },
                        "Address": "India",
                        "Name": "Anil",
                        "Mobile no.": "1234567890",
                        "Mobile no. (Alternate)": "1234567890",
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "location_uid": 4,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                            "geo_level_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                            "geo_level_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                            "geo_level_uid": 3,
                        },
                    ],
                    "target_uid": 1,
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "target_id": "target_id1",
                            "language": "language1",
                            "custom_fields": [
                                {
                                    "field_label": "Mobile no. (Alternate)",
                                    "column_name": "mobile_primary2",
                                },
                                {
                                    "field_label": "Address",
                                    "column_name": "address1",
                                },
                            ],
                        },
                        "Address": "Kenya",
                        "Name": "Anupama",
                        "Mobile no.": "1234567891",
                        "Mobile no. (Alternate)": "1234567891",
                    },
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Telugu",
                    "location_uid": 4,
                    "target_id": "2",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                            "geo_level_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                            "geo_level_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                            "geo_level_uid": 3,
                        },
                    ],
                    "target_uid": 2,
                    "completed_flag": None,
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
                {
                    "completed_flag": None,
                    "custom_fields": {
                        "column_mapping": {
                            "target_id": "target_id1",
                            "language": "language1",
                            "custom_fields": [
                                {
                                    "field_label": "Mobile no. (Alternate)",
                                    "column_name": "mobile_primary2",
                                },
                                {
                                    "field_label": "Address",
                                    "column_name": "address1",
                                },
                            ],
                        },
                        "Address": "Philippines",
                        "Mobile no. (Alternate)": "1234567892",
                    },
                    "form_uid": 1,
                    "gender": None,
                    "language": "Tagalog",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "location_uid": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "target_id": "3",
                    "target_locations": None,
                    "target_uid": 3,
                    "webapp_tag_color": None,
                    "scto_fields": None,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/targets", query_string={"form_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_target_status(
        self,
        client,
        csrf_token,
        user_permissions,
        upload_target_status,
        request,
    ):
        """
        Test that the target_status data can be updated
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        expected_response = {
            "data": [
                {
                    "custom_fields": {
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
                        "Address": "Hyderabad",
                        "Name": "Anil",
                        "Mobile no.": "1234567890",
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "location_uid": 4,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                            "geo_level_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                            "geo_level_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                            "geo_level_uid": 3,
                        },
                    ],
                    "target_uid": 1,
                    "completed_flag": False,
                    "last_attempt_survey_status": 2,
                    "last_attempt_survey_status_label": "Partially complete - revisit",
                    "final_survey_status": 2,
                    "final_survey_status_label": "Partially complete - revisit",
                    "num_attempts": 1,
                    "refusal_flag": False,
                    "revisit_sections": ["section1", "section2"],
                    "target_assignable": True,
                    "webapp_tag_color": "gold",
                    "scto_fields": {"field1": "value1", "field2": "value2"},
                },
                {
                    "custom_fields": {
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
                        "Address": "South Delhi",
                        "Name": "Anupama",
                        "Mobile no.": "1234567891",
                    },
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "location_uid": 4,
                    "target_id": "2",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                            "geo_level_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                            "geo_level_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                            "geo_level_uid": 3,
                        },
                    ],
                    "target_uid": 2,
                    "completed_flag": True,
                    "last_attempt_survey_status": 1,
                    "last_attempt_survey_status_label": "Fully complete",
                    "final_survey_status": 1,
                    "final_survey_status_label": "Fully complete",
                    "num_attempts": 5,
                    "refusal_flag": False,
                    "revisit_sections": [],
                    "target_assignable": False,
                    "webapp_tag_color": "green",
                    "scto_fields": {"field1": "value3", "field2": "value4"},
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/targets", query_string={"form_uid": 1})

        if expected_permission:
            assert response.status_code == 200

            print(response.json)
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403
            expected_response = {
                "error": "User does not have the required permission: READ Targets",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_upload_targets_csv_missing_location_error(
        self, client, login_test_user, create_form, csrf_token
    ):
        """
        Test that when uploading targets csv without a locations column
        when mapping criteria has locations raises error

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

        print(response.json)
        assert response.status_code == 422

        expected_response = {
            "errors": {
                "column_mapping": [
                    "Field name 'location_id_column' is missing from the column mapping but is required based on the mapping criteria."
                ]
            },
            "success": False,
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_targets_csv_missing_gender_error(
        self,
        client,
        login_test_user,
        create_form,
        update_target_mapping_criteria_to_gender,
        csrf_token,
    ):
        """
        Test that when uploading targets csv without a gender column when
        the mapping criteria has gender raises error

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

        print(response.json)
        assert response.status_code == 422

        expected_response = {
            "errors": {
                "column_mapping": [
                    "Field name 'gender' is missing from the column mapping but is required based on the mapping criteria."
                ]
            },
            "success": False,
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_targets_csv_missing_language_error(
        self,
        client,
        login_test_user,
        create_form,
        update_target_mapping_criteria_to_language,
        csrf_token,
    ):
        """
        Test that when uploading targets csv without a language column when
        the mapping criteria has language raises error

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

        print(response.json)
        assert response.status_code == 422

        expected_response = {
            "errors": {
                "column_mapping": [
                    "Field name 'language' is missing from the column mapping but is required based on the mapping criteria."
                ]
            },
            "success": False,
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_targets_csv_no_mapping_criteria_error(
        self,
        client,
        login_test_user,
        create_form,
        update_target_mapping_criteria_to_none,
        csrf_token,
    ):
        """
        Test uploading targets csv fails without a mapping criteria set

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

        print(response.json)
        assert response.status_code == 422

        expected_response = {
            "error": "Supervisor to target mapping criteria not found. Cannot upload targets without selecting a mapping criteria first.",
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_delete_all_targets(
        self,
        client,
        login_test_user,
        upload_targets_csv,
        csrf_token,
        create_survey,
        user_permissions,
        request,
    ):
        """
        Test deleting all targets
        Expect success for the allowed permissions
        Expect 403 for the non permissions
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        if expected_permission:
            # Delete the targets

            response = client.delete(
                "/api/targets",
                query_string={"form_uid": 1},
                headers={"X-CSRF-Token": csrf_token},
            )

            assert response.status_code == 200

            # Check the response
            response = client.get("/api/targets", query_string={"form_uid": 1})

            assert response.json == {
                "data": [],
                "success": True,
            }

        else:
            # Delete the target
            response = client.delete(
                "/api/targets/1", headers={"X-CSRF-Token": csrf_token}
            )

            assert response.status_code == 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: WRITE Targets",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
