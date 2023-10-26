import jsondiff
import pytest
import base64
import pandas as pd
from pathlib import Path


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

        print(response.json)
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
        print(response.json)
        assert response.status_code == 200

    @pytest.fixture()
    def upload_targets_csv_no_locations(
        self, client, login_test_user, create_locations_for_targets_file, csrf_token
    ):
        """
        Upload the targets csv
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
        Upload the targets csv
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

    def test_upload_targets_csv(
        self, client, login_test_user, upload_targets_csv, csrf_token
    ):
        """
        Test that the targets csv can be uploaded
        """

        expected_response = {
            "data": [
                {
                    "custom_fields": {
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
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                },
                {
                    "custom_fields": {
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
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/targets", query_string={"form_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_paginate_targets(
        self, client, login_test_user, upload_targets_csv, csrf_token
    ):
        """
        Test that the targets csv can be uploaded
        """

        expected_response = {
            "data": [
                {
                    "custom_fields": {
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
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
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
        Test uploading targets csv with no locations mapped
        """

        expected_response = {
            "data": [
                {
                    "custom_fields": {
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
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                },
                {
                    "custom_fields": {
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
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/targets", query_string={"form_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_targets_csv_no_locations_no_geo_levels_defined(
        self, client, login_test_user, create_form, csrf_token
    ):
        """
        Test uploading targets csv with no locations mapped and no geo levels defined
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
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                },
                {
                    "custom_fields": {
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
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
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
                    "custom_fields": None,
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
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                },
                {
                    "custom_fields": None,
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
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
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
        print(response.json)
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
                                "errors": "Duplicate row; Duplicate target_id; The same target_id already exists for the form - target_id's must be unique for each form",
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
                                "errors": "Duplicate row; Duplicate target_id; The same target_id already exists for the form - target_id's must be unique for each form",
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
                        "error_count": 8,
                        "total_correct_rows": 0,
                        "total_rows": 3,
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
                            "error_message": "The file has 2 duplicate row(s). Duplicate rows are not allowed. The following row numbers are duplicates: 2, 3",
                            "error_type": "Duplicate rows",
                            "row_numbers_with_errors": [2, 3],
                        },
                        {
                            "error_count": 2,
                            "error_message": "The file has 2 duplicate target_id(s). The following row numbers contain target_id duplicates: 2, 3",
                            "error_type": "Duplicate target_id's in file",
                            "row_numbers_with_errors": [2, 3],
                        },
                        {
                            "error_count": 2,
                            "error_message": "The file contains 2 target_id(s) that have already been uploaded. The following row numbers contain target_id's that have already been uploaded: 2, 3",
                            "error_type": "target_id's found in database",
                            "row_numbers_with_errors": [2, 3],
                        },
                        {
                            "error_count": 1,
                            "error_message": "The file contains 1 location_id(s) that were not found in the uploaded locations data. The following row numbers contain invalid location_id's: 4",
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

    def test_upload_column_config(
        self, client, login_test_user, create_target_column_config, csrf_token
    ):
        """
        Test uploading the targets column config
        """

        expected_response = {
            "data": [
                {
                    "bulk_editable": False,
                    "column_name": "target_id",
                    "column_type": "basic_details",
                    "contains_pii": False,
                },
                {
                    "bulk_editable": True,
                    "column_name": "language",
                    "column_type": "basic_details",
                    "contains_pii": True,
                },
                {
                    "bulk_editable": False,
                    "column_name": "gender",
                    "column_type": "basic_details",
                    "contains_pii": True,
                },
                {
                    "bulk_editable": False,
                    "column_name": "Name",
                    "column_type": "custom_fields",
                    "contains_pii": True,
                },
                {
                    "bulk_editable": False,
                    "column_name": "Mobile no.",
                    "column_type": "custom_fields",
                    "contains_pii": True,
                },
                {
                    "bulk_editable": True,
                    "column_name": "Address",
                    "column_type": "custom_fields",
                    "contains_pii": True,
                },
                {
                    "bulk_editable": True,
                    "column_name": "bottom_geo_level_location",
                    "column_type": "location",
                    "contains_pii": True,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get(
            "/api/targets/column-config",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        assert response.status_code == 200
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_target(
        self, client, login_test_user, upload_targets_csv, csrf_token
    ):
        """
        Test that an individual target can be updated
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

        response = client.put(
            "/api/targets/2",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        expected_response = {
            "data": {
                "custom_fields": {
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
                "num_attempts": None,
                "refusal_flag": None,
                "revisit_sections": None,
                "target_assignable": None,
                "webapp_tag_color": None,
            },
            "success": True,
        }

        # Check the response
        response = client.get("/api/targets/2")
        assert response.status_code == 200
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_target_incorrect_custom_fields(
        self, client, login_test_user, upload_targets_csv, csrf_token
    ):
        """
        Test that an individual target can be updated
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

    def test_delete_target(self, client, login_test_user, upload_targets_csv):
        """
        Test that an individual target can be deleted
        """

        # Delete the target
        response = client.delete("/api/targets/1")

        assert response.status_code == 200

        response = client.get("/api/targets/1", content_type="application/json")

        assert response.status_code == 404

    def test_bulk_update_targets(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        csrf_token,
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

        response = client.patch(
            "/api/targets",
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
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                },
                {
                    "custom_fields": {
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
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/targets", query_string={"form_uid": 1})
        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_unmapped_columns(
        self, client, login_test_user, create_locations_for_targets_file, csrf_token
    ):
        """
        Upload the targets csv
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

    def test_add_columns_csv(
        self,
        client,
        login_test_user,
        upload_targets_csv,
        create_target_column_config,
        csrf_token,
    ):
        """
        Test that the targets csv can be uploaded
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_targets_new_columns.csv"
        )

        # Read the targets.csv file and convert it to base64
        with open(filepath, "rb") as f:
            targets_csv = f.read()
            targets_csv_encoded = base64.b64encode(targets_csv).decode("utf-8")

        # Try to upload the targets csv
        payload = {
            "column_mapping": {
                "target_id": "target_id1",
                "custom_fields": [
                    {
                        "field_label": "Mobile no. (Alternate)",
                        "column_name": "mobile_primary2",
                    },
                    {
                        "field_label": "Language (Alternate)",
                        "column_name": "language2",
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
        print(response.json)
        assert response.status_code == 200

        expected_response = {
            "data": [
                {
                    "custom_fields": {
                        "Address": "Hyderabad",
                        "Name": "Anil",
                        "Mobile no.": "1234567890",
                        "Mobile no. (Alternate)": "1234567890",
                        "Language (Alternate)": "Telugu",
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
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                },
                {
                    "custom_fields": {
                        "Address": "South Delhi",
                        "Name": "Anupama",
                        "Mobile no.": "1234567891",
                        "Mobile no. (Alternate)": "1234567891",
                        "Language (Alternate)": "Hindi",
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
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
                    "webapp_tag_color": None,
                },
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/targets", query_string={"form_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_add_columns_csv_incorrect_target_id(
        self,
        client,
        login_test_user,
        upload_targets_csv,
        create_target_column_config,
        csrf_token,
    ):
        """
        Test that the targets csv can be uploaded
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_targets_new_columns_invalid_target_id.csv"
        )

        # Read the targets.csv file and convert it to base64
        with open(filepath, "rb") as f:
            targets_csv = f.read()
            targets_csv_encoded = base64.b64encode(targets_csv).decode("utf-8")

        # Try to upload the targets csv
        payload = {
            "column_mapping": {
                "target_id": "target_id1",
                "custom_fields": [
                    {
                        "field_label": "Mobile no. (Alternate)",
                        "column_name": "mobile_primary2",
                    },
                    {
                        "field_label": "Language (Alternate)",
                        "column_name": "language2",
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
        print(response.json)
        assert response.status_code == 422

        expected_response = {
            "errors": {
                "record_errors": {
                    "invalid_records": {
                        "ordered_columns": [
                            "row_number",
                            "target_id1",
                            "mobile_primary2",
                            "language2",
                            "errors",
                        ],
                        "records": [
                            {
                                "errors": "The target_id was not found in the database for this form",
                                "language2": "Hindi",
                                "mobile_primary2": "1234567891",
                                "row_number": 3,
                                "target_id1": "3",
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
                            "error_message": "The file contains 1 target_id(s) that were not found in the database. When using the 'add columns' functionality the uploaded sheet must contain only target_id's that have already been uploaded. The following row numbers contain target_id's that were not found in the database: 3",
                            "error_type": "target_id's not found in database",
                            "row_numbers_with_errors": [3],
                        }
                    ],
                }
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_add_columns_csv_existing_columns(
        self,
        client,
        login_test_user,
        upload_targets_csv,
        create_target_column_config,
        csrf_token,
    ):
        """
        Test that the targets csv can be uploaded
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_targets_new_columns.csv"
        )

        # Read the targets.csv file and convert it to base64
        with open(filepath, "rb") as f:
            targets_csv = f.read()
            targets_csv_encoded = base64.b64encode(targets_csv).decode("utf-8")

        # Try to upload the targets csv
        payload = {
            "column_mapping": {
                "target_id": "target_id1",
                "language": "language2",
                "custom_fields": [
                    {
                        "field_label": "Mobile no.",
                        "column_name": "mobile_primary2",
                    }
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
            "errors": {
                "column_mapping": [
                    "Column 'Mobile no.' already exists in the targets column configuration. Only new columns can be uploaded using the 'add columns' functionality.",
                    "Column 'language' already exists in the targets column configuration. Only new columns can be uploaded using the 'add columns' functionality.",
                ]
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}
