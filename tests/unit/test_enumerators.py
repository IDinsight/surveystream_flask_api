import jsondiff
import pytest
import base64
import pandas as pd
from pathlib import Path


@pytest.mark.enumerators
class TestEnumerators:
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
                "enumerator_id": "enumerator_id",
                "first_name": "first_name",
                "middle_name": "middle_name",
                "last_name": "last_name",
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

    def test_upload_enumerators_csv(
        self, client, login_test_user, upload_enumerators_csv, csrf_token
    ):
        """
        Test that the enumerators csv can be uploaded
        """

        expected_response = {
            "data": [
                {
                    "custom_fields": {"Mobile (Secondary)": "1123456789"},
                    "email": "eric.dodge@idinsight.org",
                    "enumerator_id": "0294612",
                    "enumerator_uid": 1,
                    "first_name": "Eric",
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "English",
                    "last_name": "Dodge",
                    "middle_name": "NaN",
                    "mobile_primary": "0123456789",
                    "monitor_status": None,
                    "surveyor_status": "Active",
                    "surveyor_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                        }
                    ],
                    "monitor_locations": None,
                }
            ],
            "success": True,
        }

        # Check the response
        response = client.get("/api/enumerators", query_string={"form_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_enumerator(
        self, client, login_test_user, upload_enumerators_csv, csrf_token
    ):
        """
        Test that an individual enumerator can be updated
        """

        # Update the enumerator
        payload = {
            "enumerator_id": "0294612",
            "first_name": "Hi",
            "last_name": "Dodge",
            "email": "eric.dodge@idinsight.org",
            "mobile_primary": "0123456789",
            "language": "English",
            "gender": "Male",
            "home_address": "my house",
            "custom_fields": {"Mobile (Secondary)": "1123456789"},
        }

        response = client.put(
            "/api/enumerators/1",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        expected_response = {
            "data": {
                "custom_fields": {"Mobile (Secondary)": "1123456789"},
                "email": "eric.dodge@idinsight.org",
                "enumerator_id": "0294612",
                "enumerator_uid": 1,
                "first_name": "Hi",
                "gender": "Male",
                "home_address": "my house",
                "language": "English",
                "last_name": "Dodge",
                "middle_name": None,
                "mobile_primary": "0123456789",
            },
            "success": True,
        }

        # Check the response
        response = client.get("/api/enumerators/1")
        assert response.status_code == 200
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_delete_enumerator(self, client, login_test_user, upload_enumerators_csv):
        """
        Test that an individual enumerator can be deleted
        """

        # Delete the enumerator
        response = client.delete("/api/enumerators/1")

        assert response.status_code == 200

        response = client.get("/api/enumerators/1", content_type="application/json")

        assert response.status_code == 404

    def test_update_role_status(
        self, client, login_test_user, upload_enumerators_csv, csrf_token
    ):
        """
        Test that the surveyor status can be updated
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

    # def test_reupload_locations_csv(
    #     self, client, login_test_user, create_geo_levels_for_locations_file, csrf_token
    # ):
    #     """
    #     Test that the locations csv can be uploaded twice
    #     """

    #     filepath = (
    #         Path(__file__).resolve().parent
    #         / f"data/file_uploads/sample_locations_small.csv"
    #     )

    #     # Read the locations.csv file and convert it to base64
    #     with open(filepath, "rb") as f:
    #         locations_csv = f.read()
    #         locations_csv_encoded = base64.b64encode(locations_csv).decode("utf-8")

    #     # Upload the locations csv
    #     payload = {
    #         "geo_level_mapping": [
    #             {
    #                 "geo_level_uid": 1,
    #                 "location_name_column": "district_name",
    #                 "location_id_column": "district_id",
    #             },
    #             {
    #                 "geo_level_uid": 2,
    #                 "location_name_column": "mandal_name",
    #                 "location_id_column": "mandal_id",
    #             },
    #             {
    #                 "geo_level_uid": 3,
    #                 "location_name_column": "psu_name",
    #                 "location_id_column": "psu_id",
    #             },
    #         ],
    #         "file": locations_csv_encoded,
    #     }

    #     response = client.post(
    #         "/api/locations",
    #         query_string={"survey_uid": 1},
    #         json=payload,
    #         content_type="application/json",
    #         headers={"X-CSRF-Token": csrf_token},
    #     )
    #     assert response.status_code == 200

    #     response = client.post(
    #         "/api/locations",
    #         query_string={"survey_uid": 1},
    #         json=payload,
    #         content_type="application/json",
    #         headers={"X-CSRF-Token": csrf_token},
    #     )
    #     assert response.status_code == 200

    #     df = pd.read_csv(filepath, dtype=str)
    #     df.rename(
    #         columns={
    #             "district_id": "District ID",
    #             "district_name": "District Name",
    #             "mandal_id": "Mandal ID",
    #             "mandal_name": "Mandal Name",
    #             "psu_id": "PSU ID",
    #             "psu_name": "PSU Name",
    #         },
    #         inplace=True,
    #     )

    #     expected_response = {
    #         "data": {
    #             "ordered_columns": [
    #                 "District ID",
    #                 "District Name",
    #                 "Mandal ID",
    #                 "Mandal Name",
    #                 "PSU ID",
    #                 "PSU Name",
    #             ],
    #             "records": df.to_dict(orient="records"),
    #         },
    #         "success": True,
    #     }
    #     # Check the response
    #     response = client.get("/api/locations", query_string={"survey_uid": 1})

    #     checkdiff = jsondiff.diff(expected_response, response.json)
    #     assert checkdiff == {}

    # def test_locations_validations_geo_level_mapping_errors(
    #     self, client, login_test_user, create_geo_levels_for_locations_file, csrf_token
    # ):
    #     """
    #     Test that the locations csv can be uploaded
    #     """

    #     filepath = (
    #         Path(__file__).resolve().parent
    #         / f"data/file_uploads/sample_locations_small.csv"
    #     )

    #     # Read the locations.csv file and convert it to base64
    #     with open(filepath, "rb") as f:
    #         locations_csv = f.read()
    #         locations_csv_encoded = base64.b64encode(locations_csv).decode("utf-8")

    #     # Try to upload the locations csv
    #     payload = {
    #         "geo_level_mapping": [
    #             {
    #                 "geo_level_uid": 1,
    #                 "location_name_column": "district_name",
    #                 "location_id_column": "district_id",
    #             },
    #             {
    #                 "geo_level_uid": 1,
    #                 "location_name_column": "district_name",
    #                 "location_id_column": "district_id",
    #             },
    #             {
    #                 "geo_level_uid": 2,
    #                 "location_name_column": "mandal_name",
    #                 "location_id_column": "mandal_id",
    #             },
    #             {
    #                 "geo_level_uid": 4,
    #                 "location_name_column": "gp_name",
    #                 "location_id_column": "gp_id",
    #             },
    #         ],
    #         "file": locations_csv_encoded,
    #     }

    #     response = client.post(
    #         "/api/locations",
    #         query_string={"survey_uid": 1},
    #         json=payload,
    #         content_type="application/json",
    #         headers={"X-CSRF-Token": csrf_token},
    #     )

    #     assert response.status_code == 422
    #     assert "geo_level_mapping" in response.json["errors"]
    #     assert response.json["errors"]["geo_level_mapping"] == [
    #         "Each location type defined in the location type hierarchy should appear exactly once in the location type column mapping. Location type 'District' appears 2 times in the location type mapping.",
    #         "Each location type defined in the location type hierarchy should appear exactly once in the location type column mapping. Location type 'PSU' appears 0 times in the location type mapping.",
    #         "Location type '4' in the location type column mapping is not one of the location types for the survey.",
    #         "Column name 'district_id' appears more than once in the location type column mapping. Column names should be unique.",
    #         "Column name 'district_name' appears more than once in the location type column mapping. Column names should be unique.",
    #     ]

    # def test_locations_validations_file_errors(
    #     self, client, login_test_user, create_geo_levels_for_locations_file, csrf_token
    # ):
    #     """
    #     Test that the locations csv can be uploaded
    #     """

    #     filepath = (
    #         Path(__file__).resolve().parent
    #         / f"data/file_uploads/sample_locations_small_errors.csv"
    #     )

    #     # Read the locations.csv file and convert it to base64
    #     with open(filepath, "rb") as f:
    #         locations_csv = f.read()
    #         locations_csv_encoded = base64.b64encode(locations_csv).decode("utf-8")

    #     # Try to upload the locations csv
    #     payload = {
    #         "geo_level_mapping": [
    #             {
    #                 "geo_level_uid": 1,
    #                 "location_name_column": "district_name",
    #                 "location_id_column": "district_id",
    #             },
    #             {
    #                 "geo_level_uid": 2,
    #                 "location_name_column": "mandal_name",
    #                 "location_id_column": "mandal_id",
    #             },
    #             {
    #                 "geo_level_uid": 3,
    #                 "location_name_column": "psu_name",
    #                 "location_id_column": "psu_id",
    #             },
    #         ],
    #         "file": locations_csv_encoded,
    #     }

    #     response = client.post(
    #         "/api/locations",
    #         query_string={"survey_uid": 1},
    #         json=payload,
    #         content_type="application/json",
    #         headers={"X-CSRF-Token": csrf_token},
    #     )
    #     assert response.status_code == 422
    #     assert "file" in response.json["errors"]
    #     assert response.json["errors"]["file"] == [
    #         "Column name 'district_id' from the column mapping appears 2 times in the uploaded file. It should appear exactly once.",
    #         "Column name 'extra_column' in the csv file appears 0 times in the location type column mapping. It should appear exactly once.",
    #         "The file contains 3 blank fields. Blank fields are not allowed. Blank fields are found in the following columns and rows:\n'column': psu_name, 'row': 2\n'column': mandal_id, 'row': 4\n'column': psu_id, 'row': 9",
    #         "The file has 2 duplicate rows. Duplicate rows are not allowed. The following rows are duplicates:\n           district_id district_name mandal_id     mandal_name psu_name    psu_id district_id extra_column\nrow_number                                                                                                \n7                    1      ADILABAD      1101  ADILABAD RURAL   RAMPUR  17101147           1         asdf\n8                    1      ADILABAD      1101  ADILABAD RURAL   RAMPUR  17101147           1         asdf",
    #         "Location type PSU has location id's that are mapped to more than one parent location in column mandal_id. A location (defined by the location id column) cannot be assigned to multiple parents. Make sure to use a unique location id for each location. The following rows have location id's that are mapped to more than one parent location:\n           district_id district_name mandal_id     mandal_name psu_name    psu_id district_id extra_column\nrow_number                                                                                                \n1                    1      ADILABAD      1101  ADILABAD RURAL   ANKOLI  17101102           1         asdf\n11                   1      ADILABAD      1102  ADILABAD URBAN   ANKOLI  17101102           1         asdf",
    #     ]

    # def test_locations_validations_file_errors_first_row_blank(
    #     self, client, login_test_user, create_geo_levels_for_locations_file, csrf_token
    # ):
    #     """
    #     Test that the locations csv can be uploaded
    #     """

    #     filepath = (
    #         Path(__file__).resolve().parent
    #         / f"data/file_uploads/sample_locations_small_blankrow.csv"
    #     )

    #     # Read the locations.csv file and convert it to base64
    #     with open(filepath, "rb") as f:
    #         locations_csv = f.read()
    #         locations_csv_encoded = base64.b64encode(locations_csv).decode("utf-8")

    #     # Try to upload the locations csv
    #     payload = {
    #         "geo_level_mapping": [
    #             {
    #                 "geo_level_uid": 1,
    #                 "location_name_column": "district_name",
    #                 "location_id_column": "district_id",
    #             },
    #             {
    #                 "geo_level_uid": 2,
    #                 "location_name_column": "mandal_name",
    #                 "location_id_column": "mandal_id",
    #             },
    #             {
    #                 "geo_level_uid": 3,
    #                 "location_name_column": "psu_name",
    #                 "location_id_column": "psu_id",
    #             },
    #         ],
    #         "file": locations_csv_encoded,
    #     }

    #     response = client.post(
    #         "/api/locations",
    #         query_string={"survey_uid": 1},
    #         json=payload,
    #         content_type="application/json",
    #         headers={"X-CSRF-Token": csrf_token},
    #     )
    #     assert response.status_code == 422
    #     assert "file" in response.json["errors"]
    #     assert response.json["errors"]["file"] == [
    #         "Column names were not found in the file. Make sure the first row of the file contains column names."
    #     ]

    # def test_locations_validations_file_errors_empty_string(
    #     self, client, login_test_user, create_geo_levels_for_locations_file, csrf_token
    # ):
    #     """
    #     Test uploading an empty string as the locations base64 encoded csv
    #     """

    #     locations_csv_encoded = ""

    #     # Try to upload the locations csv
    #     payload = {
    #         "geo_level_mapping": [
    #             {
    #                 "geo_level_uid": 1,
    #                 "location_name_column": "district_name",
    #                 "location_id_column": "district_id",
    #             },
    #             {
    #                 "geo_level_uid": 2,
    #                 "location_name_column": "mandal_name",
    #                 "location_id_column": "mandal_id",
    #             },
    #             {
    #                 "geo_level_uid": 3,
    #                 "location_name_column": "psu_name",
    #                 "location_id_column": "psu_id",
    #             },
    #         ],
    #         "file": locations_csv_encoded,
    #     }

    #     response = client.post(
    #         "/api/locations",
    #         query_string={"survey_uid": 1},
    #         json=payload,
    #         content_type="application/json",
    #         headers={"X-CSRF-Token": csrf_token},
    #     )
    #     assert response.status_code == 422
    #     assert "file" in response.json["errors"]
    #     assert response.json["errors"]["file"] == ["This field is required."]

    # def test_locations_validations_file_errors_invalid_base64_length(
    #     self, client, login_test_user, create_geo_levels_for_locations_file, csrf_token
    # ):
    #     """
    #     Test uploading an invalid base64 string as the locations csv
    #     """

    #     locations_csv_encoded = "a"

    #     # Try to upload the locations csv
    #     payload = {
    #         "geo_level_mapping": [
    #             {
    #                 "geo_level_uid": 1,
    #                 "location_name_column": "district_name",
    #                 "location_id_column": "district_id",
    #             },
    #             {
    #                 "geo_level_uid": 2,
    #                 "location_name_column": "mandal_name",
    #                 "location_id_column": "mandal_id",
    #             },
    #             {
    #                 "geo_level_uid": 3,
    #                 "location_name_column": "psu_name",
    #                 "location_id_column": "psu_id",
    #             },
    #         ],
    #         "file": locations_csv_encoded,
    #     }

    #     response = client.post(
    #         "/api/locations",
    #         query_string={"survey_uid": 1},
    #         json=payload,
    #         content_type="application/json",
    #         headers={"X-CSRF-Token": csrf_token},
    #     )
    #     assert response.status_code == 422
    #     assert "file" in response.json["errors"]
    #     assert response.json["errors"]["file"] == [
    #         "File data has invalid base64 encoding"
    #     ]

    # def test_locations_validations_file_errors_invalid_base64_char(
    #     self, client, login_test_user, create_geo_levels_for_locations_file, csrf_token
    # ):
    #     """
    #     Test uploading an invalid base64 string as the locations csv
    #     """

    #     locations_csv_encoded = "))))"

    #     # Try to upload the locations csv
    #     payload = {
    #         "geo_level_mapping": [
    #             {
    #                 "geo_level_uid": 1,
    #                 "location_name_column": "district_name",
    #                 "location_id_column": "district_id",
    #             },
    #             {
    #                 "geo_level_uid": 2,
    #                 "location_name_column": "mandal_name",
    #                 "location_id_column": "mandal_id",
    #             },
    #             {
    #                 "geo_level_uid": 3,
    #                 "location_name_column": "psu_name",
    #                 "location_id_column": "psu_id",
    #             },
    #         ],
    #         "file": locations_csv_encoded,
    #     }

    #     response = client.post(
    #         "/api/locations",
    #         query_string={"survey_uid": 1},
    #         json=payload,
    #         content_type="application/json",
    #         headers={"X-CSRF-Token": csrf_token},
    #     )
    #     assert response.status_code == 422
    #     assert "file" in response.json["errors"]
    #     assert response.json["errors"]["file"] == [
    #         "File data has invalid base64 encoding"
    #     ]

    # def test_get_locations_null_result(
    #     self, client, login_test_user, create_geo_levels_for_locations_file, csrf_token
    # ):
    #     """
    #     Test that the locations can be fetched when there are geo levels but no location data uploaded
    #     """

    #     # Check the response
    #     response = client.get("/api/locations", query_string={"survey_uid": 1})

    #     assert response.status_code == 200

    #     expected_response = {
    #         "data": {
    #             "ordered_columns": [
    #                 "District ID",
    #                 "District Name",
    #                 "Mandal ID",
    #                 "Mandal Name",
    #                 "PSU ID",
    #                 "PSU Name",
    #             ],
    #             "records": [],
    #         },
    #         "success": True,
    #     }

    #     checkdiff = jsondiff.diff(expected_response, response.json)

    #     assert checkdiff == {}

    # def test_get_locations_null_result_no_geo_levels(
    #     self, client, login_test_user, csrf_token
    # ):
    #     """
    #     Test that the locations  can be fetched when there are no geo levels and no location data uploaded
    #     """

    #     # Check the response
    #     response = client.get("/api/locations", query_string={"survey_uid": 1})

    #     assert response.status_code == 200

    #     expected_response = {
    #         "data": {
    #             "ordered_columns": [],
    #             "records": [],
    #         },
    #         "success": True,
    #     }

    #     checkdiff = jsondiff.diff(expected_response, response.json)

    #     assert checkdiff == {}

    # def test_create_geo_levels_missing_keys(
    #     self, client, login_test_user, csrf_token, create_survey
    # ):
    #     """
    #     Insert new geo levels with missing keys to test the validator
    #     """

    #     payload = {
    #         "geo_levels": [
    #             {
    #                 "geo_level_uid": None,
    #                 "geo_level_name": "State",
    #             },
    #             {
    #                 "geo_level_uid": None,
    #                 "geo_level_name": "District",
    #             },
    #         ]
    #     }

    #     response = client.put(
    #         "/api/locations/geo-levels",
    #         query_string={"survey_uid": 1},
    #         json=payload,
    #         content_type="application/json",
    #         headers={"X-CSRF-Token": csrf_token},
    #     )
    #     print(response.json)
    #     assert response.status_code == 200
