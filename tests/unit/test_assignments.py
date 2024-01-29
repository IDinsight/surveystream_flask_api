import jsondiff
import pytest
import base64
import pandas as pd
from pathlib import Path
from utils import set_target_assignable_status, update_logged_in_user_roles, login_user, \
    create_new_survey_role_with_permissions
from app import db


@pytest.mark.assignments
class TestAssignments:
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
    def create_form(self, client, login_test_user, csrf_token, create_survey):
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

        print(response.json)
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
        print(response.json)
        assert response.status_code == 200

    @pytest.fixture()
    def upload_enumerators_csv_no_locations(
        self, client, login_test_user, create_locations, csrf_token
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
        self, client, login_test_user, create_form, csrf_token
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
        print(response.json)
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

    @pytest.fixture()
    def upload_targets_csv_no_custom_fields(
        self, client, login_test_user, create_locations, csrf_token
    ):
        """
        Upload the targets csv with no custmo fields
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

    def test_assignments_no_enumerators_no_targets_no_geo_levels(
        self, client, login_test_user, create_form, csrf_token
    ):
        """
        Test the assignments endpoint response when key datasets are missing
        No geo levels
        No locations
        No enumerators
        No targets
        """

        expected_response = {
            "data": [],
            "success": True,
        }

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignments_no_enumerators_no_targets_no_locations(
        self, client, login_test_user, create_geo_levels, csrf_token
    ):
        """
        Test the assignments endpoint response when key datasets are missing
        No locations
        No enumerators
        No targets
        """

        expected_response = {
            "data": [],
            "success": True,
        }

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignments_no_enumerators_no_targets(
        self, client, login_test_user, create_locations, csrf_token
    ):
        """
        Test the assignments endpoint response when key datasets are missing
        No enumerators
        No targets
        """

        expected_response = {
            "data": [],
            "success": True,
        }

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignments_no_targets_for_super_admin_user(
        self, client, login_test_user, upload_enumerators_csv, csrf_token
    ):
        """
        Test the assignments endpoint response when key datasets are missing
        No targets
        """

        expected_response = {
            "data": [],
            "success": True,
        }

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignments_no_targets_for_survey_admin_user(
        self, client, login_test_user, upload_enumerators_csv, csrf_token,test_user_credentials
    ):
        """
        Using a survey_admin
        Test the assignments endpoint response when key datasets are missing
        No targets
        """
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=True,
            is_super_admin=False,
        )

        login_user(client, test_user_credentials)

        expected_response = {
            "data": [],
            "success": True,
        }

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client, test_user_credentials, is_survey_admin=False, is_super_admin=True
        )

        login_user(client, test_user_credentials)

    def test_assignments_no_targets_for_non_admin_user_roles(
        self, client, login_test_user, upload_enumerators_csv, csrf_token,test_user_credentials
    ):
        """
        Using a non_admin user with roles
        Test the assignments endpoint response when key datasets are missing
        No targets
        """
        new_role = create_new_survey_role_with_permissions(
            # 9 - WRITE Assignments
            client,
            test_user_credentials,
            "Survey Role",
            [9],
            1,
        )
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            is_super_admin=False,
            roles=[1]
        )

        login_user(client, test_user_credentials)

        expected_response = {
            "data": [],
            "success": True,
        }

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client, test_user_credentials, is_survey_admin=False, is_super_admin=True
        )

        login_user(client, test_user_credentials)

    def test_assignments_no_targets_for_non_admin_user_no_roles(
            self, client, login_test_user, upload_enumerators_csv, csrf_token, test_user_credentials
    ):
        """
        Using a non_admin user without roles
        Test the assignments endpoint response when key datasets are missing
        Expect 403 Fail; permissions denined
        """
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            is_super_admin=False,
            roles=[]
        )

        login_user(client, test_user_credentials)

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        assert response.status_code == 403

        expected_response = {
            "success": False,
            "error": f"User does not have the required permission: READ Assignments",
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client, test_user_credentials, is_survey_admin=False, is_super_admin=True
        )

        login_user(client, test_user_credentials)
    def test_assignments_empty_assignment_table(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        csrf_token,
    ):
        """
        Test the assignments endpoint response when the assignment table is empty
        """

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
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
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
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
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

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_create_assignment_for_super_admin_user(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        csrf_token,
    ):
        """
        Create an assignment between a single target and enumerator
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

        print(response.json)
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
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
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
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
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

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_create_assignment_for_survey_admin_user(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        csrf_token,
            test_user_credentials
    ):
        """
        Test create an assignment between a
        single target and enumerator using a survey_admin user
        """
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=True,
            is_super_admin=False,
        )

        login_user(client, test_user_credentials)

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

        print(response.json)
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
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
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
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
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

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client, test_user_credentials, is_survey_admin=False, is_super_admin=True
        )

        login_user(client, test_user_credentials)

    def test_create_assignment_for_non_admin_user_roles(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        csrf_token,
            test_user_credentials
    ):
        """
        Test create an assignment between a
        single target and enumerator using a non_admin user with roles
        """

        new_role = create_new_survey_role_with_permissions(
            # 9 - WRITE Assignments
            client,
            test_user_credentials,
            "Survey Role",
            [9],
            1,
        )
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            is_super_admin=False,
            roles=[1]
        )


        login_user(client, test_user_credentials)

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

        print(response.json)
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
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
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
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
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

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client, test_user_credentials, is_survey_admin=False, is_super_admin=True
        )

        login_user(client, test_user_credentials)

    def test_create_assignment_for_non_admin_user_no_roles(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        csrf_token,
            test_user_credentials
    ):
        """
        Test create an assignment between a
        single target and enumerator using a non_admin user without roles
        Expect a 403 Fail
        """


        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            is_super_admin=False,
            roles=[]
        )
        login_user(client, test_user_credentials)

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

        print(response.json)
        assert response.status_code == 403

        expected_response = {
            "success": False,
            "error": f"User does not have the required permission: WRITE Assignments",
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client, test_user_credentials, is_survey_admin=False, is_super_admin=True
        )

        login_user(client, test_user_credentials)

    def test_create_assignment_no_locations(
        self,
        client,
        login_test_user,
        upload_enumerators_csv_no_locations,
        upload_targets_csv_no_locations,
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

        print(response.json)
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
                    "last_attempt_survey_status_label": None,
                    "location_uid": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
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
                    "last_attempt_survey_status_label": None,
                    "location_uid": None,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": None,
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

    def test_multiple_assignments(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
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

        print(response.json)
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
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
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
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
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

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_remove_assignment(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
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

        print(response.json)
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

        print(response.json)
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
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
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
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
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

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_reassign_assignment(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
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

        print(response.json)
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

        print(response.json)
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
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
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
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
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

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        print(response.json)

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_dropout_enumerator_ineligible(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
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

        print(response.json)
        assert response.status_code == 422

        expected_response = {
            "message": 'The following enumerator_uid\'s have status "Dropout" and are ineligible for assignment: 1'
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

        print(response.json)
        assert response.status_code == 422

        expected_response = {
            "message": "The following target_uid's are not assignable for this form (most likely because they are complete): 1"
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

        print(response.json)
        assert response.status_code == 422

        expected_response = {
            "message": "The following target_uid's are not assignable for this form (most likely because they are complete): 1"
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

        print(response.json)
        assert response.status_code == 422

        expected_response = {
            "message": "The following target_uid's are not assignable for this form (most likely because they are complete): 1"
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignment_target_not_found(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
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

        print(response.json)
        assert response.status_code == 404

        expected_response = {
            "message": "The following target_uid's were not found for this form: 10"
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_assignment_enumerator_not_found(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
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
        print(response.json)
        assert response.status_code == 404

        expected_response = {
            "message": "The following enumerator_uid's were not found for this form: 10"
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_eligible_enumerators_response(
        self,
        app,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
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
                    "enumerator_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        }
                    ],
                    "enumerator_uid": 1,
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "English",
                    "mobile_primary": "0123456789",
                    "name": "Eric Dodge",
                    "surveyor_status": "Active",
                    "total_assigned_targets": 1,
                    "total_completed_targets": 0,
                    "total_pending_targets": 1,
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
                    "enumerator_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        }
                    ],
                    "enumerator_uid": 2,
                    "gender": "Female",
                    "home_address": "my house",
                    "language": "Telugu",
                    "mobile_primary": "0123456789",
                    "name": "Jahnavi Meher",
                    "surveyor_status": "Active",
                    "total_assigned_targets": 1,
                    "total_completed_targets": 1,
                    "total_pending_targets": 0,
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
                    "enumerator_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        }
                    ],
                    "enumerator_uid": 4,
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Swahili",
                    "mobile_primary": "0123456789",
                    "name": "Griffin Muteti",
                    "surveyor_status": "Active",
                    "total_assigned_targets": 0,
                    "total_completed_targets": 0,
                    "total_pending_targets": 0,
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
