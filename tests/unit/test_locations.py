import jsondiff
import pytest


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
        response = client.get("/api/locations/geo-levels", query_string={"survey_uid": 1})
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

    def test_update_geo_levels(self, client, login_test_user, create_geo_levels, csrf_token):
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

        response = client.get("/api/locations/geo-levels", query_string={"survey_uid": 1})

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
        response = client.get("/api/locations/geo-levels", query_string={"survey_uid": 1})

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

    def test_delete_geo_level(self, client, login_test_user, create_geo_levels, csrf_token):
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
        response = client.get("/api/locations/geo-levels", query_string={"survey_uid": 1})

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
    
    def test_delete_survey(
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
        response = client.get("/api/locations/geo-levels", query_string={"survey_uid": 1})

        expected_response = {
            "data": [],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}
