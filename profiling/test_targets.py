import base64
from pathlib import Path

import jsondiff
import pandas as pd
import pytest


@pytest.mark.targets
class TestTargets:
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
            Path(__file__).resolve().parent / f"assets/sample_locations_small.csv"
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
                    "allow_null_values": False,
                    "contains_pii": False,
                    "column_source": "target_id1",
                },
                {
                    "column_name": "language",
                    "column_type": "basic_details",
                    "allow_null_values": True,
                    "contains_pii": True,
                    "column_source": "language",
                },
                {
                    "column_name": "gender",
                    "column_type": "basic_details",
                    "allow_null_values": False,
                    "contains_pii": True,
                    "column_source": "gender",
                },
                {
                    "column_name": "Name",
                    "column_type": "custom_fields",
                    "allow_null_values": False,
                    "contains_pii": True,
                    "column_source": "name",
                },
                {
                    "column_name": "Mobile no.",
                    "column_type": "custom_fields",
                    "allow_null_values": False,
                    "contains_pii": True,
                    "column_source": "mobile_primary",
                },
                {
                    "column_name": "Address",
                    "column_type": "custom_fields",
                    "allow_null_values": True,
                    "contains_pii": True,
                    "column_source": "address",
                },
                {
                    "column_name": "bottom_geo_level_location",
                    "column_type": "location",
                    "allow_null_values": True,
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
        print(response.json)

        yield

    @pytest.fixture()
    def upload_targets_csv(
        self, client, login_test_user, create_locations_for_targets_file, csrf_token
    ):
        """
        Upload the targets csv
        """

        filepath = Path(__file__).resolve().parent / f"assets/sample_targets_small.csv"

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
        print(response.json)
        assert response.status_code == 200

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
                },
            ],
        }
        # Check the response
        response = client.get("/api/targets", query_string={"form_uid": 1})
        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_merge_csv(
        self,
        client,
        login_test_user,
        upload_targets_csv,
        create_target_column_config,
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

        filepath = Path(__file__).resolve().parent / f"assets/sample_targets_merge.csv"

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
                "location_id_column": "psu_id1",
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
                        "Address": "India",
                        "Mobile no.": "1234567890",
                        "column_mapping": {
                            "language": "language1",
                            "target_id": "target_id1",
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary2",
                                    "field_label": "Mobile no. (Alternate)",
                                },
                                {"column_name": "address1", "field_label": "Address"},
                            ],
                            "location_id_column": "psu_id1",
                        },
                        "Mobile no. (Alternate)": "1234567890",
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
                },
                {
                    "target_uid": 2,
                    "target_id": "2",
                    "language": "Telugu",
                    "gender": "Female",
                    "location_uid": 4,
                    "form_uid": 1,
                    "custom_fields": {
                        "Name": "Anupama",
                        "Address": "Kenya",
                        "Mobile no.": "1234567891",
                        "column_mapping": {
                            "language": "language1",
                            "target_id": "target_id1",
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary2",
                                    "field_label": "Mobile no. (Alternate)",
                                },
                                {"column_name": "address1", "field_label": "Address"},
                            ],
                            "location_id_column": "psu_id1",
                        },
                        "Mobile no. (Alternate)": "1234567891",
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
                },
                {
                    "target_uid": 3,
                    "target_id": "3",
                    "language": "Tagalog",
                    "gender": None,
                    "location_uid": 4,
                    "form_uid": 1,
                    "custom_fields": {
                        "Address": "Philippines",
                        "column_mapping": {
                            "language": "language1",
                            "target_id": "target_id1",
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary2",
                                    "field_label": "Mobile no. (Alternate)",
                                },
                                {"column_name": "address1", "field_label": "Address"},
                            ],
                            "location_id_column": "psu_id1",
                        },
                        "Mobile no. (Alternate)": "1234567892",
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
                },
            ],
        }
        # Check the response
        response = client.get("/api/targets", query_string={"form_uid": 1})
        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}
