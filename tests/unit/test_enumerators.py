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


@pytest.mark.enumerators
class TestEnumerators:
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
    def user_with_enumerator_permissions(self, client, test_user_credentials):
        # Assign new roles and permissions
        new_role = create_new_survey_role_with_permissions(
            # 5 - WRITE Enumerators
            client,
            test_user_credentials,
            "Enumerators Role",
            [5],
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
            ("user_with_enumerator_permissions", True),
            ("user_with_no_permissions", False),
        ],
        ids=[
            "super_admin_permissions",
            "survey_admin_permissions",
            "enumerator_permissions",
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
    def create_geo_levels_for_enumerators_file(
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
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_locations_for_enumerators_file(
        self,
        client,
        login_test_user,
        create_geo_levels_for_enumerators_file,
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
    def create_locations_for_enumerators_file_medium(
        self,
        client,
        login_test_user,
        create_geo_levels_for_enumerators_file,
        csrf_token,
    ):
        """
        Upload locations csv as a setup step for the enumerators upload tests
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_locations_small_multiple.csv"
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
    def create_enumerator_column_config(
        self, client, login_test_user, create_form, csrf_token
    ):
        """
        Upload the enumerators column config
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

        print(response.json)
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def upload_enumerators_csv(
        self, client, login_test_user, create_locations_for_enumerators_file, csrf_token
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
    def upload_enumerators_csv_no_locations(
        self,
        client,
        login_test_user,
        create_locations_for_enumerators_file,
        update_surveyor_mapping_criteria_to_language,
        csrf_token,
    ):
        """
        Upload the enumerators csv with no locations
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
        update_surveyor_mapping_criteria_to_gender,
        csrf_token,
    ):
        """
        Upload the enumerators csv with no locations mapped and no geo levels defined
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
        self, client, login_test_user, create_locations_for_enumerators_file, csrf_token
    ):
        """
        Upload the enumerators csv with no custom fields
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
        self, client, login_test_user, create_locations_for_enumerators_file, csrf_token
    ):
        """
        Upload the enumerators csv with mandal as the prime geo level instead of district
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
        print(response.json)
        assert response.status_code == 200

    @pytest.fixture()
    def create_surveyor_stats(
        self, client, login_test_user, upload_enumerators_csv, csrf_token
    ):
        """
        Insert data for surveyor stats
        """

        payload = {
            "form_uid": 1,
            "surveyor_stats": [
                {
                    "enumerator_id": "0294612",
                    "avg_num_submissions_per_day": 20,
                    "avg_num_completed_per_day": 7,
                },
                {
                    "enumerator_id": "0294613",
                    "avg_num_submissions_per_day": 15,
                    "avg_num_completed_per_day": 5,
                },
            ],
        }

        response = client.put(
            "/api/enumerators/surveyor-stats",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def update_surveyor_mapping_criteria_to_language(self, client, csrf_token):
        """
        Method to update the mapping criteria to Langauge
        """

        # Update surveyor_mapping_criteria to language
        payload = {
            "assignment_process": "Manual",
            "language_location_mapping": False,
            "reassignment_required": False,
            "target_mapping_criteria": ["Location"],
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
    def update_surveyor_mapping_criteria_to_gender(self, client, csrf_token):
        """
        Method to update the mapping criteria to Gender
        """

        # Update surveyor_mapping_criteria to gender
        payload = {
            "assignment_process": "Manual",
            "language_location_mapping": False,
            "reassignment_required": False,
            "target_mapping_criteria": ["Location"],
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

    @pytest.fixture()
    def update_surveyor_mapping_criteria_to_none(self, client, csrf_token):
        """
        Method to update the mapping criteria to none
        """

        payload = {
            "assignment_process": "Manual",
            "language_location_mapping": False,
            "reassignment_required": False,
            "target_mapping_criteria": ["Location"],
            "surveyor_mapping_criteria": None,
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

    def test_upload_merge_update_enumerators_csv(
        self, client, create_form, login_test_user, csrf_token, upload_enumerators_csv
    ):
        """
        Test that the enumerators merge functionality that columns can be updated
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_enumerators_small_updated.csv"
        )

        # Read the enumerators.csv file and convert it to base64
        with open(filepath, "rb") as f:
            enumerators_csv = f.read()
            enumerators_csv_encoded = base64.b64encode(enumerators_csv).decode("utf-8")

        # upload data with changes for update
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
            "mode": "merge",
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

        # upload data with changes for merge

        expected_response = {
            "data": [
                {
                    "custom_fields": {
                        "Age": "1",
                        "Mobile (Secondary)": "1143456789",
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
                    "enumerator_uid": 1,
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "English",
                    "mobile_primary": "1234568789",
                    "monitor_locations": None,
                    "monitor_status": None,
                    "name": "E Dodge",
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
                    "surveyor_status": "Active",
                },
                {
                    "custom_fields": {
                        "Age": "2",
                        "Mobile (Secondary)": "1143567891",
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
                    "enumerator_uid": 2,
                    "gender": "Female",
                    "home_address": "my house",
                    "language": "Telugu",
                    "mobile_primary": "1234569789",
                    "monitor_locations": None,
                    "monitor_status": None,
                    "name": "Jan Meher",
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
                    "surveyor_status": "Active",
                },
                {
                    "custom_fields": {
                        "Age": "3",
                        "Mobile (Secondary)": "1144567892",
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
                    "email": "jay.prakash@idinsight.org",
                    "enumerator_id": "0294614",
                    "enumerator_uid": 3,
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Hindi",
                    "mobile_primary": "1233564789",
                    "monitor_locations": [
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
                    "monitor_status": "Active",
                    "name": "J Prakash",
                    "surveyor_locations": None,
                    "surveyor_status": None,
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
                    "enumerator_uid": 4,
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Swahili",
                    "mobile_primary": "1236456789",
                    "monitor_locations": [
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
                    "monitor_status": "Active",
                    "name": "Griff Muteti",
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
                    "surveyor_status": "Active",
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/enumerators", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_merge_append_enumerators_csv(
        self, client, create_form, login_test_user, csrf_token, upload_enumerators_csv
    ):
        """
        Test that in the enumerators merge functionality new columns are being appended
        """

        # Upload updated data with new columns appended to the original sheet uploaded by upload_enumerators_csv fixture
        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_enumerators_small_append.csv"
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
            "mode": "merge",
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
                    "enumerator_uid": 1,
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "English",
                    "mobile_primary": "0123456789",
                    "monitor_locations": None,
                    "monitor_status": None,
                    "name": "E Dodge",
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
                    "enumerator_uid": 2,
                    "gender": "Female",
                    "home_address": "my house",
                    "language": "Telugu",
                    "mobile_primary": "0123456789",
                    "monitor_locations": None,
                    "monitor_status": None,
                    "name": "Jan Meher",
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
                    "surveyor_status": "Active",
                },
                {
                    "custom_fields": {
                        "Age": "3",
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
                    "email": "jay.prakash@idinsight.org",
                    "enumerator_id": "0294614",
                    "enumerator_uid": 3,
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Hindi",
                    "mobile_primary": "0123456789",
                    "monitor_locations": [
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
                    "monitor_status": "Active",
                    "name": "J Prakash",
                    "surveyor_locations": None,
                    "surveyor_status": None,
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
                    "enumerator_uid": 4,
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Swahili",
                    "mobile_primary": "0123456789",
                    "monitor_locations": [
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
                    "monitor_status": "Active",
                    "name": "Griff Muteti",
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
                    "email": "rohan@idinsight.org",
                    "enumerator_id": "0294616",
                    "enumerator_uid": 5,
                    "gender": "Male",
                    "home_address": "house",
                    "language": "Hindi",
                    "mobile_primary": "0123456389",
                    "monitor_locations": [
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
                    "monitor_status": "Active",
                    "name": "Rohan M",
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
                    "email": "yashi@idinsight.org",
                    "enumerator_id": "0294617",
                    "enumerator_uid": 6,
                    "gender": "Female",
                    "home_address": "house",
                    "language": "Hindi",
                    "mobile_primary": "0123556389",
                    "monitor_locations": [
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
                    "monitor_status": "Active",
                    "name": "Yashi M",
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
                    "email": "utkarsh@idinsight.org",
                    "enumerator_id": "0294618",
                    "enumerator_uid": 7,
                    "gender": "Male",
                    "home_address": "house",
                    "language": "Hindi",
                    "mobile_primary": "0123556382",
                    "monitor_locations": [
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
                    "monitor_status": "Active",
                    "name": "Utkarsh",
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
                    "surveyor_status": "Active",
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/enumerators", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_enumerators_csv_for_super_admin_user(
        self, client, login_test_user, upload_enumerators_csv, csrf_token
    ):
        """
        Test that the enumerators csv can be uploaded
        """
        expected_response = {
            "data": [
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "1123456789",
                        "Age": "1",
                    },
                    "email": "eric.dodge@idinsight.org",
                    "enumerator_id": "0294612",
                    "enumerator_uid": 1,
                    "name": "Eric Dodge",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "English",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_locations": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "1123456789",
                        "Age": "2",
                    },
                    "email": "jahnavi.meher@idinsight.org",
                    "enumerator_id": "0294613",
                    "enumerator_uid": 2,
                    "name": "Jahnavi Meher",
                    "gender": "Female",
                    "home_address": "my house",
                    "language": "Telugu",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_locations": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "1123456789",
                        "Age": "3",
                    },
                    "email": "jay.prakash@idinsight.org",
                    "enumerator_id": "0294614",
                    "enumerator_uid": 3,
                    "name": "Jay Prakash",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Hindi",
                    "mobile_primary": "0123456789",
                    "monitor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_status": "Active",
                    "surveyor_locations": None,
                    "surveyor_status": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "1123456789",
                        "Age": "4",
                    },
                    "email": "griffin.muteti@idinsight.org",
                    "enumerator_id": "0294615",
                    "enumerator_uid": 4,
                    "name": "Griffin Muteti",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Swahili",
                    "mobile_primary": "0123456789",
                    "monitor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "surveyor_status": "Active",
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/enumerators", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_enumerators_csv_for_survey_admin_user(
        self,
        client,
        login_test_user,
        create_surveyor_stats,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that the enumerators csv can be uploaded by a survey_admin user
        Expect success since the user created the survey
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

        expected_response = {
            "data": [
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "1123456789",
                        "Age": "1",
                    },
                    "email": "eric.dodge@idinsight.org",
                    "enumerator_id": "0294612",
                    "enumerator_uid": 5,
                    "name": "Eric Dodge",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "English",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_locations": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "1123456789",
                        "Age": "2",
                    },
                    "email": "jahnavi.meher@idinsight.org",
                    "enumerator_id": "0294613",
                    "enumerator_uid": 6,
                    "name": "Jahnavi Meher",
                    "gender": "Female",
                    "home_address": "my house",
                    "language": "Telugu",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_locations": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "1123456789",
                        "Age": "3",
                    },
                    "email": "jay.prakash@idinsight.org",
                    "enumerator_id": "0294614",
                    "enumerator_uid": 7,
                    "name": "Jay Prakash",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Hindi",
                    "mobile_primary": "0123456789",
                    "monitor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_status": "Active",
                    "surveyor_locations": None,
                    "surveyor_status": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "1123456789",
                        "Age": "4",
                    },
                    "email": "griffin.muteti@idinsight.org",
                    "enumerator_id": "0294615",
                    "enumerator_uid": 8,
                    "name": "Griffin Muteti",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Swahili",
                    "mobile_primary": "0123456789",
                    "monitor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "surveyor_status": "Active",
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/enumerators", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_upload_enumerators_csv_for_non_admin_user_roles(
        self,
        client,
        login_test_user,
        create_locations_for_enumerators_file,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that the enumerators csv can be uploaded by a non_admin user with WRITE Enumerators permissions
        Expect success since the user created the survey
        """
        new_role = create_new_survey_role_with_permissions(
            # 5 - WRITE Enumerators
            client,
            test_user_credentials,
            "Survey Role",
            [5],
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

        expected_response = {
            "data": [
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "1123456789",
                        "Age": "1",
                    },
                    "email": "eric.dodge@idinsight.org",
                    "enumerator_id": "0294612",
                    "enumerator_uid": 1,
                    "name": "Eric Dodge",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "English",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_locations": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "1123456789",
                        "Age": "2",
                    },
                    "email": "jahnavi.meher@idinsight.org",
                    "enumerator_id": "0294613",
                    "enumerator_uid": 2,
                    "name": "Jahnavi Meher",
                    "gender": "Female",
                    "home_address": "my house",
                    "language": "Telugu",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_locations": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "1123456789",
                        "Age": "3",
                    },
                    "email": "jay.prakash@idinsight.org",
                    "enumerator_id": "0294614",
                    "enumerator_uid": 3,
                    "name": "Jay Prakash",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Hindi",
                    "mobile_primary": "0123456789",
                    "monitor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_status": "Active",
                    "surveyor_locations": None,
                    "surveyor_status": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "1123456789",
                        "Age": "4",
                    },
                    "email": "griffin.muteti@idinsight.org",
                    "enumerator_id": "0294615",
                    "enumerator_uid": 4,
                    "name": "Griffin Muteti",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Swahili",
                    "mobile_primary": "0123456789",
                    "monitor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "surveyor_status": "Active",
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/enumerators", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_upload_enumerators_csv_for_non_admin_user_no_roles(
        self,
        client,
        login_test_user,
        create_locations_for_enumerators_file,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that the enumerators csv cannot
        be uploaded by a non_admin user without WRITE Enumerators permissions
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

        print(response)

        assert response.status_code == 403

        expected_response = {
            "success": False,
            "error": f"User does not have the required permission: WRITE Enumerators",
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_upload_enumerators_csv_no_locations(
        self, client, login_test_user, upload_enumerators_csv_no_locations, csrf_token
    ):
        """
        Test uploading enumerators csv with no locations mapped
        """

        expected_response = {
            "data": [
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary",
                                    "field_label": "Mobile (Secondary)",
                                },
                            ],
                            "gender": "gender",
                            "home_address": "home_address",
                            "language": "language",
                            "email": "email",
                            "enumerator_id": "enumerator_id",
                            "enumerator_type": "enumerator_type",
                            "mobile_primary": "mobile_primary",
                            "name": "name",
                        },
                        "Mobile (Secondary)": "1123456789",
                    },
                    "email": "eric.dodge@idinsight.org",
                    "enumerator_id": "0294612",
                    "enumerator_uid": 1,
                    "name": "Eric Dodge",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "English",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": None,
                    "monitor_locations": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary",
                                    "field_label": "Mobile (Secondary)",
                                },
                            ],
                            "gender": "gender",
                            "home_address": "home_address",
                            "language": "language",
                            "email": "email",
                            "enumerator_id": "enumerator_id",
                            "enumerator_type": "enumerator_type",
                            "mobile_primary": "mobile_primary",
                            "name": "name",
                        },
                        "Mobile (Secondary)": "1123456789",
                    },
                    "email": "jahnavi.meher@idinsight.org",
                    "enumerator_id": "0294613",
                    "enumerator_uid": 2,
                    "name": "Jahnavi Meher",
                    "gender": "Female",
                    "home_address": "my house",
                    "language": "Telugu",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": None,
                    "monitor_locations": None,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/enumerators", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_enumerators_csv_no_custom_fields(
        self,
        client,
        login_test_user,
        upload_enumerators_csv_no_custom_fields,
        csrf_token,
    ):
        """
        Test uploading enumerators csv without custom fields
        """

        expected_response = {
            "data": [
                {
                    "email": "eric.dodge@idinsight.org",
                    "enumerator_id": "0294612",
                    "enumerator_uid": 1,
                    "name": "Eric Dodge",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "English",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_locations": None,
                    "custom_fields": {
                        "column_mapping": {
                            "gender": "gender",
                            "home_address": "home_address",
                            "language": "language",
                            "email": "email",
                            "enumerator_id": "enumerator_id",
                            "enumerator_type": "enumerator_type",
                            "location_id_column": "district_id",
                            "mobile_primary": "mobile_primary",
                            "name": "name",
                        }
                    },
                },
                {
                    "email": "jahnavi.meher@idinsight.org",
                    "enumerator_id": "0294613",
                    "enumerator_uid": 2,
                    "name": "Jahnavi Meher",
                    "gender": "Female",
                    "home_address": "my house",
                    "language": "Telugu",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_locations": None,
                    "custom_fields": {
                        "column_mapping": {
                            "gender": "gender",
                            "home_address": "home_address",
                            "language": "language",
                            "email": "email",
                            "enumerator_id": "enumerator_id",
                            "enumerator_type": "enumerator_type",
                            "location_id_column": "district_id",
                            "mobile_primary": "mobile_primary",
                            "name": "name",
                        }
                    },
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/enumerators", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_enumerators_csv_mandal_prime_geo_level(
        self,
        client,
        login_test_user,
        upload_enumerators_csv_mandal_prime_geo_level,
        csrf_token,
    ):
        """
        Test uploading enumerators csv with a prime geo level that is not the top level geo level
        """

        expected_response = {
            "data": [
                {
                    "custom_fields": {
                        "column_mapping": {
                            "enumerator_id": "enumerator_id",
                            "name": "name",
                            "email": "email",
                            "gender": "gender",
                            "home_address": "home_address",
                            "language": "language",
                            "mobile_primary": "mobile_primary",
                            "enumerator_type": "enumerator_type",
                            "location_id_column": "mandal_id",
                            "custom_fields": [
                                {
                                    "field_label": "Mobile (Secondary)",
                                    "column_name": "mobile_secondary",
                                },
                            ],
                        },
                        "Mobile (Secondary)": "1123456789",
                    },
                    "email": "eric.dodge@idinsight.org",
                    "enumerator_id": "0294612",
                    "enumerator_uid": 1,
                    "name": "Eric Dodge",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "English",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
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
                        ]
                    ],
                    "monitor_locations": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "enumerator_id": "enumerator_id",
                            "name": "name",
                            "email": "email",
                            "mobile_primary": "mobile_primary",
                            "enumerator_type": "enumerator_type",
                            "gender": "gender",
                            "home_address": "home_address",
                            "language": "language",
                            "location_id_column": "mandal_id",
                            "custom_fields": [
                                {
                                    "field_label": "Mobile (Secondary)",
                                    "column_name": "mobile_secondary",
                                },
                            ],
                        },
                        "Mobile (Secondary)": "1123456789",
                    },
                    "email": "jahnavi.meher@idinsight.org",
                    "enumerator_id": "0294613",
                    "enumerator_uid": 2,
                    "name": "Jahnavi Meher",
                    "gender": "Female",
                    "home_address": "my house",
                    "language": "Telugu",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            },
                            {
                                "geo_level_name": "Mandal",
                                "location_id": "1104",
                                "location_name": "BELA",
                                "geo_level_uid": 2,
                                "location_uid": 3,
                            },
                        ]
                    ],
                    "monitor_locations": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "enumerator_id": "enumerator_id",
                            "name": "name",
                            "email": "email",
                            "mobile_primary": "mobile_primary",
                            "gender": "gender",
                            "home_address": "home_address",
                            "language": "language",
                            "enumerator_type": "enumerator_type",
                            "location_id_column": "mandal_id",
                            "custom_fields": [
                                {
                                    "field_label": "Mobile (Secondary)",
                                    "column_name": "mobile_secondary",
                                },
                            ],
                        },
                        "Mobile (Secondary)": "1123456789",
                    },
                    "email": "jay.prakash@idinsight.org",
                    "enumerator_id": "0294614",
                    "enumerator_uid": 3,
                    "name": "Jay Prakash",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Hindi",
                    "mobile_primary": "0123456789",
                    "monitor_locations": [
                        [
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
                        ]
                    ],
                    "monitor_status": "Active",
                    "surveyor_locations": None,
                    "surveyor_status": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "enumerator_id": "enumerator_id",
                            "name": "name",
                            "email": "email",
                            "mobile_primary": "mobile_primary",
                            "gender": "gender",
                            "home_address": "home_address",
                            "language": "language",
                            "enumerator_type": "enumerator_type",
                            "location_id_column": "mandal_id",
                            "custom_fields": [
                                {
                                    "field_label": "Mobile (Secondary)",
                                    "column_name": "mobile_secondary",
                                },
                            ],
                        },
                        "Mobile (Secondary)": "1123456789",
                    },
                    "email": "griffin.muteti@idinsight.org",
                    "enumerator_id": "0294615",
                    "enumerator_uid": 4,
                    "name": "Griffin Muteti",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Swahili",
                    "mobile_primary": "0123456789",
                    "monitor_locations": [
                        [
                            {
                                "location_id": "1",
                                "location_uid": 1,
                                "geo_level_uid": 1,
                                "location_name": "ADILABAD",
                                "geo_level_name": "District",
                            },
                            {
                                "location_id": "1104",
                                "location_uid": 3,
                                "geo_level_uid": 2,
                                "location_name": "BELA",
                                "geo_level_name": "Mandal",
                            },
                        ],
                        [
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
                        ],
                    ],
                    "monitor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "location_id": "1",
                                "location_uid": 1,
                                "geo_level_uid": 1,
                                "location_name": "ADILABAD",
                                "geo_level_name": "District",
                            },
                            {
                                "location_id": "1104",
                                "location_uid": 3,
                                "geo_level_uid": 2,
                                "location_name": "BELA",
                                "geo_level_name": "Mandal",
                            },
                        ],
                        [
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
                        ],
                    ],
                    "surveyor_status": "Active",
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/enumerators", query_string={"form_uid": 1})

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_enumerators_csv_record_errors(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        csrf_token,
    ):
        """
        Test that the sheet validations are working on a sheet with errors
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_enumerators_errors.csv"
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
                "custom_fields": [
                    {
                        "field_label": "Mobile (Secondary)",
                        "column_name": "mobile_secondary",
                    },
                    {
                        "field_label": "Age",
                        "column_name": "age",
                    },
                ],
            },
            "file": enumerators_csv_encoded,
            "mode": "merge",
        }

        response = client.post(
            "/api/enumerators",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422
        print(response.json)

        expected_response = {
            "errors": {
                "record_errors": {
                    "invalid_records": {
                        "ordered_columns": [
                            "row_number",
                            "enumerator_id",
                            "name",
                            "email",
                            "mobile_primary",
                            "enumerator_type",
                            "language",
                            "gender",
                            "home_address",
                            "district_id",
                            "mobile_secondary",
                            "age",
                            "errors",
                        ],
                        "records": [
                            {
                                "age": "1",
                                "district_id": "2",
                                "email": "eric.dodge@idinsight.org",
                                "enumerator_id": "0294612",
                                "enumerator_type": "surveyor",
                                "errors": "Duplicate enumerator_id; Location id not found in uploaded locations data for the survey's prime geo level",
                                "gender": "Male",
                                "home_address": "my house",
                                "language": "English",
                                "mobile_primary": "0123456789",
                                "mobile_secondary": "1123456789",
                                "name": "Eric Dodge",
                                "row_number": 2,
                            },
                            {
                                "age": "2",
                                "district_id": "1",
                                "email": "jahnavi.meher@idinsight.org",
                                "enumerator_id": "0294612",
                                "enumerator_type": "surveyor",
                                "errors": "Duplicate enumerator_id; Invalid mobile number - numbers must be between 10 and 20 characters in length and can only contain digits or the special characters '-', '.', '+', '(', or ')'",
                                "gender": "Female",
                                "home_address": "my house",
                                "language": "Telugu",
                                "mobile_primary": "0123456789*&",
                                "mobile_secondary": "1123456789",
                                "name": "Jahnavi Meher",
                                "row_number": 3,
                            },
                            {
                                "age": "3",
                                "district_id": "1",
                                "email": "jay.prakash@idinsight.org",
                                "enumerator_id": "0294614",
                                "enumerator_type": "monitor",
                                "errors": "Blank field(s) found in the following column(s): name. The column(s) cannot contain blank fields.; Invalid mobile number - numbers must be between 10 and 20 characters in length and can only contain digits or the special characters '-', '.', '+', '(', or ')'",
                                "gender": "Male",
                                "home_address": "my house",
                                "language": "Hindi",
                                "mobile_primary": "012345678901234567890123456789",
                                "mobile_secondary": "1123456789",
                                "name": "",
                                "row_number": 4,
                            },
                            {
                                "age": "4",
                                "district_id": "1",
                                "email": "griffin.muteti@sigienajsnbjerngui2.com",
                                "enumerator_id": "0294615",
                                "enumerator_type": "monitor;surveyor",
                                "errors": "Duplicate row; Duplicate enumerator_id; The domain name sigienajsnbjerngui2.com does not exist.; Invalid mobile number - numbers must be between 10 and 20 characters in length and can only contain digits or the special characters '-', '.', '+', '(', or ')'",
                                "gender": "Male",
                                "home_address": "my house",
                                "language": "Swahili",
                                "mobile_primary": "012345678",
                                "mobile_secondary": "1123456789",
                                "name": "Griffin Muteti",
                                "row_number": 5,
                            },
                            {
                                "age": "4",
                                "district_id": "1",
                                "email": "griffin.muteti@sigienajsnbjerngui2.com",
                                "enumerator_id": "0294615",
                                "enumerator_type": "monitor;surveyor",
                                "errors": "Duplicate row; Duplicate enumerator_id; The domain name sigienajsnbjerngui2.com does not exist.; Invalid mobile number - numbers must be between 10 and 20 characters in length and can only contain digits or the special characters '-', '.', '+', '(', or ')'",
                                "gender": "Male",
                                "home_address": "my house",
                                "language": "Swahili",
                                "mobile_primary": "012345678",
                                "mobile_secondary": "1123456789",
                                "name": "Griffin Muteti",
                                "row_number": 6,
                            },
                        ],
                    },
                    "summary": {
                        "error_count": 14,
                        "total_correct_rows": 0,
                        "total_rows": 5,
                        "total_rows_with_errors": 5,
                    },
                    "summary_by_error_type": [
                        {
                            "error_count": 1,
                            "error_message": "Blank values are not allowed in the following columns: enumerator_id, name, email, enumerator_type. Blank values in these columns were found for the following row(s): 4",
                            "error_type": "Blank field",
                            "row_numbers_with_errors": [4],
                        },
                        {
                            "error_count": 2,
                            "error_message": "The file has 2 duplicate row(s). Duplicate rows are not allowed. The following row numbers are duplicates: 5, 6",
                            "error_type": "Duplicate rows",
                            "row_numbers_with_errors": [5, 6],
                        },
                        {
                            "error_count": 4,
                            "error_message": "The file has 4 duplicate enumerator_id(s). The following row numbers contain enumerator_id duplicates: 2, 3, 5, 6",
                            "error_type": "Duplicate enumerator_id's in file",
                            "row_numbers_with_errors": [2, 3, 5, 6],
                        },
                        {
                            "error_count": 2,
                            "error_message": "The file contains 2 invalid email ID(s). The following row numbers have invalid email ID's: 5, 6",
                            "error_type": "Invalid email ID",
                            "row_numbers_with_errors": [5, 6],
                        },
                        {
                            "error_count": 4,
                            "error_message": "The file contains 4 invalid mobile number(s) in the mobile_primary field. Mobile numbers must be between 10 and 20 characters in length and can only contain digits or the special characters '-', '.', '+', '(', or ')'. The following row numbers have invalid mobile numbers: 3, 4, 5, 6",
                            "error_type": "Invalid mobile number",
                            "row_numbers_with_errors": [3, 4, 5, 6],
                        },
                        {
                            "error_count": 1,
                            "error_message": "The file contains 1 location_id(s) that were not found in the uploaded locations data. The following row numbers contain invalid location_id's: 2",
                            "error_type": "Invalid location_id's",
                            "row_numbers_with_errors": [2],
                        },
                    ],
                }
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        print(response.json)
        assert checkdiff == {}

    def test_upload_column_config(
        self,
        client,
        login_test_user,
        create_enumerator_column_config,
        create_geo_levels_for_enumerators_file,
        user_permissions,
        csrf_token,
        request,
    ):
        """
        Test uploading the enumerators column config for all users
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        # Check the response
        response = client.get(
            "/api/enumerators/column-config",
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
                            "column_name": "enumerator_id",
                            "column_type": "personal_details",
                        },
                        {
                            "bulk_editable": False,
                            "column_name": "name",
                            "column_type": "personal_details",
                        },
                        {
                            "bulk_editable": False,
                            "column_name": "email",
                            "column_type": "personal_details",
                        },
                        {
                            "bulk_editable": False,
                            "column_name": "mobile_primary",
                            "column_type": "personal_details",
                        },
                        {
                            "bulk_editable": True,
                            "column_name": "language",
                            "column_type": "personal_details",
                        },
                        {
                            "bulk_editable": False,
                            "column_name": "home_address",
                            "column_type": "personal_details",
                        },
                        {
                            "bulk_editable": False,
                            "column_name": "gender",
                            "column_type": "personal_details",
                        },
                        {
                            "bulk_editable": True,
                            "column_name": "prime_geo_level_location",
                            "column_type": "location",
                        },
                        {
                            "bulk_editable": True,
                            "column_name": "Mobile (Secondary)",
                            "column_type": "custom_fields",
                        },
                        {
                            "bulk_editable": False,
                            "column_name": "Age",
                            "column_type": "custom_fields",
                        },
                    ],
                    "location_columns": [
                        {
                            "column_key": "surveyor_locations[0].location_id",
                            "column_label": "District ID",
                        },
                        {
                            "column_key": "surveyor_locations[0].location_name",
                            "column_label": "District Name",
                        },
                        {
                            "column_key": "surveyor_locations[1].location_id",
                            "column_label": "Mandal ID",
                        },
                        {
                            "column_key": "surveyor_locations[1].location_name",
                            "column_label": "Mandal Name",
                        },
                        {
                            "column_key": "surveyor_locations[2].location_id",
                            "column_label": "PSU ID",
                        },
                        {
                            "column_key": "surveyor_locations[2].location_name",
                            "column_label": "PSU Name",
                        },
                    ],
                    "productivity_columns": [
                        {
                            "column_key": f"form_productivity.test_scto_input_output.total_assigned_targets",
                            "column_label": "Total Assigned Targets",
                        },
                        {
                            "column_key": f"form_productivity.test_scto_input_output.total_pending_targets",
                            "column_label": "Total Pending Targets",
                        },
                        {
                            "column_key": f"form_productivity.test_scto_input_output.total_completed_targets",
                            "column_label": "Total Completed Targets",
                        },
                        {
                            "column_key": f"form_productivity.test_scto_input_output.avg_num_submissions_per_day",
                            "column_label": "Avg. submissions/day",
                        },
                        {
                            "column_key": f"form_productivity.test_scto_input_output.avg_num_completed_per_day",
                            "column_label": "Avg. completed/day",
                        },
                    ],
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
                "error": f"User does not have the required permission: READ Enumerators",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_update_enumerator(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        csrf_token,
        user_permissions,
        request,
    ):
        """
        Test that an individual enumerator can be updated
        """

        # Update the enumerator
        payload = {
            "enumerator_id": "0294612",
            "name": "Hi",
            "email": "eric.dodge@idinsight.org",
            "mobile_primary": "0123456789",
            "language": "English",
            "gender": "Male",
            "home_address": "my house",
            "custom_fields": {"Mobile (Secondary)": "1123456789", "Age": "1"},
            "location_uid": 1,
        }

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.put(
            "/api/enumerators/1",
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
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "email": "eric.dodge@idinsight.org",
                    "enumerator_id": "0294612",
                    "enumerator_uid": 1,
                    "name": "Hi",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "English",
                    "mobile_primary": "0123456789",
                },
                "success": True,
            }

            # Check the response
            response = client.get("/api/enumerators/1")
            print(response.json)
            assert response.status_code == 200
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: WRITE Enumerators",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_update_enumerator_incorrect_custom_fields(
        self, client, login_test_user, upload_enumerators_csv, csrf_token
    ):
        """
        Test that an individual enumerator can be updated
        """

        # Update the enumerator
        payload = {
            "enumerator_id": "0294612",
            "name": "Hi",
            "email": "eric.dodge@idinsight.org",
            "mobile_primary": "0123456789",
            "language": "English",
            "gender": "Male",
            "home_address": "my house",
            "custom_fields": {"Some key": "1123456789", "Age": "1"},
        }

        response = client.put(
            "/api/enumerators/1",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

    def test_update_location_mapping(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        csrf_token,
        test_user_credentials,
        user_permissions,
        request,
    ):
        """
        Test that a location mapping can be updated - for all enumerator permissions
        Expect success for the allowed permissions
        Expect 403 fail for the un-allowed permissions
        """

        # Update the enumerator
        payload = {
            "form_uid": 1,
            "enumerator_type": "surveyor",
            "location_uid": None,
        }

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.put(
            "/api/enumerators/1/roles/locations",
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
                    "roles": [
                        {
                            "enumerator_type": "surveyor",
                            "status": "Active",
                            "locations": None,
                        }
                    ],
                },
                "success": True,
            }

            # Check the response
            response = client.get(
                "/api/enumerators/1/roles",
                query_string={"form_uid": 1, "enumerator_type": "surveyor"},
                content_type="application/json",
            )
            print(response.json)
            assert response.status_code == 200
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            assert response.status_code == 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: WRITE Enumerators",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_delete_enumerator_for_super_admin_user(
        self, client, login_test_user, upload_enumerators_csv, csrf_token
    ):
        """
        Test that an individual enumerator can be deleted by a super admin user
        """

        # Delete the enumerator
        response = client.delete(
            "/api/enumerators/1", headers={"X-CSRF-Token": csrf_token}
        )

        assert response.status_code == 200

        response = client.get("/api/enumerators/1", content_type="application/json")

        assert response.status_code == 404

    def test_delete_enumerator_for_survey_admin_user(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        test_user_credentials,
        csrf_token,
    ):
        """
        Test that an individual enumerator can be deleted by a super admin user
        """
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=True,
            survey_uid=1,
            is_super_admin=False,
        )

        login_user(client, test_user_credentials)

        # Delete the enumerator
        response = client.delete(
            "/api/enumerators/1", headers={"X-CSRF-Token": csrf_token}
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

    def test_delete_enumerator_for_non_admin_user_roles(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        test_user_credentials,
        csrf_token,
    ):
        """
        Test that an individual enumerator can be deleted by a non admin user with roles
        """
        new_role = create_new_survey_role_with_permissions(
            # 5 - WRITE Enumerators
            client,
            test_user_credentials,
            "Survey Role",
            [5],
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

        # Delete the enumerator
        response = client.delete(
            "/api/enumerators/1", headers={"X-CSRF-Token": csrf_token}
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

    def test_delete_enumerator_for_non_admin_user_no_roles(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        test_user_credentials,
        csrf_token,
    ):
        """
        Test that an individual enumerator cannot be deleted by a non admin user without roles
        Expect 403 Fail
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

        # Delete the enumerator
        response = client.delete(
            "/api/enumerators/1", headers={"X-CSRF-Token": csrf_token}
        )

        assert response.status_code == 403

        expected_response = {
            "success": False,
            "error": f"User does not have the required permission: WRITE Enumerators",
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_update_role_status_for_super_admin_user(
        self, client, login_test_user, upload_enumerators_csv, csrf_token
    ):
        """
        Test that the surveyor status can be updated by a super admin user
        """

        # Update the enumerator
        payload = {
            "status": "Temp. Inactive",
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

        expected_response = {
            "data": {
                "form_uid": 1,
                "roles": [
                    {
                        "enumerator_type": "surveyor",
                        "status": "Temp. Inactive",
                        "locations": [{"location_uid": 1}],
                    }
                ],
            },
            "success": True,
        }

        # Check the response
        response = client.get(
            "/api/enumerators/1/roles",
            query_string={"form_uid": 1, "enumerator_type": "surveyor"},
            content_type="application/json",
        )
        print(response.json)
        assert response.status_code == 200
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_role_status_for_survey_admin_user(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that the surveyor status can be updated by a survey admin user
        """
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=True,
            survey_uid=1,
            is_super_admin=False,
            roles=[],
        )

        login_user(client, test_user_credentials)

        # Update the enumerator
        payload = {
            "status": "Temp. Inactive",
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

        expected_response = {
            "data": {
                "form_uid": 1,
                "roles": [
                    {
                        "enumerator_type": "surveyor",
                        "status": "Temp. Inactive",
                        "locations": [{"location_uid": 1}],
                    }
                ],
            },
            "success": True,
        }

        # Check the response
        response = client.get(
            "/api/enumerators/1/roles",
            query_string={"form_uid": 1, "enumerator_type": "surveyor"},
            content_type="application/json",
        )
        print(response.json)
        assert response.status_code == 200
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_update_role_status_for_non_admin_user_roles(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that the surveyor status can be updated by a non_admin user with roles
        """
        new_role = create_new_survey_role_with_permissions(
            # 5 - WRITE Enumerators
            client,
            test_user_credentials,
            "Survey Role",
            [5],
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

        # Update the enumerator
        payload = {
            "status": "Temp. Inactive",
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

        expected_response = {
            "data": {
                "form_uid": 1,
                "roles": [
                    {
                        "enumerator_type": "surveyor",
                        "status": "Temp. Inactive",
                        "locations": [{"location_uid": 1}],
                    }
                ],
            },
            "success": True,
        }

        # Check the response
        response = client.get(
            "/api/enumerators/1/roles",
            query_string={"form_uid": 1, "enumerator_type": "surveyor"},
            content_type="application/json",
        )
        print(response.json)
        assert response.status_code == 200
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_update_role_status_for_non_admin_user_no_roles(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that the surveyor status cannot be updated by a non_admin user without roles
        Expect 403 Fail
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

        # Update the enumerator
        payload = {
            "status": "Temp. Inactive",
            "form_uid": 1,
            "enumerator_type": "surveyor",
        }

        response = client.patch(
            "/api/enumerators/1/roles/status",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 403

        expected_response = {
            "success": False,
            "error": f"User does not have the required permission: WRITE Enumerators",
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_bulk_update_enumerators_for_super_admin_user(
        self,
        client,
        login_test_user,
        create_enumerator_column_config,
        upload_enumerators_csv,
        csrf_token,
    ):
        """
        Test that enumerators can be bulk updated by a super_admin user
        """

        # Update the enumerator
        payload = {
            "enumerator_uids": [1, 2],
            "form_uid": 1,
            "Mobile (Secondary)": "0123456789",
            "language": "Tagalog",
            "location_uid": [1],
        }

        response = client.patch(
            "/api/enumerators",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        expected_response = {
            "data": [
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "0123456789",
                        "Age": "1",
                    },
                    "email": "eric.dodge@idinsight.org",
                    "enumerator_id": "0294612",
                    "enumerator_uid": 1,
                    "name": "Eric Dodge",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Tagalog",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_locations": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "0123456789",
                        "Age": "2",
                    },
                    "email": "jahnavi.meher@idinsight.org",
                    "enumerator_id": "0294613",
                    "enumerator_uid": 2,
                    "name": "Jahnavi Meher",
                    "gender": "Female",
                    "home_address": "my house",
                    "language": "Tagalog",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_locations": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "1123456789",
                        "Age": "3",
                    },
                    "email": "jay.prakash@idinsight.org",
                    "enumerator_id": "0294614",
                    "enumerator_uid": 3,
                    "name": "Jay Prakash",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Hindi",
                    "mobile_primary": "0123456789",
                    "monitor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_status": "Active",
                    "surveyor_locations": None,
                    "surveyor_status": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "1123456789",
                        "Age": "4",
                    },
                    "email": "griffin.muteti@idinsight.org",
                    "enumerator_id": "0294615",
                    "enumerator_uid": 4,
                    "name": "Griffin Muteti",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Swahili",
                    "mobile_primary": "0123456789",
                    "monitor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "surveyor_status": "Active",
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/enumerators", query_string={"form_uid": 1})
        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_bulk_update_enumerators_for_survey_admin_user(
        self,
        client,
        login_test_user,
        create_enumerator_column_config,
        upload_enumerators_csv,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that enumerators can be bulk updated by a survey_admin user
        """
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=True,
            survey_uid=1,
            is_super_admin=False,
        )

        login_user(client, test_user_credentials)

        # Update the enumerator
        payload = {
            "enumerator_uids": [1, 2],
            "form_uid": 1,
            "Mobile (Secondary)": "0123456789",
            "language": "Tagalog",
        }

        response = client.patch(
            "/api/enumerators",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        expected_response = {
            "data": [
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "0123456789",
                        "Age": "1",
                    },
                    "email": "eric.dodge@idinsight.org",
                    "enumerator_id": "0294612",
                    "enumerator_uid": 1,
                    "name": "Eric Dodge",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Tagalog",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_locations": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "0123456789",
                        "Age": "2",
                    },
                    "email": "jahnavi.meher@idinsight.org",
                    "enumerator_id": "0294613",
                    "enumerator_uid": 2,
                    "name": "Jahnavi Meher",
                    "gender": "Female",
                    "home_address": "my house",
                    "language": "Tagalog",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_locations": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "1123456789",
                        "Age": "3",
                    },
                    "email": "jay.prakash@idinsight.org",
                    "enumerator_id": "0294614",
                    "enumerator_uid": 3,
                    "name": "Jay Prakash",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Hindi",
                    "mobile_primary": "0123456789",
                    "monitor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_status": "Active",
                    "surveyor_locations": None,
                    "surveyor_status": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "1123456789",
                        "Age": "4",
                    },
                    "email": "griffin.muteti@idinsight.org",
                    "enumerator_id": "0294615",
                    "enumerator_uid": 4,
                    "name": "Griffin Muteti",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Swahili",
                    "mobile_primary": "0123456789",
                    "monitor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "surveyor_status": "Active",
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/enumerators", query_string={"form_uid": 1})
        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_bulk_update_enumerators_for_non_admin_user_roles(
        self,
        client,
        login_test_user,
        create_enumerator_column_config,
        upload_enumerators_csv,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that enumerators can be bulk updated by a non_admin user with roles
        """
        new_role = create_new_survey_role_with_permissions(
            # 5 - WRITE Enumerators
            client,
            test_user_credentials,
            "Survey Role",
            [5],
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

        # Update the enumerator
        payload = {
            "enumerator_uids": [1, 2],
            "form_uid": 1,
            "Mobile (Secondary)": "0123456789",
            "language": "Tagalog",
        }

        response = client.patch(
            "/api/enumerators",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        expected_response = {
            "data": [
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "0123456789",
                        "Age": "1",
                    },
                    "email": "eric.dodge@idinsight.org",
                    "enumerator_id": "0294612",
                    "enumerator_uid": 1,
                    "name": "Eric Dodge",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Tagalog",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_locations": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "0123456789",
                        "Age": "2",
                    },
                    "email": "jahnavi.meher@idinsight.org",
                    "enumerator_id": "0294613",
                    "enumerator_uid": 2,
                    "name": "Jahnavi Meher",
                    "gender": "Female",
                    "home_address": "my house",
                    "language": "Tagalog",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_locations": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "1123456789",
                        "Age": "3",
                    },
                    "email": "jay.prakash@idinsight.org",
                    "enumerator_id": "0294614",
                    "enumerator_uid": 3,
                    "name": "Jay Prakash",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Hindi",
                    "mobile_primary": "0123456789",
                    "monitor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_status": "Active",
                    "surveyor_locations": None,
                    "surveyor_status": None,
                },
                {
                    "custom_fields": {
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                        "Mobile (Secondary)": "1123456789",
                        "Age": "4",
                    },
                    "email": "griffin.muteti@idinsight.org",
                    "enumerator_id": "0294615",
                    "enumerator_uid": 4,
                    "name": "Griffin Muteti",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Swahili",
                    "mobile_primary": "0123456789",
                    "monitor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "monitor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "geo_level_name": "District",
                                "location_id": "1",
                                "location_name": "ADILABAD",
                                "geo_level_uid": 1,
                                "location_uid": 1,
                            }
                        ]
                    ],
                    "surveyor_status": "Active",
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/enumerators", query_string={"form_uid": 1})
        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_bulk_update_enumerators_for_non_admin_user_no_roles(
        self,
        client,
        login_test_user,
        create_enumerator_column_config,
        upload_enumerators_csv,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that enumerators cannot be bulk updated by a non_admin user without roles
        Expect 403 Fail
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

        # Update the enumerator
        payload = {
            "enumerator_uids": [1, 2],
            "form_uid": 1,
            "Mobile (Secondary)": "0123456789",
            "language": "Tagalog",
        }

        response = client.patch(
            "/api/enumerators",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 403
        expected_response = {
            "success": False,
            "error": f"User does not have the required permission: WRITE Enumerators",
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_unmapped_columns(
        self, client, login_test_user, create_locations_for_enumerators_file, csrf_token
    ):
        """
        Upload the enumerators csv with unmapped columns
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_enumerators_no_language_no_address.csv"
        )

        # Read the enumerators.csv file and convert it to base64
        with open(filepath, "rb") as f:
            enumerators_csv = f.read()
            enumerators_csv_encoded = base64.b64encode(enumerators_csv).decode("utf-8")

        # Try to upload the enumerators csv
        payload = {
            "column_mapping": {
                "enumerator_id": "enumerator_id",
                "gender": "gender",
                "name": "name",
                "email": "email",
                "mobile_primary": "mobile_primary",
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

        print(response.json)

        # language is required
        assert response.status_code == 422

    def test_invalid_mobile_and_enumerator_types(
        self, client, login_test_user, create_locations_for_enumerators_file, csrf_token
    ):
        """
        Upload the enumerators csv
        """

        # Try to upload the enumerators csv
        # This is a payload that was provided by Utkarsh for testing 500 errors
        payload = {
            "column_mapping": {
                "custom_fields": {},
                "email": "email1",
                "enumerator_id": "enumerator_id",
                "enumerator_type": "type",
                "gender": "gender1",
                "home_address": "state_id",
                "language": "language1",
                "location_id_column": "locati1on_id",
                "mobile_primary": "mobile1",
                "name": "name",
            },
            "file": "ZW51bWVyYXRvcl9pZCxuYW1lLGVtYWlsMSxtb2JpbGUxLGdlbmRlcjEsbG9jYXRpMW9uX2lkLGxhbmd1YWdlMSxzdGF0ZV9pZCx0eXBlDQoxLHlvLHlvQGlkaW5zaWdodC5vcmcsMCxGLDEsU3BhbmlzaCwxLGVudW0NCg==",
            "mode": "overwrite",
        }

        response = client.post(
            "/api/enumerators",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        expected_response = {
            "errors": {
                "record_errors": {
                    "invalid_records": {
                        "ordered_columns": [
                            "row_number",
                            "enumerator_id",
                            "name",
                            "email1",
                            "mobile1",
                            "type",
                            "language1",
                            "gender1",
                            "state_id",
                            "locati1on_id",
                            "errors",
                        ],
                        "records": [
                            {
                                "email1": "yo@idinsight.org",
                                "enumerator_id": "1",
                                "errors": "Invalid mobile number - numbers must be between 10 and 20 characters in length and can only contain digits or the special characters '-', '.', '+', '(', or ')'; Invalid enumerator type - valid enumerator types are 'surveyor' and 'monitor' and can be separated by a semicolon if the enumerator has multiple types",
                                "gender1": "F",
                                "language1": "Spanish",
                                "locati1on_id": "1",
                                "mobile1": "0",
                                "name": "yo",
                                "row_number": 2,
                                "state_id": "1",
                                "type": "enum",
                            }
                        ],
                    },
                    "summary": {
                        "error_count": 2,
                        "total_correct_rows": 0,
                        "total_rows": 1,
                        "total_rows_with_errors": 1,
                    },
                    "summary_by_error_type": [
                        {
                            "error_count": 1,
                            "error_message": "The file contains 1 invalid mobile number(s) in the mobile_primary field. Mobile numbers must be between 10 and 20 characters in length and can only contain digits or the special characters '-', '.', '+', '(', or ')'. The following row numbers have invalid mobile numbers: 2",
                            "error_type": "Invalid mobile number",
                            "row_numbers_with_errors": [2],
                        },
                        {
                            "error_count": 1,
                            "error_message": "The file contains 1 invalid enumerator type(s) in the enumerator_type field. Valid enumerator types are 'surveyor' and 'monitor' and can be separated by a semicolon if the enumerator has multiple types. The following row numbers have invalid enumerator types: 2",
                            "error_type": "Invalid enumerator type",
                            "row_numbers_with_errors": [2],
                        },
                    ],
                }
            },
            "success": False,
        }

        print(response.json)

        assert response.status_code == 422

        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_get_enumerator_incorrect_query_params(
        self, client, login_test_user, upload_enumerators_csv
    ):
        """
        Test that enumerators can be retrieved with incorrect query params
        """

        # Try to get the enumerators with incorrect query params
        response = client.get("/api/enumerators", query_string={"form_id": 1})
        print(response.json)
        assert response.status_code == 400

        # Try to get the enumerators with incorrect query params
        response = client.get("/api/enumerators", query_string={"form_uid": "Hi"})
        print(response.json)
        assert response.status_code == 400

        # Try to get the enumerators with incorrect query params
        response = client.get("/api/enumerators", query_string={"form_uid": None})
        print(response.json)
        assert response.status_code == 400

    def test_upload_surveyor_stats_for_super_admin_user(
        self, client, login_test_user, create_surveyor_stats, csrf_token
    ):
        """
        Test uploading the surveyor stats for super_admin users
        """

        expected_response = {
            "success": True,
            "data": [
                {
                    "enumerator_id": "0294612",
                    "avg_num_submissions_per_day": 20,
                    "avg_num_completed_per_day": 7,
                },
                {
                    "enumerator_id": "0294613",
                    "avg_num_submissions_per_day": 15,
                    "avg_num_completed_per_day": 5,
                },
            ],
        }

        # Check the response
        response = client.get(
            "/api/enumerators/surveyor-stats",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        assert response.status_code == 200
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_surveyor_stats_for_survey_admin_user(
        self,
        client,
        login_test_user,
        create_surveyor_stats,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test uploading the surveyor stats for survey_admin users
        """
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=True,
            survey_uid=1,
            is_super_admin=False,
        )

        login_user(client, test_user_credentials)

        payload = {
            "form_uid": 1,
            "surveyor_stats": [
                {
                    "enumerator_id": "0294612",
                    "avg_num_submissions_per_day": 20,
                    "avg_num_completed_per_day": 7,
                },
                {
                    "enumerator_id": "0294613",
                    "avg_num_submissions_per_day": 15,
                    "avg_num_completed_per_day": 5,
                },
            ],
        }

        response = client.put(
            "/api/enumerators/surveyor-stats",
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
                    "enumerator_id": "0294612",
                    "avg_num_submissions_per_day": 20,
                    "avg_num_completed_per_day": 7,
                },
                {
                    "enumerator_id": "0294613",
                    "avg_num_submissions_per_day": 15,
                    "avg_num_completed_per_day": 5,
                },
            ],
        }

        # Check the response
        response = client.get(
            "/api/enumerators/surveyor-stats",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        assert response.status_code == 200
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_upload_surveyor_stats_for_non_admin_user_roles(
        self,
        client,
        login_test_user,
        create_surveyor_stats,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test uploading the surveyor stats for non_admin users with roles
        """
        new_role = create_new_survey_role_with_permissions(
            # 5 - WRITE Enumerators
            client,
            test_user_credentials,
            "Survey Role",
            [5],
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
            "surveyor_stats": [
                {
                    "enumerator_id": "0294612",
                    "avg_num_submissions_per_day": 20,
                    "avg_num_completed_per_day": 7,
                },
                {
                    "enumerator_id": "0294613",
                    "avg_num_submissions_per_day": 15,
                    "avg_num_completed_per_day": 5,
                },
            ],
        }

        response = client.put(
            "/api/enumerators/surveyor-stats",
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
                    "enumerator_id": "0294612",
                    "avg_num_submissions_per_day": 20,
                    "avg_num_completed_per_day": 7,
                },
                {
                    "enumerator_id": "0294613",
                    "avg_num_submissions_per_day": 15,
                    "avg_num_completed_per_day": 5,
                },
            ],
        }

        # Check the response
        response = client.get(
            "/api/enumerators/surveyor-stats",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        assert response.status_code == 200
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_upload_surveyor_stats_for_non_admin_user_no_roles(
        self,
        client,
        login_test_user,
        create_surveyor_stats,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test uploading the surveyor stats for non_admin users without roles
        Expect Fail 403
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

        payload = {
            "form_uid": 1,
            "surveyor_stats": [
                {
                    "enumerator_id": "0294612",
                    "avg_num_submissions_per_day": 20,
                    "avg_num_completed_per_day": 7,
                },
                {
                    "enumerator_id": "0294613",
                    "avg_num_submissions_per_day": 15,
                    "avg_num_completed_per_day": 5,
                },
            ],
        }

        response = client.put(
            "/api/enumerators/surveyor-stats",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 403

        expected_response = {
            "success": False,
            "error": f"User does not have the required permission: WRITE Enumerators",
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_get_enumerator_language(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        csrf_token,
        user_permissions,
        request,
    ):
        """
        Test to get list of enumerator languages
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/enumerators/languages",
            query_string={"form_uid": 1},
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "data": {
                    "form_uid": 1,
                    "languages": ["English", "Hindi", "Swahili", "Telugu"],
                },
                "success": True,
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: READ Enumerators",
                "success": False,
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_upload_enumerators_csv_missing_location_error(
        self,
        client,
        login_test_user,
        create_locations_for_enumerators_file,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that the enumerators csv upload fails when the location_id_column is missing
        when location is in the surveyor mapping criteria
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

        assert response.status_code == 422

        expected_response = {
            "errors": {
                "column_mapping": [
                    "Field name 'location_id_column' is missing from the column mapping but is required based on the mapping criteria."
                ]
            },
            "success": False,
        }

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_enumerators_csv_no_mapping_criteria_error(
        self,
        client,
        login_test_user,
        create_locations_for_enumerators_file,
        update_surveyor_mapping_criteria_to_none,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that the enumerators csv upload fails when no surveyor mapping criteria is set
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
                "gender": "gender1",
                "home_address": "home_address1",
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

        assert response.status_code == 422

        expected_response = {
            "error": "Supervisor to surveyor mapping criteria not found. Cannot upload enumerators without selecting a mapping criteria first.",
            "success": False,
        }

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_enumerators_csv_with_multiple_locations(
        self,
        client,
        login_test_user,
        create_locations_for_enumerators_file_medium,
        csrf_token,
    ):
        """
        Test that the enumerators csv can be uploaded
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_enumerators_multiple_locations.csv"
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

        expected_response = {
            "success": True,
            "data": [
                {
                    "enumerator_uid": 1,
                    "enumerator_id": "0294612",
                    "name": "Eric Dodge",
                    "email": "eric.dodge@idinsight.org",
                    "mobile_primary": "0123456789",
                    "home_address": "my house",
                    "gender": "Male",
                    "language": "English",
                    "custom_fields": {
                        "Age": "1",
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
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "location_id": "1",
                                "location_uid": 1,
                                "geo_level_uid": 1,
                                "location_name": "ADILABAD",
                                "geo_level_name": "District",
                            }
                        ],
                        [
                            {
                                "location_id": "2",
                                "location_uid": 2,
                                "geo_level_uid": 1,
                                "location_name": "ADILABAD2",
                                "geo_level_name": "District",
                            }
                        ],
                    ],
                    "monitor_status": None,
                    "monitor_locations": None,
                },
                {
                    "enumerator_uid": 2,
                    "enumerator_id": "0294613",
                    "name": "Jahnavi Meher",
                    "email": "jahnavi.meher@idinsight.org",
                    "mobile_primary": "0123456789",
                    "home_address": "my house",
                    "gender": "Female",
                    "language": "Telugu",
                    "custom_fields": {
                        "Age": "2",
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
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "location_id": "1",
                                "location_uid": 1,
                                "geo_level_uid": 1,
                                "location_name": "ADILABAD",
                                "geo_level_name": "District",
                            }
                        ]
                    ],
                    "monitor_status": None,
                    "monitor_locations": None,
                },
                {
                    "enumerator_uid": 3,
                    "enumerator_id": "0294614",
                    "name": "Jay Prakash",
                    "email": "jay.prakash@idinsight.org",
                    "mobile_primary": "0123456789",
                    "home_address": "my house",
                    "gender": "Male",
                    "language": "Hindi",
                    "custom_fields": {
                        "Age": "3",
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
                    "surveyor_status": None,
                    "surveyor_locations": None,
                    "monitor_status": "Active",
                    "monitor_locations": [
                        [
                            {
                                "location_id": "1",
                                "location_uid": 1,
                                "geo_level_uid": 1,
                                "location_name": "ADILABAD",
                                "geo_level_name": "District",
                            }
                        ],
                        [
                            {
                                "location_id": "2",
                                "location_uid": 2,
                                "geo_level_uid": 1,
                                "location_name": "ADILABAD2",
                                "geo_level_name": "District",
                            }
                        ],
                    ],
                },
                {
                    "enumerator_uid": 4,
                    "enumerator_id": "0294615",
                    "name": "Griffin Muteti",
                    "email": "griffin.muteti@idinsight.org",
                    "mobile_primary": "0123456789",
                    "home_address": "my house",
                    "gender": "Male",
                    "language": "Swahili",
                    "custom_fields": {
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
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        [
                            {
                                "location_id": "2",
                                "location_uid": 2,
                                "geo_level_uid": 1,
                                "location_name": "ADILABAD2",
                                "geo_level_name": "District",
                            }
                        ]
                    ],
                    "monitor_status": "Active",
                    "monitor_locations": [
                        [
                            {
                                "location_id": "2",
                                "location_uid": 2,
                                "geo_level_uid": 1,
                                "location_name": "ADILABAD2",
                                "geo_level_name": "District",
                            }
                        ]
                    ],
                },
            ],
        }
        # Check the response
        response = client.get("/api/enumerators", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}
