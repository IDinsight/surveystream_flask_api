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

    def test_geo_levels_validate_hierarchy(
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
                    "parent_geo_level_uid": 1,
                },
                {
                    "geo_level_uid": 2,
                    "geo_level_name": "District",
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
            "Exactly one geo level in the hierarchy should have no parent geo level. The current hierarchy has 0 geo levels with no parent.",
            "Geo level State is referenced as its own parent.",
            "Each geo level should be referenced as a parent geo level exactly once. Geo level State is referenced as a parent 2 times.",
            "Each geo level should be referenced as a parent geo level exactly once. Geo level District is referenced as a parent 0 times.",
        ]

    def test_upload_locations_csv(
        self, client, login_test_user, create_survey, csrf_token
    ):
        """
        Test that the locations csv can be uploaded
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
