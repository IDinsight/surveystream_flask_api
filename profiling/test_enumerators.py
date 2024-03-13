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
    def upload_enumerators_csv(
        self, client, login_test_user, create_locations_for_enumerators_file, csrf_token
    ):
        """
        Upload the enumerators csv
        """

        filepath = (
            Path(__file__).resolve().parent / f"assets/sample_enumerators_small.csv"
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

    def test_upload_merge_update_enumerators_csv(
        self, client, create_form, login_test_user, csrf_token, upload_enumerators_csv
    ):
        """
        Test that the enumerators merge functionality that columns can be updated
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"assets/sample_enumerators_small_updated.csv"
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
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        }
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
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        }
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
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        }
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
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        }
                    ],
                    "monitor_status": "Active",
                    "name": "Griff Muteti",
                    "surveyor_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        }
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
        Test that the enumerators merge functionality that new columns are being appended
        """
        # upload updated data with new columns appended to the original sheet uploaded by upload_enumerators_csv fixture

        filepath = (
            Path(__file__).resolve().parent
            / f"assets/sample_enumerators_small_append.csv"
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
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
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
                    "enumerator_uid": 2,
                    "gender": "Female",
                    "home_address": "my house",
                    "language": "Telugu",
                    "mobile_primary": "0123456789",
                    "monitor_locations": None,
                    "monitor_status": None,
                    "name": "Jan Meher",
                    "surveyor_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        }
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
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        }
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
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        }
                    ],
                    "monitor_status": "Active",
                    "name": "Griff Muteti",
                    "surveyor_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
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
                    "email": "rohan@idinsight.org",
                    "enumerator_id": "0294616",
                    "enumerator_uid": 5,
                    "gender": "Male",
                    "home_address": "house",
                    "language": "Hindi",
                    "mobile_primary": "0123456389",
                    "monitor_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        }
                    ],
                    "monitor_status": "Active",
                    "name": "Rohan M",
                    "surveyor_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
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
                    "email": "yashi@idinsight.org",
                    "enumerator_id": "0294617",
                    "enumerator_uid": 6,
                    "gender": "Female",
                    "home_address": "house",
                    "language": "Hindi",
                    "mobile_primary": "0123556389",
                    "monitor_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        }
                    ],
                    "monitor_status": "Active",
                    "name": "Yashi M",
                    "surveyor_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
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
                    "email": "utkarsh@idinsight.org",
                    "enumerator_id": "0294618",
                    "enumerator_uid": 7,
                    "gender": "Male",
                    "home_address": "house",
                    "language": "Hindi",
                    "mobile_primary": "0123556382",
                    "monitor_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        }
                    ],
                    "monitor_status": "Active",
                    "name": "Utkarsh",
                    "surveyor_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        }
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
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "geo_level_uid": 1,
                            "location_uid": 1,
                        }
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
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "geo_level_uid": 1,
                            "location_uid": 1,
                        }
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
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "geo_level_uid": 1,
                            "location_uid": 1,
                        }
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
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "geo_level_uid": 1,
                            "location_uid": 1,
                        }
                    ],
                    "monitor_status": "Active",
                    "surveyor_locations": [
                        {
                            "geo_level_name": "District",
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "geo_level_uid": 1,
                            "location_uid": 1,
                        }
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
