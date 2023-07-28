import jsondiff
import pytest
import base64
import pandas as pd
from pathlib import Path


@pytest.mark.locations
class TestLocations:
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
    def create_geo_levels(self, client, login_test_user, csrf_token, create_survey):
        """
        Insert new geo levels as a setup step for the geo levels tests
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
    def create_geo_levels_for_locations_file(
        self, client, login_test_user, csrf_token, create_survey
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

    def test_insert_geo_levels(self, client, login_test_user, create_geo_levels):
        """
        Test that the geo levels are inserted correctly
        The order of the geo levels in the payload should be reflected in the assignment of the geo_level_uid
        """

        # Test the geo level were inserted correctly
        response = client.get(
            "/api/locations/geo-levels", query_string={"survey_uid": 1}
        )
        expected_response = {
            "data": [
                {
                    "geo_level_uid": 1,
                    "geo_level_name": "State",
                    "parent_geo_level_uid": None,
                    "survey_uid": 1,
                },
                {
                    "geo_level_uid": 2,
                    "geo_level_name": "District",
                    "parent_geo_level_uid": 1,
                    "survey_uid": 1,
                },
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_geo_levels(
        self, client, login_test_user, create_geo_levels, csrf_token
    ):
        """
        Test that existing geo levels can be updated
        """

        # Try to update the existing geo levels
        payload = {
            "geo_levels": [
                {
                    "geo_level_uid": 1,
                    "geo_level_name": "State",
                    "parent_geo_level_uid": None,
                },
                {
                    "geo_level_uid": 2,
                    "geo_level_name": "District",
                    "parent_geo_level_uid": 1,
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

        response = client.get(
            "/api/locations/geo-levels", query_string={"survey_uid": 1}
        )

        expected_response = {
            "data": [
                {
                    "geo_level_uid": 1,
                    "geo_level_name": "State",
                    "parent_geo_level_uid": None,
                    "survey_uid": 1,
                },
                {
                    "geo_level_uid": 2,
                    "geo_level_name": "District",
                    "parent_geo_level_uid": 1,
                    "survey_uid": 1,
                },
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_geo_levels_deferrable_constraint_violation(
        self, client, login_test_user, create_geo_levels, csrf_token
    ):
        """
        Test that updating geo levels with a temporary unique constraint violation succeeds
        """

        # Try to update the existing geo levels
        payload = {
            "geo_levels": [
                {
                    "geo_level_uid": 1,
                    "geo_level_name": "District",
                    "parent_geo_level_uid": None,
                },
                {
                    "geo_level_uid": 2,
                    "geo_level_name": "State",
                    "parent_geo_level_uid": 1,
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

        # Check the response
        response = client.get(
            "/api/locations/geo-levels", query_string={"survey_uid": 1}
        )

        expected_response = {
            "data": [
                {
                    "geo_level_uid": 1,
                    "geo_level_name": "District",
                    "parent_geo_level_uid": None,
                    "survey_uid": 1,
                },
                {
                    "geo_level_uid": 2,
                    "geo_level_name": "State",
                    "parent_geo_level_uid": 1,
                    "survey_uid": 1,
                },
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_geo_levels_constraint_violation(
        self, client, login_test_user, create_geo_levels, csrf_token
    ):
        """
        Test that updating geo levels with a unique constraint violation fails
        """

        # Try to update the existing geo levels with a unique constraint violation on `geo_level_name`
        payload = {
            "geo_levels": [
                {
                    "geo_level_uid": 1,
                    "geo_level_name": "State",
                    "parent_geo_level_uid": None,
                },
                {
                    "geo_level_uid": 2,
                    "geo_level_name": "State",
                    "parent_geo_level_uid": 1,
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
        assert response.status_code == 500

    def test_delete_geo_level(
        self, client, login_test_user, create_geo_levels, csrf_token
    ):
        """
        Test that a geo level can be deleted
        """

        # Try to delete a geo level that is not being referenced by another geo level
        payload = {
            "geo_levels": [
                {
                    "geo_level_uid": 1,
                    "geo_level_name": "State",
                    "parent_geo_level_uid": None,
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

        # Check the response
        response = client.get(
            "/api/locations/geo-levels", query_string={"survey_uid": 1}
        )

        expected_response = {
            "data": [
                {
                    "geo_level_uid": 1,
                    "geo_level_name": "State",
                    "parent_geo_level_uid": None,
                    "survey_uid": 1,
                },
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_delete_reporting_geo_level(
        self, client, login_test_user, create_geo_levels, csrf_token
    ):
        """
        Test that a geo level cannot be deleted if it is being referenced by another geo level
        """

        # Try to delete a geo level that is being referenced by another geo level
        payload = {
            "geo_levels": [
                {
                    "geo_level_uid": 2,
                    "geo_level_name": "District",
                    "parent_geo_level_uid": 1,
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
        assert response.status_code == 500

    def test_delete_survey_cascade_to_geo_level(
        self, client, login_test_user, create_geo_levels, csrf_token
    ):
        """
        Test that deleting a survey cascades to deleting the geo level data
        """

        # Try to delete a geo level that is being referenced by another geo level
        response = client.delete(
            "/api/surveys/1",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 204

        # Check the response
        response = client.get(
            "/api/locations/geo-levels", query_string={"survey_uid": 1}
        )

        expected_response = {
            "data": [],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_geo_levels_validate_hierarchy_invalid_hierarchy(
        self, client, login_test_user, create_survey, csrf_token
    ):
        """
        Test that existing geo levels can be updated
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
                    "parent_geo_level_uid": None,
                },
                {
                    "geo_level_uid": None,
                    "geo_level_name": "Mandal",
                    "parent_geo_level_uid": None,
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

        # Case 1:
        # Multiple child nodes
        payload = {
            "geo_levels": [
                {
                    "geo_level_uid": 1,
                    "geo_level_name": "State",
                    "parent_geo_level_uid": None,
                },
                {
                    "geo_level_uid": 2,
                    "geo_level_name": "District",
                    "parent_geo_level_uid": 1,
                },
                {
                    "geo_level_uid": 3,
                    "geo_level_name": "Mandal",
                    "parent_geo_level_uid": 1,
                },
            ],
            "validate_hierarchy": True,
        }

        response = client.put(
            "/api/locations/geo-levels",
            query_string={"survey_uid": 1, "validate_hierarchy": "true"},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        # Check the response
        assert response.json["errors"] == [
            "Each location type should have at most one child location type. Location type 'State' has 2 child location types:\nDistrict, Mandal"
        ]

        # Case 2:
        # No root node
        payload = {
            "geo_levels": [
                {
                    "geo_level_uid": 1,
                    "geo_level_name": "State",
                    "parent_geo_level_uid": 3,
                },
                {
                    "geo_level_uid": 2,
                    "geo_level_name": "District",
                    "parent_geo_level_uid": 1,
                },
                {
                    "geo_level_uid": 3,
                    "geo_level_name": "Mandal",
                    "parent_geo_level_uid": 2,
                },
            ],
            "validate_hierarchy": True,
        }

        response = client.put(
            "/api/locations/geo-levels",
            query_string={"survey_uid": 1, "validate_hierarchy": "true"},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        # Check the response
        assert response.json["errors"] == [
            "The hierarchy should have exactly one top level location type (ie, a location type with no parent). The current hierarchy has 0 location types with no parent."
        ]

        # Case 3:
        # Multiple root nodes
        payload = {
            "geo_levels": [
                {
                    "geo_level_uid": 1,
                    "geo_level_name": "State",
                    "parent_geo_level_uid": None,
                },
                {
                    "geo_level_uid": 2,
                    "geo_level_name": "District",
                    "parent_geo_level_uid": None,
                },
                {
                    "geo_level_uid": 3,
                    "geo_level_name": "Mandal",
                    "parent_geo_level_uid": 2,
                },
            ],
            "validate_hierarchy": True,
        }

        response = client.put(
            "/api/locations/geo-levels",
            query_string={"survey_uid": 1, "validate_hierarchy": "true"},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        # Check the response
        assert response.json["errors"] == [
            "The hierarchy should have exactly one top level location type (ie, a location type with no parent). The current hierarchy has 2 location types with no parent:\nState, District"
        ]

        # Case 4:
        # Check for a disconnected hierarchy
        payload = {
            "geo_levels": [
                {
                    "geo_level_uid": 1,
                    "geo_level_name": "State",
                    "parent_geo_level_uid": None,
                },
                {
                    "geo_level_uid": 2,
                    "geo_level_name": "District",
                    "parent_geo_level_uid": 3,
                },
                {
                    "geo_level_uid": 3,
                    "geo_level_name": "Mandal",
                    "parent_geo_level_uid": 2,
                },
            ],
            "validate_hierarchy": True,
        }

        response = client.put(
            "/api/locations/geo-levels",
            query_string={"survey_uid": 1, "validate_hierarchy": "true"},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        assert response.json["errors"] == [
            "All location types in the hierarchy should be able to be connected back to the top level location type via a chain of parent location type references. The current hierarchy has 2 location types that cannot be connected:\nDistrict, Mandal"
        ]

        # Case 5:
        # Check for a disconnected hierarchy
        # Caused by self-reference and non-existent parent
        payload = {
            "geo_levels": [
                {
                    "geo_level_uid": 1,
                    "geo_level_name": "State",
                    "parent_geo_level_uid": None,
                },
                {
                    "geo_level_uid": 2,
                    "geo_level_name": "District",
                    "parent_geo_level_uid": 2,
                },
                {
                    "geo_level_uid": 3,
                    "geo_level_name": "Mandal",
                    "parent_geo_level_uid": 5,
                },
            ],
            "validate_hierarchy": True,
        }

        response = client.put(
            "/api/locations/geo-levels",
            query_string={"survey_uid": 1, "validate_hierarchy": "true"},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        assert response.json["errors"] == [
            "All location types in the hierarchy should be able to be connected back to the top level location type via a chain of parent location type references. The current hierarchy has 2 location types that cannot be connected:\nDistrict, Mandal",
            "Location type 'District' is referenced as its own parent. Self-referencing is not allowed.",
            "Location type 'Mandal' references a parent location type with unique id '5' that is not found in the hierarchy.",
        ]

        # Case 6:
        # Duplicate uid's and names
        payload = {
            "geo_levels": [
                {
                    "geo_level_uid": 1,
                    "geo_level_name": "State",
                    "parent_geo_level_uid": None,
                },
                {
                    "geo_level_uid": 1,
                    "geo_level_name": "District",
                    "parent_geo_level_uid": 2,
                },
                {
                    "geo_level_uid": 3,
                    "geo_level_name": "District",
                    "parent_geo_level_uid": 5,
                },
            ],
            "validate_hierarchy": True,
        }

        response = client.put(
            "/api/locations/geo-levels",
            query_string={"survey_uid": 1, "validate_hierarchy": "true"},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        assert response.json["errors"] == [
            "Each location type unique id defined in the location type hierarchy should appear exactly once in the hierarchy. Location type with geo_level_uid='1' appears 2 times in the hierarchy.",
            "Each location type name defined in the location type hierarchy should appear exactly once in the hierarchy. Location type with geo_level_name='District' appears 2 times in the hierarchy.",
        ]

    def test_geo_levels_validate_hierarchy_valid_hierarchy(
        self, client, login_test_user, create_survey, csrf_token
    ):
        """
        Test that existing geo levels can be updated
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
                    "parent_geo_level_uid": None,
                },
                {
                    "geo_level_uid": None,
                    "geo_level_name": "Mandal",
                    "parent_geo_level_uid": None,
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

        # Try to update the existing geo levels
        payload = {
            "geo_levels": [
                {
                    "geo_level_uid": 1,
                    "geo_level_name": "State",
                    "parent_geo_level_uid": None,
                },
                {
                    "geo_level_uid": 2,
                    "geo_level_name": "District",
                    "parent_geo_level_uid": 1,
                },
                {
                    "geo_level_uid": 3,
                    "geo_level_name": "Mandal",
                    "parent_geo_level_uid": 2,
                },
            ],
            "validate_hierarchy": True,
        }

        response = client.put(
            "/api/locations/geo-levels",
            query_string={"survey_uid": 1, "validate_hierarchy": "true"},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

    def test_upload_locations_csv(
        self, client, login_test_user, create_geo_levels_for_locations_file, csrf_token
    ):
        """
        Test that the locations csv can be uploaded
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

    def test_reupload_locations_csv(
        self, client, login_test_user, create_geo_levels_for_locations_file, csrf_token
    ):
        """
        Test that the locations csv can be uploaded twice
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_locations_small.csv"
        )

        # Read the locations.csv file and convert it to base64
        with open(filepath, "rb") as f:
            locations_csv = f.read()
            locations_csv_encoded = base64.b64encode(locations_csv).decode("utf-8")

        # Upload the locations csv
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

    def test_locations_validations_geo_level_mapping_errors(
        self, client, login_test_user, create_geo_levels_for_locations_file, csrf_token
    ):
        """
        Test that the locations csv can be uploaded
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
                    "geo_level_uid": 4,
                    "location_name_column": "gp_name",
                    "location_id_column": "gp_id",
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

        assert response.status_code == 422
        assert "geo_level_mapping" in response.json["errors"]
        assert response.json["errors"]["geo_level_mapping"] == [
            "Each location type defined in the location type hierarchy should appear exactly once in the location type column mapping. Location type 'District' appears 2 times in the location type mapping.",
            "Each location type defined in the location type hierarchy should appear exactly once in the location type column mapping. Location type 'PSU' appears 0 times in the location type mapping.",
            "Location type '4' in the location type column mapping is not one of the location types for the survey.",
            "Column name 'district_id' appears more than once in the location type column mapping. Column names should be unique.",
            "Column name 'district_name' appears more than once in the location type column mapping. Column names should be unique.",
        ]

    def test_locations_validations_file_errors(
        self, client, login_test_user, create_geo_levels_for_locations_file, csrf_token
    ):
        """
        Test that the locations csv can be uploaded
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_locations_small_errors.csv"
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
        assert response.status_code == 422
        assert "file" in response.json["errors"]
        assert response.json["errors"]["file"] == [
            "Column name 'district_id' from the column mapping appears 2 times in the uploaded file. It should appear exactly once.",
            "Column name 'extra_column' in the csv file appears 0 times in the location type column mapping. It should appear exactly once.",
            "The file contains 3 blank fields. Blank fields are not allowed. Blank fields are found in the following columns and rows:\n'column': psu_name, 'row': 2\n'column': mandal_id, 'row': 4\n'column': psu_id, 'row': 9",
            "The file has 2 duplicate rows. Duplicate rows are not allowed. The following rows are duplicates:\n           district_id district_name mandal_id     mandal_name psu_name    psu_id district_id extra_column\nrow_number                                                                                                \n7                    1      ADILABAD      1101  ADILABAD RURAL   RAMPUR  17101147           1         asdf\n8                    1      ADILABAD      1101  ADILABAD RURAL   RAMPUR  17101147           1         asdf",
            "Location type PSU has location id's that are mapped to more than one parent location in column mandal_id. A location (defined by the location id column) cannot be assigned to multiple parents. Make sure to use a unique location id for each location. The following rows have location id's that are mapped to more than one parent location:\n           district_id district_name mandal_id     mandal_name psu_name    psu_id district_id extra_column\nrow_number                                                                                                \n1                    1      ADILABAD      1101  ADILABAD RURAL   ANKOLI  17101102           1         asdf\n11                   1      ADILABAD      1102  ADILABAD URBAN   ANKOLI  17101102           1         asdf",
        ]

    def test_locations_validations_file_errors_first_row_blank(
        self, client, login_test_user, create_geo_levels_for_locations_file, csrf_token
    ):
        """
        Test that the locations csv can be uploaded
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_locations_small_blankrow.csv"
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
        assert response.status_code == 422
        assert "file" in response.json["errors"]
        assert response.json["errors"]["file"] == [
            "Column names were not found in the file. Make sure the first row of the file contains column names."
        ]

    def test_locations_validations_file_errors_empty_string(
        self, client, login_test_user, create_geo_levels_for_locations_file, csrf_token
    ):
        """
        Test uploading an empty string as the locations base64 encoded csv
        """

        locations_csv_encoded = ""

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
        assert response.status_code == 422
        assert "file" in response.json["errors"]
        assert response.json["errors"]["file"] == ["This field is required."]

    def test_locations_validations_file_errors_invalid_base64_length(
        self, client, login_test_user, create_geo_levels_for_locations_file, csrf_token
    ):
        """
        Test uploading an invalid base64 string as the locations csv
        """

        locations_csv_encoded = "a"

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
        assert response.status_code == 422
        assert "file" in response.json["errors"]
        assert response.json["errors"]["file"] == [
            "File data has invalid base64 encoding"
        ]

    def test_locations_validations_file_errors_invalid_base64_char(
        self, client, login_test_user, create_geo_levels_for_locations_file, csrf_token
    ):
        """
        Test uploading an invalid base64 string as the locations csv
        """

        locations_csv_encoded = "))))"

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
        assert response.status_code == 422
        assert "file" in response.json["errors"]
        assert response.json["errors"]["file"] == [
            "File data has invalid base64 encoding"
        ]

    def test_get_locations_null_result(
        self, client, login_test_user, create_geo_levels_for_locations_file, csrf_token
    ):
        """
        Test that the locations can be fetched when there are geo levels but no location data uploaded
        """

        # Check the response
        response = client.get("/api/locations", query_string={"survey_uid": 1})

        assert response.status_code == 200

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
                "records": [],
            },
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_get_locations_null_result_no_geo_levels(
        self, client, login_test_user, csrf_token
    ):
        """
        Test that the locations  can be fetched when there are no geo levels and no location data uploaded
        """

        # Check the response
        response = client.get("/api/locations", query_string={"survey_uid": 1})

        assert response.status_code == 200

        expected_response = {
            "data": {
                "ordered_columns": [],
                "records": [],
            },
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)

        assert checkdiff == {}

    def test_create_geo_levels_missing_keys(
        self, client, login_test_user, csrf_token, create_survey
    ):
        """
        Insert new geo levels with missing keys to test the validator
        """

        payload = {
            "geo_levels": [
                {
                    "geo_level_uid": None,
                    "geo_level_name": "State",
                },
                {
                    "geo_level_uid": None,
                    "geo_level_name": "District",
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
