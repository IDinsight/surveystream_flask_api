import jsondiff
import pytest


@pytest.mark.roles
class TestRoles:
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
    def create_roles(self, client, login_test_user, csrf_token, create_survey):
        """
        Insert new roles as a setup step for the roles tests
        """

        payload = {
            "roles": [
                {
                    "role_uid": None,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                },
                {
                    "role_uid": None,
                    "role_name": "Regional Coordinator",
                    "reporting_role_uid": 1,
                },
            ]
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        yield

    def test_insert_roles(self, client, login_test_user, create_roles):
        """
        Test that the roles are inserted correctly
        The order of the roles in the payload should be reflected in the assignment of the role_uid
        """

        # Test the roles were inserted correctly
        response = client.get("/api/roles", query_string={"survey_uid": 1})
        expected_response = {
            "data": [
                {
                    "role_uid": 1,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                    "survey_uid": 1,
                },
                {
                    "role_uid": 2,
                    "role_name": "Regional Coordinator",
                    "reporting_role_uid": 1,
                    "survey_uid": 1,
                },
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_roles(self, client, login_test_user, create_roles, csrf_token):
        """
        Test that existing roles can be updated
        """

        # Try to update the existing roles
        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                },
                {
                    "role_uid": 2,
                    "role_name": "State Coordinator",
                    "reporting_role_uid": 1,
                },
            ]
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        response = client.get("/api/roles", query_string={"survey_uid": 1})

        expected_response = {
            "data": [
                {
                    "role_uid": 1,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                    "survey_uid": 1,
                },
                {
                    "role_uid": 2,
                    "role_name": "State Coordinator",
                    "reporting_role_uid": 1,
                    "survey_uid": 1,
                },
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_roles_deferrable_constraint_violation(
        self, client, login_test_user, create_roles, csrf_token
    ):
        """
        Test that updating roles with a temporary unique constraint violation succeeds
        """

        # Try to update the existing roles
        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Regional Coordinator",
                    "reporting_role_uid": None,
                },
                {
                    "role_uid": 2,
                    "role_name": "Core User",
                    "reporting_role_uid": 1,
                },
            ]
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Check the response
        response = client.get("/api/roles", query_string={"survey_uid": 1})

        expected_response = {
            "data": [
                {
                    "role_uid": 1,
                    "role_name": "Regional Coordinator",
                    "reporting_role_uid": None,
                    "survey_uid": 1,
                },
                {
                    "role_uid": 2,
                    "role_name": "Core User",
                    "reporting_role_uid": 1,
                    "survey_uid": 1,
                },
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_roles_constraint_violation(
        self, client, login_test_user, create_roles, csrf_token
    ):
        """
        Test that updating roles with a temporary unique constraint violation succeeds
        """

        # Try to update the existing roles with a unique constraint violation on `role_name`
        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                },
                {
                    "role_uid": 2,
                    "role_name": "Core User",
                    "reporting_role_uid": 1,
                },
            ]
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 500

    def test_delete_role(self, client, login_test_user, create_roles, csrf_token):
        """
        Test that a role can be deleted
        """

        # Try to delete a role that is not being referenced by another role
        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                },
            ]
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Check the response
        response = client.get("/api/roles", query_string={"survey_uid": 1})

        expected_response = {
            "data": [
                {
                    "role_uid": 1,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                    "survey_uid": 1,
                },
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_delete_reporting_role(
        self, client, login_test_user, create_roles, csrf_token
    ):
        """
        Test that a role cannot be deleted if it is being referenced by another role
        """

        # Try to delete a role that is being referenced by another role
        payload = {
            "roles": [
                {
                    "role_uid": 2,
                    "role_name": "Regional Coordinator",
                    "reporting_role_uid": 1,
                },
            ]
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 500
