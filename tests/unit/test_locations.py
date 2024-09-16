import jsondiff
import pytest
import base64
import pandas as pd
from pathlib import Path
from utils import (
    create_new_survey_role_with_permissions,
    login_user,
    update_logged_in_user_roles,
)


@pytest.mark.locations
class TestLocations:
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
            ("user_with_no_permissions", False),
        ],
        ids=[
            "super_admin_permissions",
            "survey_admin_permissions",
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
            "config_status": "In Progress - Configuration",
            "created_by_user_uid": test_user_credentials["user_uid"],
        }

        response = client.post(
            "/api/surveys",
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

    @pytest.fixture()
    def upload_locations_csv(
        self,
        client,
        login_test_user,
        create_geo_levels_for_locations_file,
        csrf_token,
        test_user_credentials,
    ):
        """
        Upload locations csv as a setup step for the location tests
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

        print(response)

        assert response.status_code == 200

        yield

    def test_insert_geo_levels_for_super_admin_user(
        self, client, login_test_user, create_geo_levels
    ):
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

    def test_insert_geo_levels_for_survey_admin_user(
        self, client, login_test_user, test_user_credentials, csrf_token, create_survey
    ):
        """
        Test that survey admins can insert geo levels
            - change the logged-in user to a survey_admin
        Expect success since the same user has created the survey
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

        print(response)

        assert response.status_code == 200

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

        # revert user to super admin
        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_insert_geo_levels_for_non_admin_user_roles(
        self, client, login_test_user, test_user_credentials, csrf_token, create_survey
    ):
        """
        Test that non-admins can insert geo levels
            - change the logged-in user to non admin
            - add roles and permissions for WRITE Survey Locations
        Expect success
        """

        new_role = create_new_survey_role_with_permissions(
            # 3 - WRITE Survey Locations
            client,
            test_user_credentials,
            "Survey Role",
            [3],
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

        print(response)

        assert response.status_code == 200

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

        # revert user to super admin
        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_insert_geo_levels_for_non_admin_user_no_roles(
        self, client, login_test_user, test_user_credentials, csrf_token, create_survey
    ):
        """
        Test that non-admins without permissions cannot insert geo_levels
            - change the logged-in user to non admin
            - remove all roles
        Expect fail with a 403
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

        print(response)

        assert response.status_code == 403

        expected_response = {
            "success": False,
            "error": f"User does not have the required permission: WRITE Survey Locations",
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

    def test_update_geo_levels(
        self, client, login_test_user, create_geo_levels, csrf_token
    ):
        """
        Test that existing geo levels can be updated
        - test for a single user role since the endpoint has been tested on insert
        Expect a 200 success with the updated values
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
        Test the different cases of an invalid geo level hierarchy
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
        Test that the validations pass for a valid geo level hierarchy
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

    def test_upload_locations_csv_for_super_admin_user(
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

    def test_update_survey_prime_geo_level(
        self, client, login_test_user, test_user_credentials, csrf_token, create_survey
    ):
        """
        Test that non-admins can update prime_geo_level
            - this is done on the locations flow therefore Location permissions are required
            - change the logged-in user to non admin
            - add roles and permissions for WRITE Survey Locations
        Expect success
        """

        new_role = create_new_survey_role_with_permissions(
            # 3 - WRITE Survey Locations
            client,
            test_user_credentials,
            "Survey Role",
            [3],
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

        payload = {"prime_geo_level_uid": 1}

        response = client.put(
            "/api/locations/1/prime-geo-level",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response)

        assert response.status_code == 200

        # revert user to super admin
        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_upload_locations_csv_for_survey_admin_user(
        self,
        client,
        login_test_user,
        create_geo_levels_for_locations_file,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that the locations csv can be uploaded by survey admin users
            - change current user to survey_admin
        Expect success since the survey_admin created the survey
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

        print(response)

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

        # revert user to super admin
        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_upload_locations_csv_for_non_admin_user_roles(
        self,
        client,
        login_test_user,
        create_geo_levels_for_locations_file,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that the locations csv can be uploaded by non-admin users with roles
            - change current user to non-admin
            - add permissions for writing survey locations
            - write permissions should also handle read requests
        Expect success
        """
        new_role = create_new_survey_role_with_permissions(
            # 3 - WRITE Survey Locations
            client,
            test_user_credentials,
            "Survey Role",
            [3],
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

        print(response)

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

        # revert user to super admin
        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_upload_locations_csv_for_non_admin_user_no_roles(
        self,
        client,
        login_test_user,
        create_geo_levels_for_locations_file,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that the locations csv cannot be uploaded by non-admin users without roles
            - change current user to non-admin
            - remove all roles
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

        print(response)

        assert response.status_code == 403

        expected_response = {
            "success": False,
            "error": f"User does not have the required permission: WRITE Survey Locations",
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
        Test uploading locations with geo level mapping errors
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
        Test uploading locations with location file errors
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
        print(response.json["errors"]["file"])
        assert response.json["errors"]["file"] == [
            "Column name 'district_id' from the column mapping appears 2 times in the uploaded file. It should appear exactly once.",
            "The file contains 3 blank fields. Blank fields are not allowed. Blank fields are found in the following columns and rows:\n'column': psu_name, 'row': 3\n'column': mandal_id, 'row': 5\n'column': psu_id, 'row': 10",
            "The file has 2 duplicate rows. Duplicate rows are not allowed. The following rows are duplicates:\n           district_id district_name mandal_id     mandal_name psu_name    psu_id district_id extra_column\nrow_number                                                                                                \n8                    1      ADILABAD      1101  ADILABAD RURAL   RAMPUR  17101147           1         asdf\n9                    1      ADILABAD      1101  ADILABAD RURAL   RAMPUR  17101147           1         asdf",
            "Location type PSU has location id's that are mapped to more than one parent location in column mandal_id. A location (defined by the location id column) cannot be assigned to multiple parents. Make sure to use a unique location id for each location. The following rows have location id's that are mapped to more than one parent location:\n           district_id district_name mandal_id     mandal_name psu_name    psu_id district_id extra_column\nrow_number                                                                                                \n2                    1      ADILABAD      1101  ADILABAD RURAL   ANKOLI  17101102           1         asdf\n12                   1      ADILABAD      1102  ADILABAD URBAN   ANKOLI  17101102           1         asdf",
            "Location type District has location id's that have more than one location name. Make sure to use a unique location name for each location id. The following rows have location id's that have more than one location name:\n           district_id    district_name mandal_id            mandal_name  psu_name    psu_id district_id extra_column\nrow_number                                                                                                           \n13                   2  TEST DISTRICT 2      1103  TEST DISTRICT 2 URBAN      ASDF  17101103           1         asdf\n14                   2  TEST DISTRICT 3      1103  TEST DISTRICT 2 URBAN  ASDFASDF  17101104           1         asdf",
        ]

    def test_locations_validations_file_errors_first_row_blank(
        self, client, login_test_user, create_geo_levels_for_locations_file, csrf_token
    ):
        """
        Test uploading a locations file with the first row blank
        Should return an error
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
        print(response.json)
        assert "file" in response.json["message"]
        assert response.json["message"]["file"] == ["This field is required."]

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

    def test_get_locations_null_result_for_super_admin_user(
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

    def test_get_locations_null_result_for_survey_admin_user(
        self,
        client,
        login_test_user,
        create_geo_levels_for_locations_file,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that Survey Admins can get locations
        Expect success
        """
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=True,
            survey_uid=1,
            is_super_admin=False,
        )

        login_user(client, test_user_credentials)

        # Check the response
        response = client.get("/api/locations", query_string={"survey_uid": 1})

        print(response)

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

        # revert user to super admin
        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_get_locations_null_result_for_non_admin_user_roles(
        self,
        client,
        login_test_user,
        create_geo_levels_for_locations_file,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that non admins with READ permissions can get locations
            - change logged-in user to non-admin
            - assign the user only read permissions
        Expect success
        """

        new_role = create_new_survey_role_with_permissions(
            # 2 - READ Survey Locations
            client,
            test_user_credentials,
            "Survey Role",
            [2],
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

        # Check the response
        response = client.get("/api/locations", query_string={"survey_uid": 1})

        print(response)

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

        # revert user to super admin
        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_get_locations_null_result_for_non_admin_user_no_roles(
        self,
        client,
        login_test_user,
        create_geo_levels_for_locations_file,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test that non admins without READ permissions cannot get locations
            - change logged-in user to non-admin
            - remove all roles
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

        # Check the response
        response = client.get("/api/locations", query_string={"survey_uid": 1})

        print(response)

        assert response.status_code == 403

        expected_response = {
            "success": False,
            "error": f"User does not have the required permission: READ Survey Locations",
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

    def test_get_locations_null_result_no_geo_levels(
        self, client, login_test_user, csrf_token
    ):
        """
        Test that the locations can be fetched when there are no geo levels and no location data uploaded
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

    def test_get_locations_in_long_format(
        self,
        client,
        login_test_user,
        upload_locations_csv,
        csrf_token,
        user_permissions,
        request,
    ):
        """
        Test that the locations can be fetched in long format
        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        # Check the response
        response = client.get("/api/locations/long", query_string={"survey_uid": 1})

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "data": [
                    {
                        "geo_level_name": "District",
                        "geo_level_uid": 1,
                        "location_id": "1",
                        "location_name": "ADILABAD",
                        "location_uid": 1,
                        "parent_geo_level_uid": None,
                        "parent_location_uid": None,
                    },
                    {
                        "geo_level_name": "Mandal",
                        "geo_level_uid": 2,
                        "location_id": "1104",
                        "location_name": "BELA",
                        "location_uid": 3,
                        "parent_geo_level_uid": 1,
                        "parent_location_uid": 1,
                    },
                    {
                        "geo_level_name": "Mandal",
                        "geo_level_uid": 2,
                        "location_id": "1101",
                        "location_name": "ADILABAD RURAL",
                        "location_uid": 2,
                        "parent_geo_level_uid": 1,
                        "parent_location_uid": 1,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "1710495",
                        "location_name": "SANGVI",
                        "location_uid": 22,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 3,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "1710487",
                        "location_name": "PITGAON",
                        "location_uid": 21,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 3,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "1710482",
                        "location_name": "EKORI",
                        "location_uid": 20,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 3,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "1710470",
                        "location_name": "BELA",
                        "location_uid": 19,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 3,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "1710465",
                        "location_name": "KOBBAI",
                        "location_uid": 18,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 3,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "1710462",
                        "location_name": "DAHEGAON",
                        "location_uid": 17,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 3,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "1710459",
                        "location_name": "GUDA",
                        "location_uid": 16,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 3,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "1710458",
                        "location_name": "BHEDODA",
                        "location_uid": 15,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 3,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "1710457",
                        "location_name": "SANGIDI",
                        "location_uid": 14,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 3,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "17101280",
                        "location_name": "CHANDA T",
                        "location_uid": 13,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 2,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "17101279",
                        "location_name": "CHANDA",
                        "location_uid": 12,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 2,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "17101278",
                        "location_name": "CHANDA T",
                        "location_uid": 11,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 2,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "17101147",
                        "location_name": "RAMPUR",
                        "location_uid": 10,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 2,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "17101131",
                        "location_name": "KHANAPUR",
                        "location_uid": 9,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 2,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "17101127",
                        "location_name": "NEW RAMPUR",
                        "location_uid": 8,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 2,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "17101122",
                        "location_name": "YAPALGUDA",
                        "location_uid": 7,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 2,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "17101119",
                        "location_name": "BANGARIGUDA",
                        "location_uid": 6,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 2,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "17101107",
                        "location_name": "ANKAPUR",
                        "location_uid": 5,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 2,
                    },
                    {
                        "geo_level_name": "PSU",
                        "geo_level_uid": 3,
                        "location_id": "17101102",
                        "location_name": "ANKOLI",
                        "location_uid": 4,
                        "parent_geo_level_uid": 2,
                        "parent_location_uid": 2,
                    },
                ],
                "success": True,
            }
            checkdiff = jsondiff.diff(expected_response, response.json)

            assert checkdiff == {}

        else:
            assert response.status_code == 403
            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Survey Locations",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)

            assert checkdiff == {}

    def test_get_locations_in_long_format_geo_level_filter(
        self,
        client,
        login_test_user,
        upload_locations_csv,
        csrf_token,
        user_permissions,
        request,
    ):
        """
        Test that the locations can be fetched in long format with a geo level filter
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        # Check the response
        response = client.get(
            "/api/locations/long", query_string={"survey_uid": 1, "geo_level_uid": 2}
        )

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "data": [
                    {
                        "geo_level_name": "Mandal",
                        "geo_level_uid": 2,
                        "location_id": "1101",
                        "location_name": "ADILABAD RURAL",
                        "location_uid": 2,
                        "parent_geo_level_uid": 1,
                        "parent_location_uid": 1,
                    },
                    {
                        "geo_level_name": "Mandal",
                        "geo_level_uid": 2,
                        "location_id": "1104",
                        "location_name": "BELA",
                        "location_uid": 3,
                        "parent_geo_level_uid": 1,
                        "parent_location_uid": 1,
                    },
                ],
                "success": True,
            }
            checkdiff = jsondiff.diff(expected_response, response.json)

            assert checkdiff == {}

        else:
            assert response.status_code == 403
            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: READ Survey Locations",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)

            assert checkdiff == {}
